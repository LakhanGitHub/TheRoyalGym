import os
import re
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'gym.db'))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _column_exists(conn, table, column):
    rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return any(row['name'] == column for row in rows)


def init_db():
    conn = get_db()
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS enquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                mobile TEXT,
                message TEXT NOT NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS membership_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                duration_months INTEGER NOT NULL,
                fee REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_plans_name
                ON membership_plans(name);

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
                plan_id   INTEGER REFERENCES membership_plans(id) ON DELETE SET NULL,
                amount    REAL NOT NULL,
                paid_on   TEXT NOT NULL,
                method    TEXT NOT NULL,
                status    TEXT NOT NULL DEFAULT 'paid',
                notes     TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_payments_member_id ON payments(member_id);
            CREATE INDEX IF NOT EXISTS idx_payments_paid_on   ON payments(paid_on);
        ''')
        if not _column_exists(conn, 'membership_plans', 'duration_days'):
            conn.execute('ALTER TABLE membership_plans ADD COLUMN duration_days INTEGER NOT NULL DEFAULT 0')
        if not _column_exists(conn, 'members', 'role'):
            conn.execute("ALTER TABLE members ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

        for col, ddl in (
            ('username',         'ALTER TABLE members ADD COLUMN username TEXT'),
            ('mobile',           'ALTER TABLE members ADD COLUMN mobile TEXT'),
            ('age',              'ALTER TABLE members ADD COLUMN age INTEGER'),
            ('gender',           'ALTER TABLE members ADD COLUMN gender TEXT'),
            ('address',          'ALTER TABLE members ADD COLUMN address TEXT'),
            ('join_date',        'ALTER TABLE members ADD COLUMN join_date TEXT'),
            ('plan_id',          'ALTER TABLE members ADD COLUMN plan_id INTEGER REFERENCES membership_plans(id) ON DELETE SET NULL'),
            ('plan_expire_date', 'ALTER TABLE members ADD COLUMN plan_expire_date TEXT'),
            ('trainer_id',       'ALTER TABLE members ADD COLUMN trainer_id INTEGER'),
        ):
            if not _column_exists(conn, 'members', col):
                conn.execute(ddl)

        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_members_username '
            'ON members(username) WHERE username IS NOT NULL'
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """First-run bootstrap data. Only inserts seeds when the corresponding
    table is empty so admin-initiated deletions can never be reversed by a
    server restart.
    """
    admin_password = os.environ.get('SEED_ADMIN_PASSWORD', '123456')
    member_password = os.environ.get('SEED_MEMBER_PASSWORD', '123456')
    user_seeds = [
        {'name': 'lakhan', 'email': 'lakhan@admin.com',  'password': admin_password,  'role': 'admin'},
        {'name': 'ansh',   'email': 'ansh@member.com',   'password': member_password, 'role': 'user'},
    ]
    plan_seeds = [
        {'name': 'Trial Plan', 'duration_months': 0, 'duration_days': 5, 'fee':  200.00},
        {'name': 'Monthly',    'duration_months': 1, 'duration_days': 0, 'fee': 1200.00},
    ]

    conn = get_db()
    try:
        member_count = conn.execute('SELECT COUNT(*) AS c FROM members').fetchone()['c']
        if member_count == 0:
            for seed in user_seeds:
                conn.execute(
                    'INSERT INTO members (name, email, password_hash, role) '
                    'VALUES (:name, :email, :password_hash, :role)',
                    {
                        'name': seed['name'],
                        'email': seed['email'].lower(),
                        'password_hash': generate_password_hash(seed['password']),
                        'role': seed['role'],
                    }
                )

        plan_count = conn.execute('SELECT COUNT(*) AS c FROM membership_plans').fetchone()['c']
        if plan_count == 0:
            for plan in plan_seeds:
                conn.execute(
                    'INSERT INTO membership_plans (name, duration_months, duration_days, fee) '
                    'VALUES (?, ?, ?, ?)',
                    (plan['name'], plan['duration_months'], plan['duration_days'], plan['fee'])
                )
        conn.commit()
    finally:
        conn.close()


_MEMBER_COLUMNS = (
    'm.id, m.name, m.email, m.username, m.mobile, m.age, m.gender, '
    'm.address, m.join_date, m.plan_id, m.plan_expire_date, m.trainer_id, '
    'm.role, m.created_at, '
    'p.name AS plan_name, p.duration_months AS plan_duration, '
    'p.duration_days AS plan_duration_days, p.fee AS plan_fee'
)


def get_member_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            f'SELECT {_MEMBER_COLUMNS} FROM members m '
            'LEFT JOIN membership_plans p ON p.id = m.plan_id '
            'WHERE m.id = ?',
            (user_id,)
        ).fetchone()
    finally:
        conn.close()


def get_member_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT id, name, email, password_hash, role, created_at FROM members WHERE email = ?',
            (email.lower(),)
        ).fetchone()
    finally:
        conn.close()


def get_member_by_login(value):
    """Look up a member by either email or username (case-insensitive)."""
    conn = get_db()
    try:
        v = value.strip().lower()
        return conn.execute(
            'SELECT id, name, email, password_hash, role, created_at '
            'FROM members WHERE email = ? OR username = ? LIMIT 1',
            (v, v)
        ).fetchone()
    finally:
        conn.close()


def get_all_members(role=None):
    sql = (
        f'SELECT {_MEMBER_COLUMNS} FROM members m '
        'LEFT JOIN membership_plans p ON p.id = m.plan_id'
    )
    params = ()
    if role is not None:
        sql += ' WHERE m.role = ?'
        params = (role,)
    sql += ' ORDER BY m.created_at DESC'

    conn = get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def create_member(name, email, password_hash, username, mobile, age,
                  gender, join_date, address, plan_id, plan_expire_date,
                  trainer_id=None):
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO members ('
            'name, email, password_hash, role, username, mobile, age, '
            'gender, address, join_date, plan_id, plan_expire_date, trainer_id'
            ') VALUES (?, ?, ?, "user", ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (name, email.lower(), password_hash,
             username.lower() if username else None,
             mobile, age, gender, address, join_date,
             plan_id, plan_expire_date, trainer_id)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_member(member_id, name, mobile, age, gender, join_date, address,
                  plan_id, plan_expire_date, trainer_id=None):
    conn = get_db()
    try:
        conn.execute(
            'UPDATE members SET name = ?, mobile = ?, age = ?, gender = ?, '
            'join_date = ?, address = ?, plan_id = ?, plan_expire_date = ?, '
            'trainer_id = ? WHERE id = ?',
            (name, mobile, age, gender, join_date, address,
             plan_id, plan_expire_date, trainer_id, member_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_member_self(member_id, mobile, age, gender, address):
    """Self-service update touching ONLY the four contact fields a member
    is allowed to change. Never modifies name, email, username, role,
    plan_id, plan_expire_date, join_date, trainer_id, or password_hash."""
    conn = get_db()
    try:
        conn.execute(
            'UPDATE members SET mobile = ?, age = ?, gender = ?, address = ? '
            'WHERE id = ?',
            (mobile, age, gender, address, member_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_dashboard_metrics():
    """Return a dict with the 6 admin-dashboard tile counts. All counts
    exclude members whose role is 'admin'. Uses SQLite's local-time
    `date('now', 'localtime')` so the values match what the admin sees in
    their own timezone.
    """
    sql = """
        SELECT
            SUM(CASE WHEN role <> 'admin' THEN 1 ELSE 0 END)
                AS total_members,
            SUM(CASE
                    WHEN role <> 'admin'
                     AND join_date IS NOT NULL
                     AND strftime('%Y-%m', join_date) = strftime('%Y-%m', 'now', 'localtime')
                    THEN 1 ELSE 0 END)
                AS month_registrations,
            SUM(CASE
                    WHEN role <> 'admin'
                     AND plan_expire_date IS NOT NULL
                     AND plan_expire_date >= date('now', 'localtime')
                    THEN 1 ELSE 0 END)
                AS active,
            SUM(CASE
                    WHEN role <> 'admin'
                     AND LOWER(gender) = 'male'
                    THEN 1 ELSE 0 END)
                AS men,
            SUM(CASE
                    WHEN role <> 'admin'
                     AND LOWER(gender) = 'female'
                    THEN 1 ELSE 0 END)
                AS women,
            SUM(CASE
                    WHEN role <> 'admin'
                     AND plan_expire_date IS NOT NULL
                     AND strftime('%Y-%m', plan_expire_date) = strftime('%Y-%m', 'now', 'localtime')
                    THEN 1 ELSE 0 END)
                AS expiring_this_month
        FROM members
    """
    conn = get_db()
    try:
        row = conn.execute(sql).fetchone()
        return {
            'total_members':       row['total_members']       or 0,
            'month_registrations': row['month_registrations'] or 0,
            'active':              row['active']              or 0,
            'men':                 row['men']                 or 0,
            'women':               row['women']               or 0,
            'expiring_this_month': row['expiring_this_month'] or 0,
        }
    finally:
        conn.close()


def get_all_enquiries():
    conn = get_db()
    try:
        return conn.execute(
            'SELECT id, name, email, mobile, message, submitted_at FROM enquiries ORDER BY submitted_at DESC'
        ).fetchall()
    finally:
        conn.close()


def create_enquiry(name, email, mobile, message):
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO enquiries (name, email, mobile, message) VALUES (?, ?, ?, ?)',
            (name, email, mobile, message)
        )
        conn.commit()
    finally:
        conn.close()


def update_member_role(user_id, new_role):
    if new_role not in ('admin', 'user'):
        raise ValueError(f'invalid role: {new_role!r}')
    conn = get_db()
    try:
        conn.execute('UPDATE members SET role = ? WHERE id = ?', (new_role, user_id))
        conn.commit()
    finally:
        conn.close()


def update_member_password(user_id, new_hash):
    conn = get_db()
    try:
        conn.execute('UPDATE members SET password_hash = ? WHERE id = ?', (new_hash, user_id))
        conn.commit()
    finally:
        conn.close()


def delete_member(user_id):
    """Returns the number of rows deleted (0 if the id no longer exists)."""
    conn = get_db()
    try:
        cur = conn.execute('DELETE FROM members WHERE id = ?', (user_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def count_admins():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM members WHERE role = 'admin'"
        ).fetchone()
        return row['c'] if row else 0
    finally:
        conn.close()


_PLAN_COLUMNS = 'id, name, duration_months, duration_days, fee, created_at'


def get_all_plans():
    conn = get_db()
    try:
        return conn.execute(
            f'SELECT {_PLAN_COLUMNS} FROM membership_plans '
            'ORDER BY duration_months ASC, duration_days ASC, id ASC'
        ).fetchall()
    finally:
        conn.close()


def get_plan_by_id(plan_id):
    conn = get_db()
    try:
        return conn.execute(
            f'SELECT {_PLAN_COLUMNS} FROM membership_plans WHERE id = ?',
            (plan_id,)
        ).fetchone()
    finally:
        conn.close()


def create_plan(name, duration_months, fee, duration_days=0):
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO membership_plans (name, duration_months, duration_days, fee) '
            'VALUES (?, ?, ?, ?)',
            (name, duration_months, duration_days, fee)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_plan(plan_id, name, duration_months, fee, duration_days=0):
    conn = get_db()
    try:
        conn.execute(
            'UPDATE membership_plans SET name = ?, duration_months = ?, '
            'duration_days = ?, fee = ? WHERE id = ?',
            (name, duration_months, duration_days, fee, plan_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_plan(plan_id):
    conn = get_db()
    try:
        conn.execute('DELETE FROM membership_plans WHERE id = ?', (plan_id,))
        conn.commit()
    finally:
        conn.close()


_PAYMENT_COLUMNS = (
    'p.id, p.member_id, p.plan_id, p.amount, p.paid_on, p.method, '
    'p.status, p.notes, p.created_at, '
    'm.name AS member_name, m.email AS member_email, '
    'm.join_date AS member_join_date, '
    'pl.name AS plan_name, pl.duration_months AS plan_duration, '
    'pl.duration_days AS plan_duration_days'
)


def get_all_payments(member_id=None):
    sql = (
        f'SELECT {_PAYMENT_COLUMNS} FROM payments p '
        'JOIN members m ON m.id = p.member_id '
        'LEFT JOIN membership_plans pl ON pl.id = p.plan_id'
    )
    params = ()
    if member_id is not None:
        sql += ' WHERE p.member_id = ?'
        params = (member_id,)
    sql += ' ORDER BY p.paid_on DESC, p.id DESC'

    conn = get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def get_payment_by_id(payment_id):
    conn = get_db()
    try:
        return conn.execute(
            f'SELECT {_PAYMENT_COLUMNS} FROM payments p '
            'JOIN members m ON m.id = p.member_id '
            'LEFT JOIN membership_plans pl ON pl.id = p.plan_id '
            'WHERE p.id = ?',
            (payment_id,)
        ).fetchone()
    finally:
        conn.close()


def create_payment(member_id, plan_id, amount, paid_on, method, status, notes):
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO payments '
            '(member_id, plan_id, amount, paid_on, method, status, notes) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (member_id, plan_id, amount, paid_on, method, status, notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_payment(payment_id, member_id, plan_id, amount, paid_on, method, status, notes):
    conn = get_db()
    try:
        cur = conn.execute(
            'UPDATE payments SET member_id = ?, plan_id = ?, amount = ?, '
            'paid_on = ?, method = ?, status = ?, notes = ? WHERE id = ?',
            (member_id, plan_id, amount, paid_on, method, status, notes, payment_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_payment(payment_id):
    """Returns the number of rows deleted (0 if the id no longer exists)."""
    conn = get_db()
    try:
        cur = conn.execute('DELETE FROM payments WHERE id = ?', (payment_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_MOBILE_RE = re.compile(r'^[\d\s+()\-]{7,20}$')
_INDIAN_MOBILE_RE = re.compile(r'^\+91[6-9]\d{9}$')
_USERNAME_RAW_RE = re.compile(r'^\S{4,50}$')

USERNAME_DEFAULT_DOMAIN = '@theroyalgym.com'


def is_valid_email(value):
    return bool(_EMAIL_RE.match(value or ''))


def is_valid_mobile(value):
    """Lenient mobile check used by the public enquiry form."""
    return bool(_MOBILE_RE.match(value or ''))


def is_valid_indian_mobile(value):
    """Strict +91 followed by a 10-digit Indian mobile (starts 6-9)."""
    return bool(_INDIAN_MOBILE_RE.match(value or ''))


def is_valid_username(value):
    """Admin-supplied username: 4-50 chars, no whitespace."""
    return bool(_USERNAME_RAW_RE.match(value or ''))


def normalize_username_to_email(value):
    """Lower-case the input and append USERNAME_DEFAULT_DOMAIN if no '@' is present."""
    s = (value or '').strip().lower()
    if not s:
        return ''
    if '@' not in s:
        s = f'{s}{USERNAME_DEFAULT_DOMAIN}'
    return s
