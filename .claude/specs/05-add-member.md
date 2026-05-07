# Spec: Add Member

## Overview
Wires up the **Members** tab — currently the last `endpoint=None` placeholder
in `ADMIN_NAV_ITEMS` for an in-progress feature — to a real admin-only flow at
`/admin/members` whose primary purpose is the **Add Member** form. Now that
the Plans CRUD shipped in step 04, an admin needs to register a new gym
member and assign them a plan in one go. This step delivers the minimum
viable Members surface: a basic list page that doubles as the entry point
for the Add Member button on the right (matching the Figma reference image
already used in step 04 planning), plus a focused new-member form that
captures name, email, mobile, password, plan, and plan start date — and
computes the plan-expiry date server-side from the chosen plan's
`duration_months`. Edit, detail, search, and filter remain out of scope and
are deferred to step 06.

## Depends on
- Step 02 — Admin Dashboard layout, including `ADMIN_NAV_ITEMS` and the
  shared `_admin_tabs.html` partial.
- Step 03 — Admin Settings (`b527d60`, merged in `7ad96b0`) — supplies the
  reusable `.user-action-btn` / `.user-pw-input` / `.user-pw-label` styles
  and the `data-confirm` JS handler that future actions on this page will
  reuse.
- Step 04 — Membership Plans CRUD (`5731561`, merged in `e72697f`) — the
  Add Member form's "Plan" dropdown is populated from `membership_plans` and
  uses `duration_months` to compute the expiry date.
- Existing auth scaffolding: `admin_required`, `_valid_csrf()`,
  `is_valid_email()`, `is_valid_mobile()`, `werkzeug.security.generate_password_hash`.

## Routes
- `GET /admin/members` — render the members list page (active tab =
  Members) — admin-only.
- `GET /admin/members/new` — render the **Add Member** form — admin-only.
- `POST /admin/members/new` — validate + create — admin-only. CSRF-protected.
  Successful creation flashes "Member created." and PRG-redirects to
  `/admin/members`. Validation failures or DB errors re-render the form
  with the entered values preserved (passwords are not echoed back).

No edit / delete / detail routes here. Delete remains in step 03's Settings
page; edit and detail are deferred to step 06.

## Database changes
- **Schema migrations in `init_db()`** — four idempotent `ALTER TABLE`
  blocks, mirroring the existing `members.role` migration pattern:
  ```python
  if not _column_exists(conn, 'members', 'mobile'):
      conn.execute('ALTER TABLE members ADD COLUMN mobile TEXT')
  if not _column_exists(conn, 'members', 'plan_id'):
      conn.execute('ALTER TABLE members ADD COLUMN plan_id INTEGER REFERENCES membership_plans(id) ON DELETE SET NULL')
  if not _column_exists(conn, 'members', 'plan_start_date'):
      conn.execute('ALTER TABLE members ADD COLUMN plan_start_date TEXT')
  if not _column_exists(conn, 'members', 'plan_expire_date'):
      conn.execute('ALTER TABLE members ADD COLUMN plan_expire_date TEXT')
  ```
  All four columns are nullable so the existing seeded admin and member rows
  continue to satisfy the schema. `ON DELETE SET NULL` on `plan_id` ensures
  deleting a plan via step 04 doesn't orphan a member with an FK reference
  pointing at a non-existent row.

- **Existing helpers updated to surface the new columns:**
  - `get_member_by_id(user_id)` — extend SELECT projection to include
    `mobile, plan_id, plan_start_date, plan_expire_date`.
  - `get_all_members()` — extend SELECT to include the same four columns
    plus a `LEFT JOIN membership_plans p ON p.id = members.plan_id` so the
    list page can show the plan name without a per-row lookup. Add `p.name
    AS plan_name, p.duration_months AS plan_duration` to the projection.
  - `get_member_by_email(email)` — leave alone (login flow doesn't need
    plan info).

- **One new helper in `database/db.py`:**
  - `create_member(name, email, password_hash, mobile, plan_id, plan_start_date, plan_expire_date) -> int`
    - SQL: `INSERT INTO members (name, email, password_hash, role, mobile,
      plan_id, plan_start_date, plan_expire_date) VALUES (?, ?, ?, 'user',
      ?, ?, ?, ?)`
    - Lower-cases email before insert (matches `seed_db` and login
      conventions). Returns `lastrowid`. Lets `sqlite3.IntegrityError`
      propagate so the route can flash a duplicate-email error.

- **No change to `seed_db()`** — existing seeds keep `mobile`, `plan_id`,
  and the date columns NULL; the list page renders these as `—`.

All helpers use parameterised queries and the existing `get_db()` /
`try…finally close()` pattern.

## Templates
- **Create:**
  - `templates/admin_members.html` — extends `base.html`, loads
    `dashboard.css`. Sections in order:
    1. `{% include "_admin_tabs.html" %}` (Members tab `is-active`).
    2. `<section class="dash-panel">` containing:
       - `.plans-header` (reused) with crown-style icon, `Members` title,
         "Manage gym members, plans, and profiles." subtitle on the left,
         and a `<a class="plans-add-btn" href="{{ url_for('admin_members_new') }}">+ Add Member</a>`
         button on the right.
       - `.dash-table-wrap` + `.dash-table` columns: `#`, `Full Name`,
         `Email`, `Mobile`, `Plan`, `Join Date`, `Plan Expiry`. Each row's
         Plan cell shows a `.role-pill` (or new `.plan-pill`) with the
         joined `plan_name`, falling back to `—` when null. The Mobile,
         Plan, Plan Expiry cells render `—` when their value is null.
       - Empty state: existing `.dash-empty` row when no members exist.

  - `templates/admin_member_new.html` — extends `base.html`. Sections:
    1. Tab bar (Members tab still `is-active`).
    2. `.plans-header` with the same crown icon, heading "Add Member", and
       a `← Back to members` link on the right (using `.user-action-btn`).
    3. `<form method="post" class="plan-form" action="{{ url_for('admin_members_new') }}">` with CSRF input and fields:
       - `name`         (text, required, minlength=2, maxlength=100)
       - `email`        (email, required, maxlength=150)
       - `mobile`       (tel,  required, maxlength=20)
       - `plan_id`      (`<select>`, required) populated from
         `plans` template var (`{{ p.id }}`/`{{ p.name }} ({{ p.duration_months }} mo)`).
       - `plan_start_date` (date, required, default `today_iso`)
       - `new_password`     (password, required, minlength=6, maxlength=200)
       - `confirm_password` (password, required, minlength=6, maxlength=200)
       Submit button `<button type="submit" class="plans-add-btn">Create member</button>`
       and a Cancel `<a class="user-action-btn" href="{{ url_for('admin_members') }}">`.
       On validation failure the route re-renders this template with
       `prefill={'name': …, 'email': …, 'mobile': …, 'plan_id': …, 'plan_start_date': …}`
       so the admin doesn't lose typed values. Password fields are NOT
       prefilled.

- **Modify:**
  - `templates/admin_dashboard.html` is **not** edited — its top tab loop
    and bottom quick-link loop iterate `nav_items`, so flipping the
    `Members` entry's `endpoint` to `'admin_members'` in `app.py`
    automatically activates both surfaces.
  - `templates/_admin_tabs.html` is unchanged.

## Files to change
- `app.py`
  - In `ADMIN_NAV_ITEMS`, change the `Members` entry's `endpoint` from
    `None` to `'admin_members'`.
  - Imports: add `create_member` from `database.db`. (`get_all_plans`,
    `get_all_members`, `is_valid_email`, `is_valid_mobile`,
    `get_member_by_email`, `generate_password_hash` are all already
    imported from earlier steps.)
  - New helper `_add_months(start_iso: str, months: int) -> str` — pure
    Python (stdlib only) using `datetime.date`. Adds `months` to a
    `YYYY-MM-DD` string and returns the same format. Handles month-end
    edge cases (e.g. Jan 31 + 1 month → Feb 28/29). Local to `app.py`.
  - Three new route handlers, all decorated with `@admin_required`:
    - `admin_members()` — `GET /admin/members` — calls
      `get_all_members(role='user')` (or filter in route until a
      `get_members_by_role` helper exists — see DB section above; spec
      assumes the existing helper is extended to allow filtering OR a new
      `get_members_by_role('user')` is added). Renders
      `admin_members.html` with `nav_items=ADMIN_NAV_ITEMS`,
      `members=…`, `active_tab='Members'`.
    - `admin_members_new()` — `GET /admin/members/new` — fetches plans via
      `get_all_plans()`, renders `admin_member_new.html` with
      `prefill={…default…}`, `plans=…`, `today_iso=date.today().isoformat()`,
      `active_tab='Members'`.
    - `admin_members_create()` — `POST /admin/members/new` — CSRF check,
      server-side validation (see Rules), computes
      `plan_expire_date = _add_months(plan_start_date, plan.duration_months)`,
      hashes password, calls `create_member`. `try/except sqlite3.IntegrityError`
      → flash "An account with that email already exists." and re-render
      the form preserving entered values. `try/except sqlite3.Error` →
      flash generic error. On success, flash "Member created." and
      redirect to `/admin/members`.

- `database/db.py`
  - Add the four idempotent column migrations in `init_db()`.
  - Update `get_member_by_id` and `get_all_members` SELECT projections.
  - Add the `create_member` helper.
  - **Decision in this spec:** extend `get_all_members` to accept an
    optional `role` argument (default `None`). When provided, append a
    `WHERE role = ?` clause. Keeps the API surface tight (one helper, two
    callers — admin_dashboard count and admin_members list).

- `static/css/dashboard.css`
  - Add `.member-row-name` (a 2-line stack: bold name + small
    `Member` sub-tag, mirroring step 04's `.plan-name` pattern but with a
    different sub-tag colour — reuses `.plan-tag`).
  - Add `.plan-pill` — small green pill for the "Plan" column on the
    members list, using the existing `--accent-gold` family or a new
    `--success-bg` variable. **Decision:** reuse the existing
    `.role-pill .role-pill-user` styling as a base; if the Figma's plan
    pill is meaningfully different (green vs the existing teal-ish
    treatment), define `.plan-pill` with `var(--accent-gold)` family
    tokens — no new hex literals.
  - Reuse `.plan-form`, `.user-pw-input`, `.user-pw-label`,
    `.plan-form-actions`, `.plans-header`, `.plans-add-btn`, `.dash-table`,
    `.dash-empty` from earlier steps. No new CSS variables required.

- `static/css/style.css` — no changes.

## Files to create
- `templates/admin_members.html`
- `templates/admin_member_new.html`

## New dependencies
No new dependencies. Flask, Werkzeug, and stdlib `sqlite3` + `datetime`.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only (`?` placeholders) for the new helper and the
  modified SELECTs. The schema migration uses literal `ALTER TABLE`
  statements with no user input.
- Passwords hashed with `werkzeug.security.generate_password_hash` — never
  stored in plain text. Hashing happens in the route, before
  `create_member` is called.
- **Use CSS variables — never hardcode hex** inside any `.member-*`,
  `.plan-*`, `.dash-*`, `.admin-*`, or `.user-*` rule. If a new tone is
  needed, add a `:root` variable in `style.css` first.
- All templates `{% extends "base.html" %}`.
- Vanilla JS only — no new JS for this step. The form uses native
  `required` / `minlength` / `type=date` / `type=email` attributes; server
  is authoritative.
- All three new routes decorated with `@admin_required`.
- POST route starts with `if not _valid_csrf(request.form.get('csrf_token')): abort(403)`.
- Server-side validation of the **Add Member** form:
  - `name`             — strip → required, length ∈ [2, 100].
  - `email`            — strip + lower → required, length ≤ 150,
    `is_valid_email(email)`.
  - `mobile`           — strip → required, length ≤ 20,
    `is_valid_mobile(mobile)`.
  - `plan_id`          — int-castable, must match an existing plan
    (`get_plan_by_id(plan_id)` returns a row).
  - `plan_start_date`  — non-empty, parseable via `date.fromisoformat`,
    not in the distant past or future. **Decision:** keep validation
    minimal — accept any valid date; admin discretion governs. Reject
    only on parse error.
  - `new_password`     — required, length ∈ [6, 200].
  - `confirm_password` — required, must equal `new_password`.
  - Each failure flashes a specific error and re-renders
    `admin_member_new.html` with the typed values (excluding passwords) in
    `prefill`.
- Email storage and lookup are case-insensitive (the `members.email` column
  is already `COLLATE NOCASE`). Always lower-case before insert/comparison.
- Duplicate email handled at the DB layer: `create_member` lets
  `sqlite3.IntegrityError` propagate; the route catches it and flashes
  "An account with that email already exists."
- New member's `role` is hard-coded to `'user'` in `create_member`. To
  promote them, the admin uses the Settings page from step 03.
- `plan_expire_date` is computed server-side via `_add_months(start, plan.duration_months)`.
  The form does NOT collect this value — admins can't override the
  computed expiry from the create form. Future edit flow may allow it.
- Members tab is now `endpoint='admin_members'` in `ADMIN_NAV_ITEMS`. The
  bottom quick-link card on `/admin/dashboard` automatically becomes
  navigable; `_admin_tabs.html` already filters Settings out of the top
  bar but Members is unaffected.
- No inline `onclick` / `onsubmit` (CSP `script-src 'self'`).
- Errors logged via `app.logger.exception`; users see generic flash text
  only.

## Definition of done
- [ ] `python theroyalgym/app.py` boots cleanly on port 5001 with no
      console errors and no Jinja2 warnings.
- [ ] `PRAGMA table_info(members);` (via `sqlite3 gym.db`) lists the four
      new columns: `mobile TEXT`, `plan_id INTEGER`, `plan_start_date
      TEXT`, `plan_expire_date TEXT`. Existing seeded rows keep all four
      `NULL`.
- [ ] Logged in as `lakhan@admin.com` / `123456`:
  - [ ] The top admin tab bar's **Members** entry is a real link
        (no `aria-disabled`) pointing at `/admin/members`.
  - [ ] The bottom quick-link card **Members** is a real link too.
  - [ ] Visiting `/admin/members` renders 200 with: tab bar (Members tab
        `is-active`), header with crown-style icon + `+ Add Member`
        button, and a table containing the seeded `ansh@member.com` row
        (mobile / plan / plan-expiry render as `—`).
- [ ] **Add Member happy path** — `/admin/members/new` renders the form
      with the plan dropdown populated from `get_all_plans()` and
      `plan_start_date` defaulting to today. Submitting valid
      name/email/mobile/plan/start-date/passwords:
  - [ ] Inserts the row with `role='user'` (verify via `sqlite3 gym.db
        "SELECT name, email, mobile, plan_id, plan_start_date,
        plan_expire_date, role FROM members WHERE email='new@member.com';"`).
  - [ ] `plan_expire_date` equals `plan_start_date` plus the chosen plan's
        `duration_months` (e.g., Monthly + 2026-05-07 → 2026-06-07).
  - [ ] Redirects to `/admin/members`, flashes "Member created.", and the
        new row appears in the table with the plan name shown.
- [ ] **Quarterly plan** — selecting Quarterly with start `2026-03-31`
      yields expire `2026-06-30` (month-end edge case handled).
- [ ] **Yearly plan** — selecting Yearly with start `2026-05-07` yields
      expire `2027-05-07`.
- [ ] **Add Member duplicate email** — submitting an email that already
      exists (e.g. `ansh@member.com`) re-renders the form with the error
      flash "An account with that email already exists.", retains the
      typed name/email/mobile/plan_id/plan_start_date, and does **not**
      create a duplicate (DB row count unchanged).
- [ ] **Add Member validation errors** — each of the following re-renders
      the form with a specific error and creates no row:
  - [ ] empty name
  - [ ] invalid email format
  - [ ] empty / invalid mobile
  - [ ] non-existent `plan_id` (e.g., `9999`)
  - [ ] invalid `plan_start_date` (e.g., `not-a-date`)
  - [ ] `new_password` length 5
  - [ ] `confirm_password` != `new_password`
- [ ] **CSRF rejection** — `curl -X POST /admin/members/new` with a valid
      session cookie but no CSRF token returns 403, no row created.
- [ ] **Anonymous** — visiting `/admin/members` or `/admin/members/new`
      redirects to `/login`.
- [ ] **Member access** — `ansh@member.com` visiting `/admin/members*`
      returns 403.
- [ ] **Login still works** — the new columns do not break the existing
      login flow (verify by logging in as ansh).
- [ ] At 1440px viewport: list table renders inline; Add Member button
      sits on the right of the panel header. At 768px: the form stacks
      vertically; the table scrolls horizontally without page overflow.
- [ ] `curl -s -D - -o /dev/null http://127.0.0.1:5001/admin/members`
      (logged in as admin) returns CSP, X-Frame-Options,
      X-Content-Type-Options, Referrer-Policy headers.
- [ ] **No new hex literals** inside any `.member-*`, `.plan-*`, `.dash-*`,
      `.admin-*`, or `.user-*` rule. Verify via:
      ```powershell
      git diff main..HEAD -- static/css/dashboard.css `
        | Select-String '^\+' | Select-String -NotMatch '^\+\+\+' `
        | Select-String '#[0-9a-fA-F]{3,6}\b'
      ```
      Output must be empty.
- [ ] **No inline event handlers** in any new template (`Select-String
      'on(click|submit)=' templates/admin_members*.html` returns nothing).
- [ ] `/`, `/login`, `/terms`, `/admin/dashboard`, `/admin/settings`,
      `/admin/plans`, `/admin/plans/new`, `/admin/plans/<id>/edit`,
      `/member/dashboard`, `/this-route-does-not-exist` all render
      exactly as before — only the Members surface is added.
- [ ] `git diff main..HEAD --name-only` lists exactly: `app.py`,
      `database/db.py`, `static/css/dashboard.css`,
      `templates/admin_members.html`, `templates/admin_member_new.html`,
      `.claude/specs/05-add-member.md`. No other paths.

## Open questions
- **Edit member** — current spec defers in-place edit (name / email /
  mobile / plan / start date). The Members list shows the data but
  provides no Edit affordance. Alternative: include an `/admin/members/<id>/edit`
  GET+POST in this step. Going without to keep step 05 narrowly focused
  on the Add Member flow that the user explicitly requested. Step 06 can
  layer in edit + detail.
- **Username column** — image from step 04 planning shows a Username
  column with @ icon (e.g., `abcd`, `sachin`). Current spec drops this
  column from the list table to avoid a schema addition that has no
  current login-by-username flow. Alternative: add the column. Going
  without — the list table shows Email + Mobile, which together
  uniquely identify the member without a separate handle.
- **Plan start date validation** — current spec accepts any valid date.
  Alternative: reject dates older than today, or older than 1 year ago,
  or further than 1 year ahead. Going lax — admins may backdate when
  importing existing members.
- **Existing seeded `ansh@member.com` row** — has all four new columns
  NULL. List rendering shows `—` for each. Alternative: extend
  `seed_db()` to assign ansh the Monthly plan retroactively. Going
  without — keeps the seed simple; admins can use the Add Member flow
  to create test data.
- **`get_all_members` API shape** — current spec extends it to accept an
  optional `role` arg. Alternative: add a new `get_members_by_role`
  helper. Going with extending the existing helper to keep the count of
  helpers down; both calling sites (`admin_dashboard`,
  `admin_members`) are simple.
