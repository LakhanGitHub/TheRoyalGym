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
    create_member,
    is_valid_email, is_valid_mobile, is_valid_username,
)

PLAN_DURATIONS = {'Monthly': 1, 'Quarterly': 3, 'Yearly': 12}
GENDER_OPTIONS = ('Male', 'Female', 'Other')


def _add_months(start_iso, months):
    """Add `months` to an ISO YYYY-MM-DD string; clamps to month-end (Jan 31 + 1 month -> Feb 28/29)."""
    start = date.fromisoformat(start_iso)
    total = (start.month - 1) + int(months)
    new_year = start.year + total // 12
    new_month = total % 12 + 1
    last_day = calendar.monthrange(new_year, new_month)[1]
    new_day = min(start.day, last_day)
    return date(new_year, new_month, new_day).isoformat()


ADMIN_NAV_ITEMS = [
    {'label': 'Members',       'endpoint': 'admin_members',  'desc': 'Add, edit and search members.',         'color': 'cyan'},
    {'label': 'Plans',         'endpoint': 'admin_plans',    'desc': 'Membership plans and pricing.',         'color': 'pink'},
    {'label': 'Trainers',      'endpoint': None,             'desc': 'Roster, schedules and payouts.',        'color': 'purple'},
    {'label': 'Payments',      'endpoint': None,             'desc': 'Paid and pending invoices.',            'color': 'orange'},
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
    return url_for('admin_dashboard') if role == 'admin' else url_for('member_dashboard')


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
        delete_member(user_id)
        flash(f"Deleted {target['name']}.", 'success')
    except sqlite3.Error:
        app.logger.exception('Delete failed')
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
    """Validate name + fee from request.form. Returns (name, duration_months, fee, error)."""
    name = request.form.get('name', '').strip()
    fee_raw = request.form.get('fee', '').strip()

    if name not in PLAN_DURATIONS:
        return None, None, None, 'Plan name must be Monthly, Quarterly, or Yearly.'

    try:
        fee = float(fee_raw)
    except ValueError:
        return None, None, None, 'Fee must be a valid number.'
    if fee < 0 or fee > 1_000_000:
        return None, None, None, 'Fee must be between 0 and 1,000,000.'

    return name, PLAN_DURATIONS[name], fee, None


@app.route('/admin/plans/new', methods=['GET', 'POST'])
@admin_required
def admin_plans_new():
    prefill = {'name': request.form.get('name', ''), 'fee': request.form.get('fee', '')}

    if request.method == 'POST':
        if not _valid_csrf(request.form.get('csrf_token')):
            abort(403)

        name, duration_months, fee, err = _parse_plan_form()
        if err:
            flash(err, 'error')
            return render_template(
                'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
                active_tab='Plans', mode='new', plan=None, prefill=prefill,
                allowed_names=list(PLAN_DURATIONS.keys()),
            )

        try:
            create_plan(name, duration_months, fee)
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
        )

    return render_template(
        'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
        active_tab='Plans', mode='new', plan=None, prefill=prefill,
        allowed_names=list(PLAN_DURATIONS.keys()),
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

        name, duration_months, fee, err = _parse_plan_form()
        if err:
            flash(err, 'error')
            return render_template(
                'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
                active_tab='Plans', mode='edit', plan=plan, prefill=prefill,
                allowed_names=list(PLAN_DURATIONS.keys()),
            )

        try:
            update_plan(plan_id, name, duration_months, fee)
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
        )

    return render_template(
        'admin_plan_form.html', nav_items=ADMIN_NAV_ITEMS,
        active_tab='Plans', mode='edit', plan=plan, prefill=prefill,
        allowed_names=list(PLAN_DURATIONS.keys()),
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
    members = get_all_members(role='user')
    return render_template(
        'admin_members.html',
        nav_items=ADMIN_NAV_ITEMS,
        members=members,
        active_tab='Members',
    )


def _empty_member_prefill():
    return {
        'username': '', 'name': '', 'mobile': '', 'age': '',
        'gender': '', 'join_date': date.today().isoformat(),
        'address': '', 'plan_id': '',
    }


def _render_member_form(prefill, mode='new'):
    return render_template(
        'admin_member_new.html',
        nav_items=ADMIN_NAV_ITEMS,
        plans=get_all_plans(),
        gender_options=GENDER_OPTIONS,
        today_iso=date.today().isoformat(),
        prefill=prefill,
        active_tab='Members',
        mode=mode,
    )


@app.route('/admin/members/new', methods=['GET', 'POST'])
@admin_required
def admin_members_new():
    if request.method == 'GET':
        return _render_member_form(_empty_member_prefill())

    if not _valid_csrf(request.form.get('csrf_token')):
        abort(403)

    f = request.form
    prefill = {
        'username':  f.get('username', '').strip(),
        'name':      f.get('name', '').strip(),
        'mobile':    f.get('mobile', '').strip(),
        'age':       f.get('age', '').strip(),
        'gender':    f.get('gender', '').strip(),
        'join_date': f.get('join_date', '').strip(),
        'address':   f.get('address', '').strip(),
        'plan_id':   f.get('plan_id', '').strip(),
    }
    password = f.get('password', '')

    # Required fields
    if not prefill['username'] or not is_valid_username(prefill['username']):
        flash('Username is required (3-30 chars, letters/digits/underscore/hyphen).', 'error')
        return _render_member_form(prefill)
    if not password or len(password) < 6 or len(password) > 200:
        flash('Password is required (6-200 characters).', 'error')
        return _render_member_form(prefill)
    if not prefill['name'] or len(prefill['name']) < 2 or len(prefill['name']) > 100:
        flash('Full name is required (2-100 characters).', 'error')
        return _render_member_form(prefill)

    # Optional fields
    mobile = prefill['mobile'] or None
    if mobile and not is_valid_mobile(mobile):
        flash('Mobile number is invalid.', 'error')
        return _render_member_form(prefill)

    age = None
    if prefill['age']:
        try:
            age = int(prefill['age'])
            if age < 5 or age > 120:
                raise ValueError()
        except ValueError:
            flash('Age must be a whole number between 5 and 120.', 'error')
            return _render_member_form(prefill)

    gender = prefill['gender'] or None
    if gender and gender not in GENDER_OPTIONS:
        flash('Gender selection is invalid.', 'error')
        return _render_member_form(prefill)

    join_date = prefill['join_date'] or None
    if join_date:
        try:
            date.fromisoformat(join_date)
        except ValueError:
            flash('Join date is invalid.', 'error')
            return _render_member_form(prefill)

    address = prefill['address'] or None
    if address and len(address) > 500:
        flash('Address is too long (max 500 characters).', 'error')
        return _render_member_form(prefill)

    plan_id = None
    plan_expire_date = None
    if prefill['plan_id']:
        try:
            plan_id = int(prefill['plan_id'])
        except ValueError:
            flash('Selected plan is invalid.', 'error')
            return _render_member_form(prefill)
        plan = get_plan_by_id(plan_id)
        if not plan:
            flash('Selected plan no longer exists.', 'error')
            return _render_member_form(prefill)
        if join_date:
            plan_expire_date = _add_months(join_date, plan['duration_months'])

    synth_email = f"{prefill['username'].lower()}@member.local"
    try:
        create_member(
            name=prefill['name'],
            email=synth_email,
            password_hash=generate_password_hash(password),
            username=prefill['username'],
            mobile=mobile,
            age=age,
            gender=gender,
            join_date=join_date,
            address=address,
            plan_id=plan_id,
            plan_expire_date=plan_expire_date,
        )
        flash(f"Member \"{prefill['name']}\" created.", 'success')
        return redirect(url_for('admin_members'))
    except sqlite3.IntegrityError:
        flash('That username (or its synthesised email) is already taken. Try a different username.', 'error')
        return _render_member_form(prefill)
    except sqlite3.Error:
        app.logger.exception('Member create failed')
        flash('Action failed. Please try again.', 'error')
        return _render_member_form(prefill)


@app.route('/member/dashboard')
@member_required
def member_dashboard():
    member = get_member_by_id(session['user_id'])
    return render_template('member_dashboard.html', member=member)


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
