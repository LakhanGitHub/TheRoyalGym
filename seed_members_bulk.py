"""One-shot seeder: 100 realistic Ghaziabad-based Indian members spread across
the last 6 months, with mixed genders, varied membership plans, and realistic
join_date / created_at distribution.
"""
import random
from collections import Counter
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from database.db import (
    get_db,
    is_valid_indian_mobile,
    is_valid_username,
    USERNAME_DEFAULT_DOMAIN,
)

random.seed(20260509)

MALE_FIRST_NAMES = [
    'aarav', 'aditya', 'akash', 'akhil', 'amit', 'aniket', 'ankit', 'anuj',
    'arjun', 'arun', 'ashish', 'ayush', 'bharat', 'chetan', 'deepak', 'devang',
    'dhruv', 'gaurav', 'harsh', 'hemant', 'ishaan', 'jatin', 'kabir', 'karan',
    'kartik', 'kunal', 'lalit', 'manish', 'mayank', 'mohit', 'naveen', 'nikhil',
    'nitin', 'pankaj', 'parth', 'pawan', 'piyush', 'prateek', 'prem', 'pushkar',
    'rahul', 'rajat', 'rajeev', 'rakesh', 'ravi', 'rishabh', 'rohan', 'sachin',
    'sahil', 'sameer', 'sandeep', 'sanjay', 'saurabh', 'shashank', 'shivam',
    'shubham', 'siddharth', 'sumit', 'suraj', 'tanmay', 'tarun', 'tushar',
    'umesh', 'utkarsh', 'varun', 'veer', 'vikas', 'vikram', 'vinay', 'vishal',
    'yash', 'yogesh', 'aaditya', 'rohit', 'salman', 'imran', 'faisal', 'zaid',
    'arvind', 'jaideep', 'manoj', 'naman', 'om',
]

FEMALE_FIRST_NAMES = [
    'aanya', 'aarti', 'aditi', 'akanksha', 'alka', 'ananya', 'anita', 'anjali',
    'anushka', 'archana', 'arpita', 'asha', 'bhavna', 'chanda', 'deepika',
    'divya', 'ekta', 'gauri', 'geeta', 'harshita', 'isha', 'jaya', 'jyoti',
    'kajal', 'kavita', 'khushi', 'kiran', 'komal', 'lata', 'madhu', 'mansi',
    'meena', 'megha', 'mona', 'naina', 'neelam', 'neha', 'nikita', 'nisha',
    'pooja', 'pragya', 'preeti', 'priya', 'priyanka', 'radhika', 'rashmi',
    'reena', 'rekha', 'richa', 'ridhima', 'ritu', 'ruchi', 'sakshi', 'sanya',
    'sapna', 'shalini', 'shilpa', 'shivani', 'shreya', 'simran', 'smita',
    'sneha', 'sonal', 'sonam', 'sonia', 'suman', 'sunita', 'swati', 'tanvi',
    'tara', 'tina', 'usha', 'vandana', 'varsha', 'vidya', 'vinita', 'yamini',
]

LAST_NAMES = [
    'sharma', 'verma', 'singh', 'kumar', 'gupta', 'agarwal', 'mishra', 'tiwari',
    'pandey', 'chauhan', 'yadav', 'rana', 'rawat', 'negi', 'bisht', 'joshi',
    'bhatt', 'kapoor', 'malhotra', 'khanna', 'arora', 'chopra', 'bansal',
    'goel', 'jain', 'mittal', 'aggarwal', 'tyagi', 'tomar', 'choudhary',
    'rathore', 'shukla', 'srivastava', 'saxena', 'dixit', 'pant', 'rastogi',
    'goswami', 'bhardwaj', 'thakur', 'sengupta', 'das', 'nair', 'menon',
    'pillai', 'iyer', 'reddy', 'rao', 'naidu', 'hussain', 'khan', 'ali',
    'ansari', 'siddiqui', 'qureshi',
]

GHAZIABAD_LOCALITIES = [
    'Sector 12, Pratapvihar', 'Vasundhara Sector 9', 'Indirapuram, Niti Khand 1',
    'Indirapuram, Shakti Khand 2', 'Kaushambi', 'Vaishali Sector 4',
    'Vaishali Sector 6', 'Raj Nagar Extension', 'Crossings Republik',
    'Govindpuram', 'Kavi Nagar', 'Shastri Nagar', 'Lohia Nagar',
    'Nehru Nagar', 'Shalimar Garden', 'Sahibabad', 'Ramprastha',
    'Mohan Nagar', 'Chiranjiv Vihar', 'Surya Nagar', 'Patel Nagar',
    'Modinagar', 'Tila More', 'Hapur Road', 'Meerut Road',
]


def random_mobile():
    first = random.choice(['6', '7', '8', '9'])
    rest = ''.join(random.choices('0123456789', k=9))
    return f'+91{first}{rest}'


def random_address():
    locality = random.choice(GHAZIABAD_LOCALITIES)
    house_no = random.randint(1, 350)
    return f'{house_no}, {locality}, Ghaziabad'


def add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    # clamp day to last day of target month
    if month == 2:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    day = min(d.day, last)
    return date(year, month, day)


def compute_expiry(join_date_str, plan_months, plan_days):
    jd = datetime.strptime(join_date_str, '%Y-%m-%d').date()
    expiry = add_months(jd, plan_months) + timedelta(days=plan_days)
    return expiry.strftime('%Y-%m-%d')


def random_join_date(today):
    """Pick a date roughly uniformly over the last 6 calendar months."""
    six_months_ago = add_months(today, -6) + timedelta(days=1)
    span_days = (today - six_months_ago).days
    offset = random.randint(0, span_days)
    return six_months_ago + timedelta(days=offset)


def random_created_at_for(join_date_str):
    """Return an ISO timestamp on the same calendar day as join_date with a
    random time-of-day (so registered-today / monthly stats look natural)."""
    jd = datetime.strptime(join_date_str, '%Y-%m-%d').date()
    hour = random.randint(7, 21)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(jd.year, jd.month, jd.day, hour, minute, second).strftime('%Y-%m-%d %H:%M:%S')


def main():
    today = date.today()
    conn = get_db()
    try:
        plans = conn.execute(
            'SELECT id, name, duration_months, duration_days, fee FROM membership_plans'
        ).fetchall()
        if len(plans) < 3:
            wanted = [
                ('Trial Plan', 0, 5, 200.0),
                ('Monthly', 1, 0, 600.0),
                ('Quarterly', 3, 0, 1400.0),
                ('Half-Yearly', 6, 0, 2400.0),
                ('Yearly', 12, 0, 5400.0),
            ]
            existing_names = {p['name'] for p in plans}
            for name, dm, dd, fee in wanted:
                if name not in existing_names:
                    conn.execute(
                        'INSERT INTO membership_plans (name, duration_months, duration_days, fee) '
                        'VALUES (?, ?, ?, ?)',
                        (name, dm, dd, fee),
                    )
            conn.commit()
            plans = conn.execute(
                'SELECT id, name, duration_months, duration_days, fee FROM membership_plans'
            ).fetchall()

        plan_by_name = {p['name']: p for p in plans}

        # Skewed weights: Monthly/Quarterly common, Trial/Yearly rare.
        plan_weights_template = {
            'Trial Plan': 1,
            'Monthly': 5,
            'Quarterly': 4,
            'Half-Yearly': 2,
            'Yearly': 1,
        }
        weighted_plans = []
        weights = []
        for p in plans:
            w = plan_weights_template.get(p['name'], 2)
            weighted_plans.append(p)
            weights.append(w)

        existing = conn.execute(
            'SELECT email, username FROM members'
        ).fetchall()
        used_emails = {r['email'].lower() for r in existing if r['email']}
        used_usernames = {r['username'].lower() for r in existing if r['username']}

        # Bucket join-dates by month so distribution is roughly even.
        bucket_starts = []
        for i in range(6, 0, -1):
            start = add_months(today, -i) + timedelta(days=1)
            end = add_months(today, -(i - 1))
            if end > today:
                end = today
            bucket_starts.append((start, end))
        # ~16-17 per bucket → 100 total
        per_bucket = [17, 17, 17, 17, 16, 16]

        target_total = 100
        target_female = 30  # ~30 of 100
        female_remaining = target_female
        male_remaining = target_total - target_female

        # Pre-allocate genders so the distribution is exact.
        gender_pool = ['female'] * female_remaining + ['male'] * male_remaining
        random.shuffle(gender_pool)

        # Pre-allocate join dates per bucket.
        join_dates = []
        for (start, end), n in zip(bucket_starts, per_bucket):
            span_days = (end - start).days
            for _ in range(n):
                offset = random.randint(0, max(0, span_days))
                join_dates.append(start + timedelta(days=offset))
        random.shuffle(join_dates)

        inserted = 0
        skipped = 0
        first_rows = []

        # Single transaction.
        try:
            for i in range(target_total):
                gender = gender_pool[i]
                first_pool = MALE_FIRST_NAMES if gender == 'male' else FEMALE_FIRST_NAMES
                first = random.choice(first_pool)
                last = random.choice(LAST_NAMES)
                full_name = f'{first} {last}'

                # Username generation with retry on collision.
                base = f'{first}{last}'.replace(' ', '').lower()
                username = None
                email = None
                for attempt in range(25):
                    if attempt == 0:
                        candidate = base
                    else:
                        candidate = f'{base}{random.randint(10, 999)}'
                    if not is_valid_username(candidate):
                        continue
                    if len(candidate) > 50:
                        continue
                    cand_email = f'{candidate}{USERNAME_DEFAULT_DOMAIN}'.lower()
                    if candidate in used_usernames or cand_email in used_emails:
                        continue
                    username = candidate
                    email = cand_email
                    break

                if username is None or email is None:
                    skipped += 1
                    print(f'  ! skipped {full_name}: could not produce unique username/email')
                    continue

                age = random.randint(18, 55)

                # Mobile: regenerate until valid (essentially always first try).
                mobile = random_mobile()
                while not is_valid_indian_mobile(mobile):
                    mobile = random_mobile()

                address = random_address()

                plan = random.choices(weighted_plans, weights=weights, k=1)[0]

                jd = join_dates[i]
                join_date_str = jd.strftime('%Y-%m-%d')
                expire_str = compute_expiry(
                    join_date_str, plan['duration_months'], plan['duration_days']
                )
                created_at = random_created_at_for(join_date_str)

                pwd_hash = generate_password_hash('123456')

                cur = conn.execute(
                    'INSERT INTO members ('
                    'name, email, password_hash, role, username, mobile, age, '
                    'gender, address, join_date, plan_id, plan_expire_date, '
                    'trainer_id, created_at'
                    ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (full_name, email, pwd_hash, 'user', username, mobile, age,
                     gender, address, join_date_str, plan['id'], expire_str,
                     None, created_at),
                )
                used_emails.add(email)
                used_usernames.add(username)
                inserted += 1

                if len(first_rows) < 5:
                    first_rows.append({
                        'id': cur.lastrowid,
                        'name': full_name,
                        'username': username,
                        'email': email,
                        'gender': gender,
                        'plan_name': plan['name'],
                        'join_date': join_date_str,
                        'plan_expire_date': expire_str,
                    })

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        # ---- Summary ----
        rows = conn.execute(
            'SELECT m.gender, m.join_date, p.name AS plan_name '
            'FROM members m LEFT JOIN membership_plans p ON p.id = m.plan_id '
            'WHERE m.id IN (SELECT id FROM members ORDER BY id DESC LIMIT ?)',
            (inserted,),
        ).fetchall()
        gender_ct = Counter(r['gender'] for r in rows)
        plan_ct = Counter(r['plan_name'] for r in rows)
        month_ct = Counter((r['join_date'] or '')[:7] for r in rows)

        print()
        print(f'Total members inserted: {inserted}')
        if skipped:
            print(f'Skipped due to collisions: {skipped}')
        print()
        print('By gender:')
        for g, c in sorted(gender_ct.items()):
            print(f'  {g}: {c}')
        print()
        print('By plan:')
        for name, c in sorted(plan_ct.items(), key=lambda kv: -kv[1]):
            print(f'  {name}: {c}')
        print()
        print('By join-month:')
        for m, c in sorted(month_ct.items()):
            print(f'  {m}: {c}')
        print()
        print('First 5 inserted rows:')
        for r in first_rows:
            print(
                f"  id={r['id']:<4} name={r['name']:<28} "
                f"username={r['username']:<22} email={r['email']:<40} "
                f"gender={r['gender']:<6} plan={r['plan_name']:<12} "
                f"join={r['join_date']} expire={r['plan_expire_date']}"
            )
    finally:
        conn.close()


if __name__ == '__main__':
    main()
