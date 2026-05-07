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
        ''')
        if not _column_exists(conn, 'members', 'role'):
            conn.execute("ALTER TABLE members ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        conn.commit()
    finally:
        conn.close()


def seed_db():
    admin_password = os.environ.get('SEED_ADMIN_PASSWORD', '123456')
    member_password = os.environ.get('SEED_MEMBER_PASSWORD', '123456')
    seeds = [
        {'name': 'lakhan', 'email': 'lakhan@admin.com',  'password': admin_password,  'role': 'admin'},
        {'name': 'ansh',   'email': 'ansh@member.com',   'password': member_password, 'role': 'user'},
    ]
    conn = get_db()
    try:
        for seed in seeds:
            email = seed['email'].lower()
            existing = conn.execute(
                'SELECT id, role FROM members WHERE email = ?', (email,)
            ).fetchone()
            if not existing:
                conn.execute(
                    'INSERT INTO members (name, email, password_hash, role) VALUES (:name, :email, :password_hash, :role)',
                    {
                        'name': seed['name'],
                        'email': email,
                        'password_hash': generate_password_hash(seed['password']),
                        'role': seed['role'],
                    }
                )

        plan_seeds = [
            {'name': 'Monthly', 'duration_months': 1,  'fee': 1200.00},
        ]
        for plan in plan_seeds:
            existing = conn.execute(
                'SELECT id FROM membership_plans WHERE name = ?', (plan['name'],)
            ).fetchone()
            if not existing:
                conn.execute(
                    'INSERT INTO membership_plans (name, duration_months, fee) VALUES (?, ?, ?)',
                    (plan['name'], plan['duration_months'], plan['fee'])
                )
        conn.commit()
    finally:
        conn.close()


def get_member_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT id, name, email, role, created_at FROM members WHERE id = ?', (user_id,)
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


def get_all_members():
    conn = get_db()
    try:
        return conn.execute(
            'SELECT id, name, email, role, created_at FROM members ORDER BY created_at DESC'
        ).fetchall()
    finally:
        conn.close()


def count_members_registered_today():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM members WHERE date(created_at) = date('now', 'localtime')"
        ).fetchone()
        return row['c'] if row else 0
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
    conn = get_db()
    try:
        conn.execute('DELETE FROM members WHERE id = ?', (user_id,))
        conn.commit()
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


def get_all_plans():
    conn = get_db()
    try:
        return conn.execute(
            'SELECT id, name, duration_months, fee, created_at FROM membership_plans ORDER BY duration_months ASC, id ASC'
        ).fetchall()
    finally:
        conn.close()


def get_plan_by_id(plan_id):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT id, name, duration_months, fee, created_at FROM membership_plans WHERE id = ?',
            (plan_id,)
        ).fetchone()
    finally:
        conn.close()


def create_plan(name, duration_months, fee):
    conn = get_db()
    try:
        cur = conn.execute(
            'INSERT INTO membership_plans (name, duration_months, fee) VALUES (?, ?, ?)',
            (name, duration_months, fee)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_plan(plan_id, name, duration_months, fee):
    conn = get_db()
    try:
        conn.execute(
            'UPDATE membership_plans SET name = ?, duration_months = ?, fee = ? WHERE id = ?',
            (name, duration_months, fee, plan_id)
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


_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_MOBILE_RE = re.compile(r'^[\d\s+()\-]{7,20}$')


def is_valid_email(value):
    return bool(_EMAIL_RE.match(value))


def is_valid_mobile(value):
    return bool(_MOBILE_RE.match(value))
