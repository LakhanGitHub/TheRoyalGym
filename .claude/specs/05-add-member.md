# Spec: Add Member

## Overview
Wires up the **Members** tab — previously the last `endpoint=None` placeholder
in `ADMIN_NAV_ITEMS` — to a real admin-only flow at `/admin/members` whose
primary purpose is the **Add Member** form. The form is the single
onboarding surface used to register a gym member, generate their login
credential from a short username, capture their contact details, and
assign them a Membership Plan that maps live to rows in the
`membership_plans` table. The plan-expiry date is computed server-side
from the chosen plan's `duration_months`.

This revision (May 2026) strengthens validation to fix bugs in the
original Add Member flow and aligns frontend UX with backend rules:

* The **Username** is the source of the login email. If the admin types a
  bare handle (e.g. `raj123`) the backend appends `@theroyalgym.com` to
  store a valid email; full email input (e.g. `raj@gmail.com`) is also
  accepted.
* The **Mobile** field is locked to the Indian format `+91` followed by a
  10-digit mobile number whose first digit is 6–9.
* The **Membership Plan** dropdown is populated from `get_all_plans()` and
  re-validated server-side against `get_plan_by_id()` so a stale or
  deleted plan id can never be inserted.
* The **Age** field is unprefilled — only a placeholder hint — so admins
  start with a clean number input.
* The **Join Date** field is required, supports the native date picker
  *and* manual entry, and parses via `date.fromisoformat()` server-side.
* Inline JavaScript validation mirrors every server rule, disables the
  Save button until the form is valid, and highlights invalid fields in
  red — but the server is still authoritative.

The Members list page is unchanged from the original step 05 scope: a
read-only table with an `+ Add Member` button. Edit, detail, search,
and filter remain deferred.

The Admin Dashboard hero's `+ Add Member` button is also wired to this
form so admins can jump in from anywhere in the admin shell.

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
  `is_valid_email()`, `is_valid_mobile()`, `is_valid_indian_mobile()`,
  `is_valid_username()`, `normalize_username_to_email()`,
  `werkzeug.security.generate_password_hash`.

## Routes
- `GET /admin/members` — render the members list page (active tab =
  Members) — admin-only. Passes `today_iso` and `current_month` to the
  template so the expiry pill can colour by month.
- `GET /admin/members/new` — render the **Add Member** form — admin-only.
- `POST /admin/members/new` — validate + create — admin-only.
  CSRF-protected. Successful creation flashes "Member created. Login:
  &lt;email&gt;" and PRG-redirects to `/admin/members`. Validation
  failures or DB errors re-render the form with the entered values
  preserved (passwords are not echoed back).
- `GET /admin/members/<int:member_id>/edit` — render the form in edit
  mode prefilled from the member row — admin-only. Username (the email)
  is shown as read-only; the password field is removed (use the
  Settings page from step 03 to reset passwords).
- `POST /admin/members/<int:member_id>/edit` — validate + update —
  admin-only. CSRF-protected. The username/email is never updated by
  this route. Successful update flashes "Member &lt;name&gt; updated."
  and PRG-redirects to `/admin/members`.
- `POST /admin/members/<int:member_id>/delete` — admin-only,
  CSRF-protected, confirmed via the gym-themed `<dialog>` modal on the
  list page. Refuses any member whose `role != 'user'`. Successful
  delete flashes "Deleted &lt;name&gt;." and redirects to
  `/admin/members`.

Detail / search / filter remain deferred to step 06.

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

- **Two new helpers in `database/db.py`:**
  - `create_member(name, email, password_hash, mobile, plan_id, plan_start_date, plan_expire_date) -> int`
    - SQL: `INSERT INTO members (name, email, password_hash, role, mobile,
      plan_id, plan_start_date, plan_expire_date) VALUES (?, ?, ?, 'user',
      ?, ?, ?, ?)`
    - Lower-cases email before insert (matches `seed_db` and login
      conventions). Returns `lastrowid`. Lets `sqlite3.IntegrityError`
      propagate so the route can flash a duplicate-email error.
  - `update_member(member_id, name, mobile, age, gender, join_date, address, plan_id, plan_expire_date, trainer_id=None)`
    - SQL: `UPDATE members SET name=?, mobile=?, age=?, gender=?,
      join_date=?, address=?, plan_id=?, plan_expire_date=?,
      trainer_id=? WHERE id=?`. Email and username are intentionally
      NOT touched — the login credential is immutable from this surface.
    - The existing `delete_member(member_id)` helper from step 03 is
      reused unchanged.

- **No change to `seed_db()`** — existing seeds keep `mobile`, `plan_id`,
  and the date columns NULL; the list page renders these as `—`.

All helpers use parameterised queries and the existing `get_db()` /
`try…finally close()` pattern.

## Templates
- **Create:**
  - `templates/admin_members.html` — extends `base.html`, loads
    `dashboard.css`. Sections in order:
    1. `{% include "_admin_tabs.html" %}` (Members tab `is-active`).
    2. `<section class="dash-panel members-panel">` containing:
       - `.plans-header` (reused) with crown-style icon, `Members`
         title, "Manage gym members, plans, and profiles." subtitle on
         the left, and a
         `<a class="plans-add-btn" href="{{ url_for('admin_members_new') }}">+ Add Member</a>`
         button on the right.
       - `.dash-table-wrap` + `.dash-table.members-table` columns: `#`,
         `Full Name`, `Username`, `Mobile`, `Plan`, `Join Date`,
         `Plan Expiry`, `Actions`.
         - **Username** cell renders `m.email` (the login credential)
           via `.member-email-cell` with a `mailto:` envelope icon that
           appears on row hover. The mailto link prefills a
           gym-branded subject and body referencing the member name,
           plan, and expiry date so admins can fire off a renewal
           reminder in one click.
         - **Mobile** cell renders the stored `+91XXXXXXXXXX` as
           `+91 XXXXX XXXXX` inside `.member-mobile-cell` with a small
           gold-tinted phone-icon chip. The number is a plain
           `<span class="member-mobile-text">` — **no** anchor wrapping
           and **no** hover effect (this column is read-only display,
           not an interactive call link).
         - **Plan** cell shows a `.role-pill.role-pill-user` with the
           joined `plan_name`, or `—` when null.
         - **Plan Expiry** cell renders `<span class="expiry-pill expiry-{state}">…</span>`,
           where `{state}` is computed in Jinja from `today_iso` /
           `current_month`:
           - `expired` — date is strictly before today.
           - `warning` — date is in the current calendar month
             (red background, white bold text + warning icon).
           - `active` — any other future date.
         - **Actions** cell shows two `.member-icon-btn` buttons:
           - `.member-icon-btn-edit` — pencil SVG, `<a>` link to the
             edit route, `title="Edit Member"`.
           - `.member-icon-btn-delete` — trash SVG, `<button>` carrying
             `data-delete-member-id`, `data-delete-member-name`,
             `data-delete-member-email`, `title="Delete Member"`.
       - Empty state: existing `.dash-empty` row when no members exist.
    3. A single `<dialog class="member-modal" id="deleteMemberModal">`
       at the bottom of the page containing a CSRF-stamped form whose
       `action` is set by the modal-wiring JS to
       `/admin/members/<id>/delete` when an admin clicks a row's delete
       icon. `data-modal-close` triggers `dialog.close()`; the dialog
       backdrop also closes the modal.

  - `templates/admin_member_new.html` — extends `base.html`. Serves
    BOTH the create flow (`mode='new'`) and the edit flow
    (`mode='edit'`). The header title, submit button label, and form
    `action` switch between the two modes. In edit mode the username
    field is `readonly` and the password field is omitted entirely so
    the credential is non-mutable from this surface. Sections:
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
  - **Compact members table** (May 2026): `.members-table` overrides
    base `.dash-table` typography with a denser look — `font-size:
    0.82rem`, `td { padding: 9px 14px; white-space: nowrap; }`,
    `th { font-size: 0.68rem; padding: 9px 14px; }`. `white-space:
    nowrap` keeps each member's row on a single line (the table wraps
    into a horizontal scroll inside `.dash-table-wrap` if the viewport
    is narrower than the content).
  - **Action row stays horizontal**: `.user-actions.member-actions`
    forces `flex-direction: row; flex-wrap: nowrap; align-items:
    center; gap: 6px;` and an explicit override inside the
    `@media (max-width: 768px)` block prevents the parent
    `.user-actions` column-stack rule from flipping member icon
    actions to vertical on tablet/mobile. Used by both the Members
    list and the Plans list.
  - **Shared icon button** (`.member-icon-btn` /
    `.member-icon-btn-edit` / `.member-icon-btn-delete`) is the single
    source of truth for action icons across Members and Plans. 32×32
    square, 15×15 SVG, gold tint on edit hover, danger fill on delete
    hover, `:focus-visible` outline.
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
- Vanilla JS only. Two blocks in `static/js/main.js`:
  - **Member form validation**, gated by `#addMemberForm`. Mirrors
    every server-side rule, masks the mobile input to lock the `+91`
    prefix, disables the Save button until the form is valid, and tags
    invalid fields with `.is-invalid` (red border). The form sets
    `novalidate` so the JS layer owns the UX; the server is still
    authoritative for acceptance.
  - **Delete-confirmation modal**, gated by `#deleteMemberModal`. On
    click of any `[data-delete-member-id]` button, the script sets the
    form `action` to `/admin/members/<id>/delete`, populates the modal
    name/email, and calls `dialog.showModal()`. `data-modal-close` and
    backdrop clicks call `dialog.close()`. Falls back gracefully on
    browsers without `<dialog>` support by toggling the `open`
    attribute.
- All three new routes decorated with `@admin_required`.
- POST route starts with `if not _valid_csrf(request.form.get('csrf_token')): abort(403)`.
- Server-side validation of the **Add Member** form (each failure flashes
  a specific message and re-renders `admin_member_new.html` with the
  typed values; the password is never echoed back):
  - `username`   — strip → required, `is_valid_username` (4–50 chars, no
    whitespace). After `normalize_username_to_email(username)` the result
    must satisfy `is_valid_email` and be ≤ 150 chars. The normalized
    value is what gets stored in `members.email` AND `members.username`,
    so uniqueness is enforced via the `email UNIQUE COLLATE NOCASE`
    constraint and the `idx_members_username` partial unique index.
  - `password`   — required, length ∈ [6, 200], hashed with
    `generate_password_hash` before insert.
  - `name`       — strip → required, length ∈ [2, 100].
  - `mobile`     — strip → required, `is_valid_indian_mobile(mobile)`
    (must match `^\+91[6-9]\d{9}$`).
  - `age`        — optional. If provided, must be a whole number in
    [5, 120].
  - `gender`     — optional. If provided, must be in `GENDER_OPTIONS`.
  - `join_date`  — required, parseable via `date.fromisoformat()`. Any
    valid ISO date is accepted (admin discretion). The form does **not**
    pre-fill today; the input renders empty so the admin actively picks
    via the native `<input type="date">` calendar widget (clicking the
    field also lets them type the date manually). `_empty_member_prefill()`
    sets `'join_date': ''` and the template uses
    `value="{{ prefill.join_date }}"` (no `or today_iso` fallback).
  - `address`    — optional, length ≤ 500.
  - `plan_id`    — required, int-castable, must reference an existing
    row via `get_plan_by_id(plan_id)`. Server then computes
    `plan_expire_date = _add_months(join_date, plan.duration_months)`.
- Username/email storage and lookup are case-insensitive (the
  `members.email` column is `COLLATE NOCASE`). Always lower-case before
  insert/comparison. The route always stores the full normalized email
  in `members.email`. For `members.username` it stores the **bare handle
  the admin typed** when no `@` was present (e.g. `raj123`), and the
  full email otherwise — so members onboarded via a handle can log in
  with either `raj123` or `raj123@theroyalgym.com` via
  `get_member_by_login()` (which queries `email OR username`).
- Duplicate username/email handled at the DB layer: `create_member` lets
  `sqlite3.IntegrityError` propagate; the route catches it and flashes
  "That username is already taken. Pick a different one."
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
- [ ] `PRAGMA table_info(members);` (via `sqlite3 gym.db`) lists the
      member-detail columns: `username`, `mobile`, `age`, `gender`,
      `address`, `join_date`, `plan_id`, `plan_expire_date`,
      `trainer_id`. Existing seeded rows keep all of these `NULL`.
- [ ] Logged in as `lakhan@admin.com` / `123456`:
  - [ ] The top admin tab bar's **Members** entry is a real link
        pointing at `/admin/members`.
  - [ ] The bottom quick-link card **Members** is a real link.
  - [ ] The dashboard hero's **+ Add Member** button is a real link to
        `/admin/members/new` (not the previous disabled stub).
  - [ ] Visiting `/admin/members` renders 200 with: tab bar (Members tab
        `is-active`), header with crown-style icon + `+ Add Member`
        button, and a table containing seeded rows (empty cells render
        as `—`).
- [ ] **Add Member happy path (handle only)** — submitting username
      `raj123`, password `secret1`, name `Raj K`, mobile `+919876543210`,
      gender `Male`, today's join date, and the Monthly plan:
  - [ ] Inserts a row with `role='user'`,
        `email='raj123@theroyalgym.com'`, `username='raj123'`,
        the supplied mobile, and the chosen plan id.
  - [ ] `plan_expire_date` equals join date plus the plan's
        `duration_months` (e.g., Monthly + 2026-05-08 → 2026-06-08).
  - [ ] Redirects to `/admin/members`, flashes
        "Member \"Raj K\" created. Login: raj123@theroyalgym.com",
        and the new row appears in the table.
- [ ] **Add Member happy path (full email)** — submitting username
      `raj@gmail.com` stores `email='raj@gmail.com'` (no domain rewrite).
- [ ] **Quarterly plan** — Quarterly + start `2026-03-31` →
      expire `2026-06-30` (month-end edge case handled).
- [ ] **Yearly plan** — Yearly + start `2026-05-08` →
      expire `2027-05-08`.
- [ ] **Duplicate username/email** — submitting a username that resolves
      to an existing email (e.g. `lakhan@admin.com`) re-renders the form
      with the error flash "That username is already taken. Pick a
      different one.", retains all non-password fields, and does not
      create a row.
- [ ] **Add Member validation errors** — each of the following
      re-renders the form with a specific error and creates no row:
  - [ ] empty username
  - [ ] username with whitespace (`ra j 123`)
  - [ ] username under 4 chars (`abc`)
  - [ ] empty / under-6-char password
  - [ ] empty name / 1-char name
  - [ ] missing mobile / mobile without `+91` / mobile starting `+915…`
        / mobile with fewer or more than 10 digits after `+91`
  - [ ] non-existent `plan_id` (e.g., `9999`)
  - [ ] missing or non-parseable `join_date` (e.g., `not-a-date`)
  - [ ] no plan selected
- [ ] **Frontend validation** —
  - [ ] Mobile field renders pre-filled with `+91` and refuses to let
        the prefix be deleted; only digits are accepted after it.
  - [ ] Save button is disabled (`aria-disabled="true"`) on initial
        render of an empty form and re-enables once every required
        field passes client validation.
  - [ ] Invalid fields gain an `is-invalid` class (red border) and
        their `.member-error` span shows the specific message.
  - [ ] The age field is empty on first render — only the placeholder
        is visible.
  - [ ] The Membership Plan dropdown lists exactly the rows returned
        by `get_all_plans()`; the placeholder option (`Select a
        plan…`) is `disabled` and cannot be submitted.
- [ ] **Backend authority** — submitting via curl with malformed values
      (e.g. `mobile=123456`, `plan_id=9999`, `username=ra j`) bypasses
      the JS layer but is rejected with a flashed error and no DB row
      is created.
- [ ] **CSRF rejection** — `curl -X POST /admin/members/new` with a
      valid session cookie but no CSRF token returns 403, no row
      created.
- [ ] **Anonymous** — visiting `/admin/members` or `/admin/members/new`
      redirects to `/login`.
- [ ] **Member access** — `ansh@member.com` visiting `/admin/members*`
      returns 403.
- [ ] **Login still works** — a member created via the new flow can
      log in using the username they were registered with (handle or
      full email) and reaches `/member/dashboard`.
- [ ] **Members list rendering** — at `/admin/members`:
  - [ ] The Username column shows each member&rsquo;s stored email
        verbatim (no separate `username` column display).
  - [ ] The Mobile column shows `+91 XXXXX XXXXX` (a single space after
        `+91` and another between the 5-digit blocks) inside a
        `.member-mobile-cell` with the phone-icon prefix; clicking the
        number opens `tel:`.
  - [ ] The Plan Expiry column shows an `.expiry-pill` whose modifier
        class is computed from `today_iso` / `current_month`:
        `.expiry-warning` (red bg + white bold + warning icon) when
        the date is in the current month, `.expiry-expired` (darker
        danger + strike-through) when before today, `.expiry-active`
        otherwise.
  - [ ] Hovering a row reveals the envelope `.member-email-action`
        next to the email; clicking it opens a `mailto:` URL whose
        subject is "The Royal Gym — Membership Renewal Reminder" and
        whose body references the member name, plan name, and expiry
        date.
  - [ ] The Edit action is a pencil-icon `<a>` with
        `title="Edit Member"` linking to `/admin/members/<id>/edit`.
  - [ ] The Delete action is a trash-icon `<button>` with
        `title="Delete Member"` whose `data-delete-member-*`
        attributes feed the confirmation modal.
- [ ] **Edit happy path** — clicking Edit loads the form pre-filled
      with the member&rsquo;s name, mobile, age, gender, address,
      join_date, and selected plan. The username field is `readonly`,
      the password field is absent, the submit button reads "Save
      changes". Submitting an updated name + plan flashes
      "Member &lt;name&gt; updated.", PRG-redirects to
      `/admin/members`, and persists the change in SQLite. Email and
      username remain unchanged.
- [ ] **Edit guard** — `GET /admin/members/&lt;id&gt;/edit` for
      `id` of an admin user (e.g. `lakhan@admin.com`) flashes
      "Member not found." and redirects to `/admin/members` (no edit
      surface for fellow admins).
- [ ] **Delete modal** — clicking Delete opens
      `#deleteMemberModal` with the member&rsquo;s name and email
      filled in. Pressing Cancel or backdrop closes the modal with
      no DB change. Pressing Delete submits to
      `/admin/members/&lt;id&gt;/delete`, flashes
      "Deleted &lt;name&gt;.", PRG-redirects, and removes the row.
- [ ] **Delete CSRF** — `curl -X POST
      /admin/members/&lt;id&gt;/delete` without a valid token
      returns 403 and the row remains.
- [ ] **Delete guard** — POST to
      `/admin/members/&lt;admin_id&gt;/delete` with a valid CSRF
      token does not delete the admin and flashes "Member not found.".
- [ ] **Join Date picker UX** — visiting `/admin/members/new` shows
      the Join Date input **empty** (no auto-prefill). Clicking it
      opens the native browser calendar and any past, current, or
      future date can be selected. Manually typing a date is also
      accepted. Submitting an arbitrary date (e.g. `2027-01-15`)
      stores that exact value in `members.join_date`; the
      `plan_expire_date` is computed from it.
- [ ] **Compact members table** — `/admin/members` rows render with
      `.members-table` typography (smaller font, single-line cells,
      denser padding) and content does **not** wrap mid-row at
      desktop widths. The Mobile cell shows the formatted number as
      a plain span — hovering it does **not** change colour, and it
      is **not** a clickable `tel:` link.
- [ ] **Horizontal action layout** — Edit and Delete icon buttons
      sit on a single row in the Actions column at every viewport
      ≥ 360px (verified by inspecting layout at 1440px, 1024px,
      768px, and 360px). They never wrap or stack vertically.
- [ ] **Plans tab icon parity** — `/admin/plans` rows now use the
      same `.member-icon-btn` family as Members. Edit is a pencil
      `<a>` with `title="Edit Plan"` linking to
      `/admin/plans/&lt;id&gt;/edit`; Delete is a trash `<button>`
      inside a CSRF-stamped form with `title="Delete Plan"` and the
      existing `data-confirm` guard. Icon size, button shape, and
      spacing match Members.
- [ ] At 1440px viewport: list table renders inline; Add Member button
      sits on the right of the panel header. At 768px: the form stacks
      vertically; the table scrolls horizontally without page overflow.
- [ ] `curl -s -D - -o /dev/null http://127.0.0.1:5001/admin/members`
      (logged in as admin) returns CSP, X-Frame-Options,
      X-Content-Type-Options, Referrer-Policy headers.
- [ ] **No new hex literals** inside any `.member-*`, `.plan-*`,
      `.dash-*`, `.admin-*`, or `.user-*` rule. Verify via:
      ```powershell
      git diff main..HEAD -- static/css/dashboard.css `
        | Select-String '^\+' | Select-String -NotMatch '^\+\+\+' `
        | Select-String '#[0-9a-fA-F]{3,6}\b'
      ```
      Output must be empty.
- [ ] **No inline event handlers** in any new template — `Select-String
      'on(click|submit)=' templates/admin_members*.html` returns
      nothing. CSP `script-src 'self'` continues to allow only
      `static/js/main.js`.
- [ ] `/`, `/login`, `/terms`, `/admin/dashboard`, `/admin/settings`,
      `/admin/plans`, `/admin/plans/new`, `/admin/plans/<id>/edit`,
      `/member/dashboard`, `/this-route-does-not-exist` all render
      exactly as before — only the Members surface and the dashboard
      hero's `+ Add Member` link are added.

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
