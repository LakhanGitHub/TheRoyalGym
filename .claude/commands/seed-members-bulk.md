---
description: Seed N realistic Indian members spread across the last M months with mixed genders and varied membership plans
allowed-tools: Read, Bash(python3:*), Bash(python:*), AskUserQuestion
argument-hint: [months] [members]
---

## 0. Collect inputs

The slash command may be invoked with arguments: `$ARGUMENTS`
(positional → `$1` = months, `$2` = members count).

- If `$1` (months) is missing or not a positive integer, use
  `AskUserQuestion` to ask:
  > "How many months of join-date history should the seed cover?"
  Offer options like `3`, `6`, `12`, plus an Other free-text option.
- If `$2` (members count) is missing or not a positive integer, use
  `AskUserQuestion` to ask:
  > "How many members should be seeded?"
  Offer options like `25`, `50`, `100`, `200`, plus an Other free-text
  option.

After collecting both values, store them as `MONTHS` and `MEMBERS`.
Both must be positive integers; reject zero/negative/non-numeric input
and re-ask. Echo the chosen values back before generating the script
(e.g. `Seeding 100 members across the last 6 months...`).

## 1. Read the schema

Read `database/db.py` to understand:
- The `members` table schema (name, email, password_hash, role, username,
  mobile, age, gender, address, join_date, plan_id, plan_expire_date,
  trainer_id, created_at)
- The `membership_plans` table and what plans currently exist
- The `get_db()` connection helper (uses `PRAGMA foreign_keys = ON`)
- Validation regexes: `_USERNAME_RAW_RE`, `_INDIAN_MOBILE_RE`
- `USERNAME_DEFAULT_DOMAIN = '@theroyalgym.com'`
- Existing seed data so you do NOT collide with `lakhan@admin.com` or
  `ansh@member.com`

Then write and run a Python script using Bash that uses `MEMBERS` and
`MONTHS` from step 0.

## 2. Generate `MEMBERS` realistic Indian members

Use your own knowledge of common Indian names across regions
(North, South, East, West). For each member:

- **Name**: realistic Indian `<first> <last>` — mix religions/regions
- **Gender**: roughly balanced — ~70% male, ~30% female. Pick first
  names that match the assigned gender. Store as `'male'` or `'female'`.
- **Age**: random integer between 18 and 55
- **Mobile**: Indian format that satisfies `is_valid_indian_mobile`
  → `+91` followed by a 10-digit number whose first digit is 6, 7, 8, or 9
  (e.g. `+919812345678`)
- **Address**: a short realistic Indian address only from Ghaziabad
  (e.g. `"Sector 12, Pratapvihar, Ghaziabad"`)

## 3. Username rule (must satisfy `is_valid_username`)

- 4-50 chars, **no whitespace**, lowercase
- Derive from the name: `<firstname><lastname>` lowercased,
  optionally suffixed with a 2-3 digit number to keep it unique
  (e.g. `rahulsharma`, `priyanair42`)
- Must be unique across the `members.username` column
- Email = `<username>@theroyalgym.com` (matches
  `normalize_username_to_email` behaviour)
- Email must also be unique across `members.email`
- If either collides, regenerate the numeric suffix until both are unique

## 4. Password

- Plain text: `"123456"` for every seeded member
- Store as `password_hash` using
  `werkzeug.security.generate_password_hash`

## 5. Membership plan distribution

- Read all rows from `membership_plans` first.
- If fewer than 3 distinct plans exist, INSERT the missing ones so the
  seed has variety. Use these (only insert names that don't already
  exist — match by `name`):
  - `Trial Plan`     → duration_months=0, duration_days=5,  fee=200
  - `Monthly`        → duration_months=1, duration_days=0,  fee=600
  - `Quarterly`      → duration_months=3, duration_days=0,  fee=1400
  - `Half-Yearly`    → duration_months=6, duration_days=0,  fee=2400
  - `Yearly`         → duration_months=12, duration_days=0, fee=5400
- Assign each member a random plan from the available plans, skewed so
  Monthly / Quarterly are most common and Trial / Yearly are rarer.

## 6. Spread join dates across the last `MONTHS` months

- Pick `join_date` as a random date within the **last `MONTHS` months**
  from today, formatted as `YYYY-MM-DD`.
- Roughly even distribution across those `MONTHS` buckets
  (≈ `MEMBERS / MONTHS` members per month, distribute the remainder
  across the earliest buckets so the totals match `MEMBERS` exactly).
- Compute `plan_expire_date` as
  `join_date + plan.duration_months months + plan.duration_days days`,
  formatted as `YYYY-MM-DD`.
- Set `created_at` to the same date as `join_date` at a random time of
  day (so the registered-today / monthly stats reflect realistic spread,
  not a single bulk insert timestamp). Use an explicit
  `INSERT ... (created_at) VALUES (?)` rather than relying on the
  `DEFAULT CURRENT_TIMESTAMP`.

## 7. Insert into the database

- Use the same `get_db()` pattern from `db.py` (parameterized SQL only).
- Set `role = 'user'` for all members.
- Leave `trainer_id = NULL`.
- Wrap the inserts in a single transaction; commit at the end.
- Skip (do not error) any row whose generated email or username still
  collides after a few retries — log it and continue.

## 8. Print a summary

After the run, print:
- The chosen `MONTHS` and `MEMBERS` inputs
- Total members inserted
- Count per gender
- Count per plan name
- Count per join-month (e.g. `2025-12: 17`, `2026-01: 16`, ...)
- The first 5 inserted rows showing `id, name, username, email, gender,
  plan_name, join_date, plan_expire_date`

Do not modify any application code or templates — this command only
seeds data.
