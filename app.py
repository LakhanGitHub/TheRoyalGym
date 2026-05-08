import os
import time
import hmac
import secrets
import sqlite3
import logging
import calendar
from datetime import timedelta, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    init_db, seed_db,
    get_member_by_id, get_all_members,
    get_member_by_email, get_member_by_login, create_enquiry,
    count_members_registered_today,
    update_member_role, update_member_password, delete_member, count_admins,
    get_all_plans, get_plan_by_id, create_plan, update_plan, delete_plan,
    create_member, update_member, update_member_self,
    get_all_payments, get_payment_by_id,
    create_payment, update_payment, delete_payment,
    is_valid_email, is_valid_mobile, is_valid_indian_mobile,
    is_valid_username, normalize_username_to_email,
)

PLAN_DURATIONS = {
    'Trial Plan': (0, 5),
    'Monthly':    (1, 0),
    'Quarterly':  (3, 0),
    'Yearly':     (12, 0),
}
GENDER_OPTIONS = ('Male', 'Female', 'Other')
PAYMENT_METHODS = ('cash', 'upi', 'card', 'online')
PAYMENT_STATUSES = ('paid', 'pending')


def _format_plan_duration(months, days):
    """Human-readable duration label, e.g. '5 days', '1 month', '3 months'."""
    months = int(months or 0)
    days = int(days or 0)
    if days and not months:
        return f"{days} day{'s' if days != 1 else ''}"
    if months and not days:
        return f"{months} month{'s' if months != 1 else ''}"
    if months and days:
        return f"{months} month{'s' if months != 1 else ''} {days} day{'s' if days != 1 else ''}"
    return '0 days'


def _add_duration(start_iso, months, days):
    """Add `months` (with month-end clamp) then `days` to an ISO YYYY-MM-DD string."""
    start = date.fromisoformat(start_iso)
    months = int(months or 0)
    days = int(days or 0)
    if months:
        total = (start.month - 1) + months
        new_year = start.year + total // 12
        new_month = total % 12 + 1
        last_day = calendar.monthrange(new_year, new_month)[1]
        new_day = min(start.day, last_day)
        start = date(new_year, new_month, new_day)
    if days:
        start = start + timedelta(days=days)
    return start.isoformat()


def _membership_status(plan_expire_iso):
    """Derive membership status from plan_expire_date. Status is never stored.

    Returns a dict {label, css_class, days_remaining, is_expired}.
    `days_remaining` is positive while the plan is active; `is_expired` flips
    to True once the expiry date is in the past, in which case
    `days_remaining` reports how many days ago the plan expired (positive).
    """
    if not plan_expire_iso:
        return {
            'label': 'No active plan',
            'css_class': 'expiry-active',
            'days_remaining': 0,
            'is_expired': False,
        }
    try:
        expire = date.fromisoformat(plan_expire_iso)
    except ValueError:
        return {
            'label': 'No active plan',
            'css_class': 'expiry-active',
            'days_remaining': 0,
            'is_expired': False,
        }
    delta = (expire - date.today()).days
    if delta < 0:
        return {
            'label': 'Expired',
            'css_class': 'expiry-expired',
            'days_remaining': -delta,
            'is_expired': True,
        }
    if delta <= 7:
        return {
            'label': 'Expiring soon',
            'css_class': 'expiry-warning',
            'days_remaining': delta,
            'is_expired': False,
        }
    return {
        'label': 'Active',
        'css_class': 'expiry-active',
        'days_remaining': delta,
        'is_expired': False,
    }


ADMIN_NAV_ITEMS = [
    {'label': 'Members',       'endpoint': 'admin_members',  'desc': 'Add, edit and search members.',         'color': 'cyan'},
    {'label': 'Plans',         'endpoint': 'admin_plans',    'desc': 'Membership plans and pricing.',         'color': 'pink'},
    {'label': 'Trainers',      'endpoint': None,             'desc': 'Roster, schedules and payouts.',        'color': 'purple'},
    {'label': 'Payments',      'endpoint': 'admin_payments', 'desc': 'Paid and pending invoices.',            'color': 'orange'},
    {'label': 'Attendance',    'endpoint': None,             'desc': 'Daily check-in records.',               'color': 'cyan'},
    {'label': 'Diet',          'endpoint': None,             'desc': 'Meal plans for members.',               'color': 'pink'},
    {'label': 'Equipment',     'endpoint': None,             'desc': 'Inventory and purchase records.',       'color': 'purple'},
    {'label': 'Enquiries',     'endpoint': None,             'desc': 'Leads from the contact form.',          'color': 'orange'},
    {'label': 'Workout Plans', 'endpoint': None,             'desc': 'Training routines and sets.',           'color': 'cyan'},
    {'label': 'Feedback',      'endpoint': None,             'desc': 'Member reviews and ratings.',           'color': 'pink'},
    {'label': 'Settings',      'endpoint': 'admin_settings', 'desc': 'Roles, passwords and account control.', 'color': 'purple'},
]

IS_PRODUCTION = os.environ.get('FLASK_ENV', '').lower() == 'production'

app = Flask(__name__)

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    if IS_PRODUCTION:
        raise RuntimeError('SECRET_KEY must be set in production')
    _secret = secrets.token_hex(32)
app.secret_key = _secret

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

if not app.debug:
    logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)


# ---------- Rate limiting (in-memory, per-IP) ----------
_LOGIN_BUCKETS = {}
_ENQUIRY_BUCKETS = {}
_LOGIN_LIMIT = (5, 900)      # 5 attempts per 15 minutes
_ENQUIRY_LIMIT = (5, 60)     # 5 submissions per minute


def _rate_limited(buckets, key, limit):
    max_hits, window = limit
    now = time.time()
    history = [t for t in buckets.get(key, []) if now - t < window]
    if len(history) >= max_hits:
        buckets[key] = history
        return True
    history.append(now)
    buckets[key] = history
    return False


def _client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()


# ---------- CSRF ----------
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def _valid_csrf(submitted):
    expected = session.get('csrf_token', '')
    if not submitted or not expected:
        return False
    return hmac.compare_digest(str(submitted), str(expected))


app.jinja_env.globals['csrf_token'] = generate_csrf_token
app.jinja_env.globals['format_plan_duration'] = _format_plan_duration


# ---------- Auth decorators ----------
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('user_id'):
                flash('Please log in to continue.', 'error')
                return redirect(url_for('login'))
            if roles and session.get('user_role') not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


login_required = role_required()
admin_required = role_required('admin')
member_required = role_required('user')


def _dashboard_url_for(role):
    return url_for('admin_dashboard') if role == 'admin' else url_for('member_profile')


# ---------- Security headers ----------
@app.after_request
def set_security_headers(resp):
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('Referrer-Policy', 'no-referrer')
    resp.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; "
        "img-src 'self' https://images.unsplash.com data:; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src https://fonts.gstatic.com; "
        "script-src 'self'; "
        "frame-ancestors 'none'"
    )
    return resp


# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(_dashboard_url_for(session.get('user_role')))

    email_value = ''
    if request.method == 'POST':
        if _rate_limited(_LOGIN_BUCKETS, _client_ip(), _LOGIN_LIMIT):
            flash('Too many login attempts. Please try again later.', 'error')
            return render_template('login.html', email=''), 429

        if not _valid_csrf(request.form.get('csrf_token')):
            abort(403)

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        email_value = email

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html', email=email_value)

        try:
            user = get_member_by_login(email)
            if user and check_password_hash(user['password_hash'], password):
                user_id = user['id']
                user_name = user['name']
                user_role = user['role']
                session.clear()
                session.permanent = True
                session['user_id'] = user_id
                session['user_name'] = user_name
                session['user_role'] = user_role
                session['csrf_token'] = secrets.token_hex(32)
                flash(f'Welcome back, {user_name}!', 'success')
                return redirect(_dashboard_url_for(user_role))
            flash('Invalid email or password.', 'error')
            return render_template('login.html', email=email_value)
        except sqlite3.Error:
            app.logger.exception('Login DB error')
            flash('Login failed. Please try again.', 'error')
            return render_template('login.html', email=email_value)

    return render_template('login.html', email=email_value)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/terms')
def terms():
    return render_template('terms.html')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    metrics = {
        'total_members':         len(get_all_members()),
        'today_registrations':   count_members_registered_today(),
        'men':                   0,
        'women':                 0,
        'active_membership':     0,
        'subscription_expiring': 0,
    }
    return render_template(
        'admin_dashboard.html',
        nav_items=ADMIN_NAV_ITEMS,
        metrics=metrics,
        active_tab='Dashboard',
    )


@app.route('/admin/settings')
@admin_required
def admin_settings():
    users = get_all_members()
    return render_template(
        'admin_settings.html',
        nav_items=ADMIN_NAV_ITEMS,
        users=users,
        current_user_id=session['user_id'],
        active_tab='Settings',
    )


@app.route('/admin/settings/users/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_settings_role(user_id):
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    if user_id == session['user_id']:
        flash('You cannot change your own role.', 'error')
        return redirect(url_for('admin_settings'))

    target = get_member_by_id(user_id)
    if not target:
        flash('User not found.', 'error')
        return redirect(url_for('admin_settings'))

    new_role = 'user' if target['role'] == 'admin' else 'admin'

    if new_role == 'user' and count_admins() <= 1:
        flash('Cannot demote the last remaining admin.', 'error')
        return redirect(url_for('admin_settings'))

    try:
        update_member_role(user_id, new_role)
        flash(f"{target['name']}'s role updated to {new_role}.", 'success')
    except sqlite3.Error:
        app.logger.exception('Role update failed')
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/users/<int:user_id>/password', methods=['POST'])
@admin_required
def admin_settings_password(user_id):
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    target = get_member_by_id(user_id)
    if not target:
        flash('User not found.', 'error')
        return redirect(url_for('admin_settings'))

    new_password     = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not new_password or not confirm_password:
        flash('Both password fields are required.', 'error')
        return redirect(url_for('admin_settings'))
    if len(new_password) < 6 or len(new_password) > 200:
        flash('Password must be between 6 and 200 characters.', 'error')
        return redirect(url_for('admin_settings'))
    if new_password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('admin_settings'))

    try:
        update_member_password(user_id, generate_password_hash(new_password))
        flash(f"Password reset for {target['name']}.", 'success')
    except sqlite3.Error:
        app.logger.exception('Password update failed')
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_settings_delete(user_id):
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    if user_id == session['user_id']:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin_settings'))

    target = get_member_by_id(user_id)
    if not target:
        flash('User not found.', 'error')
        return redirect(url_for('admin_settings'))

    try:
        rowcount = delete_member(user_id)
        if rowcount == 0:
            app.logger.warning(
                'Settings delete affected 0 rows: id=%s name=%r', user_id, target['name'],
            )
            flash('Action failed. The user may have already been removed.', 'error')
        else:
            app.logger.info(
                'User deleted via settings: id=%s name=%r role=%s by_admin=%s',
                user_id, target['name'], target['role'], session.get('user_id'),
            )
            flash(f"Deleted {target['name']}.", 'success')
    except sqlite3.Error:
        app.logger.exception('Settings delete failed: id=%s', user_id)
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('admin_settings'))


@app.route('/admin/plans')
@admin_required
def admin_plans():
    plans = get_all_plans()
    return render_template(
        'admin_plans.html',
        nav_items=ADMIN_NAV_ITEMS,
        plans=plans,
        active_tab='Plans',
    )


def _parse_plan_form():
    """Validate name + fee from request.form.
    Returns (name, duration_months, duration_days, fee, error)."""
    name = request.form.get('name', '').strip()
    fee_raw = request.form.get('fee', '').strip()

    if name not in PLAN_DURATIONS:
        return None, None, None, None, 'Plan name must be one of: ' + ', '.join(PLAN_DURATIONS.keys()) + '.'

    try:
        fee = float(fee_raw)
    except ValueError:
        return None, None, None, None, 'Fee must be a valid number.'
    if fee < 0 or fee > 1_000_000:
        return None, None, None, None, 'Fee must be between 0 and 1,000,000.'

    months, days = PLAN_DURATIONS[name]
    return name, months, days, fee, None


@app.route('/admin/plans/new', methods=['GET', 'POST'])
@admin_required
def admin_plans_new():
    prefill = {'name': request.form.get('name', ''), 'fee': request.form.get('fee', '')}

    if request.method == 'POST':
        if not _valid_csrf(request.form.get('csrf_token')):
            abort(403)

        name, duration_months, duration_days, fee, err = _parse_plan_form()
        if err:
            flash(err, 'error')
            return render_template(
                'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
                active_tab='Plans', mode='new', plan=None, prefill=prefill,
                allowed_names=list(PLAN_DURATIONS.keys()),
                name_durations=PLAN_DURATIONS,
            )

        try:
            create_plan(name, duration_months, fee, duration_days=duration_days)
            flash(f'Plan "{name}" created.', 'success')
            return redirect(url_for('admin_plans'))
        except sqlite3.IntegrityError:
            flash(f'A "{name}" plan already exists. Edit the existing one or delete it first.', 'error')
        except sqlite3.Error:
            app.logger.exception('Plan create failed')
            flash('Action failed. Please try again.', 'error')

        return render_template(
            'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
            active_tab='Plans', mode='new', plan=None, prefill=prefill,
            allowed_names=list(PLAN_DURATIONS.keys()),
            name_durations=PLAN_DURATIONS,
        )

    return render_template(
        'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
        active_tab='Plans', mode='new', plan=None, prefill=prefill,
        allowed_names=list(PLAN_DURATIONS.keys()),
        name_durations=PLAN_DURATIONS,
    )


@app.route('/admin/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_plans_edit(plan_id):
    plan = get_plan_by_id(plan_id)
    if not plan:
        flash('Plan not found.', 'error')
        return redirect(url_for('admin_plans'))

    prefill = {
        'name': request.form.get('name', plan['name']),
        'fee':  request.form.get('fee',  f"{plan['fee']:.2f}"),
    }

    if request.method == 'POST':
        if not _valid_csrf(request.form.get('csrf_token')):
            abort(403)

        name, duration_months, duration_days, fee, err = _parse_plan_form()
        if err:
            flash(err, 'error')
            return render_template(
                'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
                active_tab='Plans', mode='edit', plan=plan, prefill=prefill,
                allowed_names=list(PLAN_DURATIONS.keys()),
                name_durations=PLAN_DURATIONS,
            )

        try:
            update_plan(plan_id, name, duration_months, fee, duration_days=duration_days)
            flash(f'Plan "{name}" updated.', 'success')
            return redirect(url_for('admin_plans'))
        except sqlite3.IntegrityError:
            flash(f'A "{name}" plan already exists. Pick a different name or delete the duplicate.', 'error')
        except sqlite3.Error:
            app.logger.exception('Plan update failed')
            flash('Action failed. Please try again.', 'error')

        return render_template(
            'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
            active_tab='Plans', mode='edit', plan=plan, prefill=prefill,
            allowed_names=list(PLAN_DURATIONS.keys()),
            name_durations=PLAN_DURATIONS,
        )

    return render_template(
        'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
        active_tab='Plans', mode='edit', plan=plan, prefill=prefill,
        allowed_names=list(PLAN_DURATIONS.keys()),
        name_durations=PLAN_DURATIONS,
    )


@app.route('/admin/plans/<int:plan_id>/delete', methods=['POST'])
@admin_required
def admin_plans_delete(plan_id):
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    plan = get_plan_by_id(plan_id)
    if not plan:
        flash('Plan not found.', 'error')
        return redirect(url_for('admin_plans'))

    try:
        delete_plan(plan_id)
        flash(f'Deleted plan "{plan["name"]}".', 'success')
    except sqlite3.Error:
        app.logger.exception('Plan delete failed')
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('admin_plans'))


@app.route('/admin/members')
@admin_required
def admin_members():
    today = date.today()
    return render_template(
        'admin_members.html',
        nav_items=ADMIN_NAV_ITEMS,
        members=get_all_members(role='user'),
        active_tab='Members',
        today_iso=today.isoformat(),
        current_month=today.strftime('%Y-%m'),
    )


def _empty_member_prefill():
    return {
        'username': '', 'name': '', 'mobile': '+91', 'age': '',
        'gender': '', 'join_date': '', 'address': '', 'plan_id': '',
    }


def _prefill_from_member(member):
    return {
        'username':  member['email'] or '',
        'name':      member['name'] or '',
        'mobile':    member['mobile'] or '+91',
        'age':       str(member['age']) if member['age'] is not None else '',
        'gender':    member['gender'] or '',
        'join_date': member['join_date'] or '',
        'address':   member['address'] or '',
        'plan_id':   str(member['plan_id']) if member['plan_id'] else '',
    }


def _render_member_form(prefill, mode='new', member=None):
    return render_template(
        'admin_member_new.html',
        nav_items=ADMIN_NAV_ITEMS,
        plans=get_all_plans(),
        gender_options=GENDER_OPTIONS,
        today_iso=date.today().isoformat(),
        prefill=prefill,
        active_tab='Members',
        mode=mode,
        member=member,
    )


def _read_member_form(form):
    """Snapshot the typed form values into the prefill dict the form template expects."""
    return {
        'username':  form.get('username', '').strip(),
        'name':      form.get('name', '').strip(),
        'mobile':    form.get('mobile', '').strip(),
        'age':       form.get('age', '').strip(),
        'gender':    form.get('gender', '').strip(),
        'join_date': form.get('join_date', '').strip(),
        'address':   form.get('address', '').strip(),
        'plan_id':   form.get('plan_id', '').strip(),
    }


def _validate_member_form(prefill):
    """Validate shared (non-credential) fields and resolve the chosen plan.

    Returns (parsed_dict, error_message). On success error_message is None.
    `parsed_dict` keys: name, mobile, age, gender, join_date, address, plan_id,
    plan_expire_date.
    """
    if not prefill['name'] or len(prefill['name']) < 2 or len(prefill['name']) > 100:
        return None, 'Full name is required (2-100 characters).'

    mobile = prefill['mobile']
    if not mobile or not is_valid_indian_mobile(mobile):
        return None, 'Mobile number must be in the format +91XXXXXXXXXX (10 digits, starting 6-9).'

    age = None
    if prefill['age']:
        try:
            age = int(prefill['age'])
            if age < 5 or age > 120:
                raise ValueError()
        except ValueError:
            return None, 'Age must be a whole number between 5 and 120.'

    gender = prefill['gender'] or None
    if gender and gender not in GENDER_OPTIONS:
        return None, 'Gender selection is invalid.'

    if not prefill['join_date']:
        return None, 'Join date is required.'
    try:
        date.fromisoformat(prefill['join_date'])
    except ValueError:
        return None, 'Join date must be a valid date (YYYY-MM-DD).'
    join_date = prefill['join_date']

    address = prefill['address'] or None
    if address and len(address) > 500:
        return None, 'Address is too long (max 500 characters).'

    if not prefill['plan_id']:
        return None, 'Membership plan is required.'
    try:
        plan_id = int(prefill['plan_id'])
    except ValueError:
        return None, 'Selected plan is invalid.'
    plan = get_plan_by_id(plan_id)
    if not plan:
        return None, 'Selected plan no longer exists. Please pick a current plan.'

    return {
        'name':             prefill['name'],
        'mobile':           mobile,
        'age':              age,
        'gender':           gender,
        'join_date':        join_date,
        'address':          address,
        'plan_id':          plan_id,
        'plan_expire_date': _add_duration(join_date, plan['duration_months'], plan['duration_days']),
    }, None


@app.route('/admin/members/new', methods=['GET', 'POST'])
@admin_required
def admin_members_new():
    if request.method == 'GET':
        return _render_member_form(_empty_member_prefill())

    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    prefill = _read_member_form(request.form)
    password = request.form.get('password', '')

    if not prefill['username'] or not is_valid_username(prefill['username']):
        flash('Username is required (4-50 characters, no spaces).', 'error')
        return _render_member_form(prefill)
    email = normalize_username_to_email(prefill['username'])
    if not is_valid_email(email) or len(email) > 150:
        flash('Username must form a valid email after appending the default domain.', 'error')
        return _render_member_form(prefill)

    if not password or len(password) < 6 or len(password) > 200:
        flash('Password is required (6-200 characters).', 'error')
        return _render_member_form(prefill)

    parsed, err = _validate_member_form(prefill)
    if err:
        flash(err, 'error')
        return _render_member_form(prefill)

    raw_username = prefill['username'].lower()
    username_for_db = raw_username if '@' not in raw_username else email

    try:
        create_member(
            name=parsed['name'], email=email,
            password_hash=generate_password_hash(password),
            username=username_for_db,
            mobile=parsed['mobile'], age=parsed['age'],
            gender=parsed['gender'], join_date=parsed['join_date'],
            address=parsed['address'], plan_id=parsed['plan_id'],
            plan_expire_date=parsed['plan_expire_date'],
        )
        flash(f"Member \"{parsed['name']}\" created. Login: {email}", 'success')
        return redirect(url_for('admin_members'))
    except sqlite3.IntegrityError:
        flash('That username is already taken. Pick a different one.', 'error')
        return _render_member_form(prefill)
    except sqlite3.Error:
        app.logger.exception('Member create failed')
        flash('Action failed. Please try again.', 'error')
        return _render_member_form(prefill)


def _load_editable_member(member_id):
    """Return a non-admin member by id, or None — flashing the right message and
    pushing the redirect target onto the caller is left to the route."""
    member = get_member_by_id(member_id)
    if not member or member['role'] != 'user':
        return None
    return member


@app.route('/admin/members/<int:member_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_members_edit(member_id):
    member = _load_editable_member(member_id)
    if not member:
        flash('Member not found.', 'error')
        return redirect(url_for('admin_members'))

    if request.method == 'GET':
        return _render_member_form(_prefill_from_member(member), mode='edit', member=member)

    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    prefill = _read_member_form(request.form)
    # Username and email are immutable from this form — keep the originals.
    prefill['username'] = member['email']

    parsed, err = _validate_member_form(prefill)
    if err:
        flash(err, 'error')
        return _render_member_form(prefill, mode='edit', member=member)

    try:
        update_member(
            member_id=member['id'],
            name=parsed['name'], mobile=parsed['mobile'], age=parsed['age'],
            gender=parsed['gender'], join_date=parsed['join_date'],
            address=parsed['address'], plan_id=parsed['plan_id'],
            plan_expire_date=parsed['plan_expire_date'],
            trainer_id=member['trainer_id'],
        )
        flash(f"Member \"{parsed['name']}\" updated.", 'success')
        return redirect(url_for('admin_members'))
    except sqlite3.Error:
        app.logger.exception('Member update failed')
        flash('Action failed. Please try again.', 'error')
        return _render_member_form(prefill, mode='edit', member=member)


@app.route('/admin/members/<int:member_id>/delete', methods=['POST'])
@admin_required
def admin_members_delete(member_id):
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    member = _load_editable_member(member_id)
    if not member:
        flash('Member not found.', 'error')
        return redirect(url_for('admin_members'))

    try:
        rowcount = delete_member(member['id'])
        if rowcount == 0:
            app.logger.warning(
                'Member delete affected 0 rows: id=%s name=%r', member['id'], member['name'],
            )
            flash('Action failed. The member may have already been removed.', 'error')
        else:
            app.logger.info(
                'Member deleted: id=%s name=%r email=%r by_admin=%s',
                member['id'], member['name'], member['email'], session.get('user_id'),
            )
            flash(f"Deleted {member['name']}.", 'success')
    except sqlite3.Error:
        app.logger.exception('Member delete failed: id=%s', member['id'])
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('admin_members'))


# ---------- Payments ----------
def _empty_payment_prefill():
    return {
        'member_id': '', 'plan_id': '', 'amount': '',
        'paid_on': '', 'method': 'cash', 'status': 'paid', 'notes': '',
    }


def _prefill_from_payment(payment):
    return {
        'member_id': str(payment['member_id']) if payment['member_id'] else '',
        'plan_id':   str(payment['plan_id']) if payment['plan_id'] else '',
        'amount':    f"{payment['amount']:.2f}" if payment['amount'] is not None else '',
        'paid_on':   payment['paid_on'] or '',
        'method':    payment['method'] or 'cash',
        'status':    payment['status'] or 'paid',
        'notes':     payment['notes'] or '',
    }


def _read_payment_form(form):
    return {
        'member_id': form.get('member_id', '').strip(),
        'plan_id':   form.get('plan_id', '').strip(),
        'amount':    form.get('amount', '').strip(),
        'paid_on':   form.get('paid_on', '').strip(),
        'method':    form.get('method', '').strip().lower(),
        'status':    form.get('status', '').strip().lower(),
        'notes':     form.get('notes', '').strip(),
    }


def _validate_payment_form(prefill):
    """Validate payment fields. Returns (parsed, error_message)."""
    if not prefill['member_id']:
        return None, 'Member is required.'
    try:
        member_id = int(prefill['member_id'])
    except ValueError:
        return None, 'Selected member is invalid.'
    member = get_member_by_id(member_id)
    if not member or member['role'] != 'user':
        return None, 'Selected member no longer exists.'

    plan_id = None
    if prefill['plan_id']:
        try:
            plan_id = int(prefill['plan_id'])
        except ValueError:
            return None, 'Selected plan is invalid.'
        if not get_plan_by_id(plan_id):
            return None, 'Selected plan no longer exists.'

    if not prefill['amount']:
        return None, 'Amount is required.'
    try:
        amount = float(prefill['amount'])
    except ValueError:
        return None, 'Amount must be a valid number.'
    if amount <= 0 or amount > 10_000_000:
        return None, 'Amount must be greater than 0 and at most 10,000,000.'
    amount = round(amount, 2)

    if not prefill['paid_on']:
        return None, 'Payment date is required.'
    try:
        date.fromisoformat(prefill['paid_on'])
    except ValueError:
        return None, 'Payment date must be a valid date (YYYY-MM-DD).'

    if prefill['method'] not in PAYMENT_METHODS:
        return None, 'Payment mode must be Cash, UPI, Card, or Online.'

    if prefill['status'] not in PAYMENT_STATUSES:
        return None, 'Payment status must be Paid or Pending.'

    notes = prefill['notes'] or None
    if notes and len(notes) > 500:
        return None, 'Notes are too long (max 500 characters).'

    return {
        'member_id': member_id,
        'plan_id':   plan_id,
        'amount':    amount,
        'paid_on':   prefill['paid_on'],
        'method':    prefill['method'],
        'status':    prefill['status'],
        'notes':     notes,
    }, None


def _render_payment_form(prefill, mode='new', payment=None):
    return render_template(
        'admin_payment_form.html',
        nav_items=ADMIN_NAV_ITEMS,
        members=get_all_members(role='user'),
        plans=get_all_plans(),
        payment_methods=PAYMENT_METHODS,
        payment_statuses=PAYMENT_STATUSES,
        prefill=prefill,
        active_tab='Payments',
        mode=mode,
        payment=payment,
    )


@app.route('/admin/payments')
@admin_required
def admin_payments():
    return render_template(
        'admin_payments.html',
        nav_items=ADMIN_NAV_ITEMS,
        payments=get_all_payments(),
        payment_statuses=PAYMENT_STATUSES,
        active_tab='Payments',
    )


@app.route('/admin/payments/new', methods=['GET', 'POST'])
@admin_required
def admin_payments_new():
    if request.method == 'GET':
        return _render_payment_form(_empty_payment_prefill())

    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    prefill = _read_payment_form(request.form)
    parsed, err = _validate_payment_form(prefill)
    if err:
        flash(err, 'error')
        return _render_payment_form(prefill)

    try:
        payment_id = create_payment(
            member_id=parsed['member_id'], plan_id=parsed['plan_id'],
            amount=parsed['amount'], paid_on=parsed['paid_on'],
            method=parsed['method'], status=parsed['status'],
            notes=parsed['notes'],
        )
        member = get_member_by_id(parsed['member_id'])
        app.logger.info(
            'Payment created: id=%s member=%r amount=%s status=%s by_admin=%s',
            payment_id, member['name'] if member else '?', parsed['amount'],
            parsed['status'], session.get('user_id'),
        )
        flash(f"Payment recorded for {member['name'] if member else 'member'}.", 'success')
        return redirect(url_for('admin_payments'))
    except sqlite3.Error:
        app.logger.exception('Payment create failed')
        flash('Action failed. Please try again.', 'error')
        return _render_payment_form(prefill)


@app.route('/admin/payments/<int:payment_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_payments_edit(payment_id):
    payment = get_payment_by_id(payment_id)
    if not payment:
        flash('Payment not found.', 'error')
        return redirect(url_for('admin_payments'))

    if request.method == 'GET':
        return _render_payment_form(_prefill_from_payment(payment), mode='edit', payment=payment)

    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    prefill = _read_payment_form(request.form)
    parsed, err = _validate_payment_form(prefill)
    if err:
        flash(err, 'error')
        return _render_payment_form(prefill, mode='edit', payment=payment)

    try:
        rowcount = update_payment(
            payment_id=payment['id'],
            member_id=parsed['member_id'], plan_id=parsed['plan_id'],
            amount=parsed['amount'], paid_on=parsed['paid_on'],
            method=parsed['method'], status=parsed['status'],
            notes=parsed['notes'],
        )
        if rowcount == 0:
            app.logger.warning('Payment update affected 0 rows: id=%s', payment['id'])
            flash('Action failed. The payment may have been removed.', 'error')
        else:
            app.logger.info(
                'Payment updated: id=%s amount=%s status=%s by_admin=%s',
                payment['id'], parsed['amount'], parsed['status'], session.get('user_id'),
            )
            flash(f"Payment #{payment['id']} updated.", 'success')
        return redirect(url_for('admin_payments'))
    except sqlite3.Error:
        app.logger.exception('Payment update failed: id=%s', payment['id'])
        flash('Action failed. Please try again.', 'error')
        return _render_payment_form(prefill, mode='edit', payment=payment)


@app.route('/admin/payments/<int:payment_id>/delete', methods=['POST'])
@admin_required
def admin_payments_delete(payment_id):
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    payment = get_payment_by_id(payment_id)
    if not payment:
        flash('Payment not found.', 'error')
        return redirect(url_for('admin_payments'))

    try:
        rowcount = delete_payment(payment['id'])
        if rowcount == 0:
            app.logger.warning('Payment delete affected 0 rows: id=%s', payment['id'])
            flash('Action failed. The payment may have already been removed.', 'error')
        else:
            app.logger.info(
                'Payment deleted: id=%s member=%r amount=%s by_admin=%s',
                payment['id'], payment['member_name'], payment['amount'],
                session.get('user_id'),
            )
            flash(f"Deleted payment #{payment['id']}.", 'success')
    except sqlite3.Error:
        app.logger.exception('Payment delete failed: id=%s', payment['id'])
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('admin_payments'))


# ---------- Member self-service ----------
def _empty_self_prefill(member):
    return {
        'mobile':  member['mobile'] or '+91',
        'age':     str(member['age']) if member['age'] is not None else '',
        'gender':  member['gender'] or '',
        'address': member['address'] or '',
    }


def _read_self_form(form):
    return {
        'mobile':  form.get('mobile', '').strip(),
        'age':     form.get('age', '').strip(),
        'gender':  form.get('gender', '').strip(),
        'address': form.get('address', '').strip(),
    }


def _validate_self_form(prefill):
    """Returns (parsed_dict, error_message). On success error_message is None."""
    if not prefill['mobile'] or not is_valid_indian_mobile(prefill['mobile']):
        return None, 'Mobile number must be in the format +91XXXXXXXXXX (10 digits, starting 6-9).'

    age = None
    if prefill['age']:
        try:
            age = int(prefill['age'])
            if age < 5 or age > 120:
                raise ValueError()
        except ValueError:
            return None, 'Age must be a whole number between 5 and 120.'

    gender = prefill['gender'] or None
    if gender and gender not in GENDER_OPTIONS:
        return None, 'Gender selection is invalid.'

    address = prefill['address'] or None
    if address and len(address) > 500:
        return None, 'Address is too long (max 500 characters).'

    return {
        'mobile':  prefill['mobile'],
        'age':     age,
        'gender':  gender,
        'address': address,
    }, None


def _render_member_profile(member, prefill):
    payments = get_all_payments(member_id=member['id'])
    total_paid = sum(p['amount'] for p in payments if p['status'] == 'paid')
    plan_fee = member['plan_fee']
    if member['plan_id'] and plan_fee is not None:
        remaining = max(0.0, float(plan_fee) - float(total_paid))
    else:
        remaining = None
    status_meta = _membership_status(member['plan_expire_date'])
    return render_template(
        'member_profile.html',
        member=member,
        payments_recent=payments[:5],
        total_paid=total_paid,
        remaining=remaining,
        plan_fee=plan_fee,
        status_meta=status_meta,
        gender_options=GENDER_OPTIONS,
        prefill=prefill,
    )


@app.route('/member/profile', methods=['GET', 'POST'])
@member_required
def member_profile():
    member = get_member_by_id(session['user_id'])
    if not member:
        session.clear()
        flash('Your session is no longer valid. Please log in again.', 'error')
        return redirect(url_for('login'))

    if request.method == 'GET':
        return _render_member_profile(member, _empty_self_prefill(member))

    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    prefill = _read_self_form(request.form)
    parsed, err = _validate_self_form(prefill)
    if err:
        flash(err, 'error')
        return _render_member_profile(member, prefill)

    try:
        update_member_self(
            member_id=session['user_id'],
            mobile=parsed['mobile'],
            age=parsed['age'],
            gender=parsed['gender'],
            address=parsed['address'],
        )
        flash('Profile updated.', 'success')
        return redirect(url_for('member_profile'))
    except sqlite3.Error:
        app.logger.exception('Member self-update failed: id=%s', session['user_id'])
        flash('Action failed. Please try again.', 'error')
        return _render_member_profile(member, prefill)


@app.route('/member/profile/password', methods=['POST'])
@member_required
def member_profile_password():
    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    old_password     = request.form.get('old_password', '')
    new_password     = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not old_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('member_profile'))
    if len(new_password) < 6 or len(new_password) > 200:
        flash('New password must be between 6 and 200 characters.', 'error')
        return redirect(url_for('member_profile'))
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('member_profile'))

    member = get_member_by_id(session['user_id'])
    if not member:
        session.clear()
        flash('Your session is no longer valid. Please log in again.', 'error')
        return redirect(url_for('login'))

    auth_row = get_member_by_email(member['email'])
    if not auth_row or not check_password_hash(auth_row['password_hash'], old_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('member_profile'))

    try:
        update_member_password(session['user_id'], generate_password_hash(new_password))
        app.logger.info('Member password changed: id=%s', session['user_id'])
        flash('Password updated.', 'success')
    except sqlite3.Error:
        app.logger.exception('Member password update failed: id=%s', session['user_id'])
        flash('Action failed. Please try again.', 'error')
    return redirect(url_for('member_profile'))


@app.route('/member/dashboard')
@member_required
def member_dashboard():
    return redirect(url_for('member_profile'))


@app.route('/enquiry', methods=['POST'])
def enquiry():
    if not _valid_csrf(request.form.get('csrf_token')):
        flash('Session expired. Please try again.', 'error')
        return redirect(url_for('index', _anchor='contact'))

    if _rate_limited(_ENQUIRY_BUCKETS, _client_ip(), _ENQUIRY_LIMIT):
        flash('Too many submissions. Please wait a moment and try again.', 'error')
        return redirect(url_for('index', _anchor='contact'))

    name    = request.form.get('name', '').strip()
    email   = request.form.get('email', '').strip()
    mobile  = request.form.get('mobile', '').strip()
    message = request.form.get('message', '').strip()

    if not name or not message:
        flash('Name and message are required.', 'error')
        return redirect(url_for('index', _anchor='contact'))
    if len(name) > 100 or len(email) > 150 or len(mobile) > 20 or len(message) > 1000:
        flash('Input exceeds maximum length.', 'error')
        return redirect(url_for('index', _anchor='contact'))
    if email and not is_valid_email(email):
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('index', _anchor='contact'))
    if mobile and not is_valid_mobile(mobile):
        flash('Please enter a valid mobile number.', 'error')
        return redirect(url_for('index', _anchor='contact'))

    try:
        create_enquiry(name, email, mobile, message)
        flash('Thank you! We will get back to you soon.', 'success')
    except sqlite3.Error:
        app.logger.exception('Enquiry insert failed')
        flash('Failed to submit. Please try again.', 'error')
    return redirect(url_for('index', _anchor='contact'))


# ---------- Error handlers ----------
@app.errorhandler(403)
def forbidden(_):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(_):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
    app.logger.exception('Unhandled server error: %s', e)
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    init_db()
    if os.environ.get('SEED_DB', '1') == '1':
        seed_db()
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, port=5001)
