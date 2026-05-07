# Spec: Create Members Page

## Overview
Wires up the **Members** tab — currently a placeholder in `ADMIN_NAV_ITEMS` — to a
real admin-only page at `/admin/members` that lists every member account
(`role = 'user'`), exposes a focused **Add Member** flow so admins can register a
member directly, and gives each row a read-only **detail** view. The Settings
page (step 03) handles role/password/delete on *all* users including admins;
the Members page is the operationally-narrow members directory the admin will
spend most time in. This step is the second non-placeholder destination in the
admin nav and establishes the CRUD-list pattern future sub-pages (Plans,
Trainers, etc.) will follow. A new optional `mobile` column on `members` is
introduced so admins can capture a phone number at registration without
needing the member to fill out a profile first.

## Depends on
- Step 01 — Footer (`3dd4536`).
- Step 02 — Admin Dashboard layout, including the dict-shaped `ADMIN_NAV_ITEMS`
  and the shared `_admin_tabs.html` partial.
- Step 03 — Admin Settings (`b527d60`, merged in `7ad96b0`) — the `Settings`
  endpoint pattern (`endpoint='admin_settings'`) is what the new `Members`
  entry will mirror.
- Existing auth scaffolding: `admin_required`, `_valid_csrf()`,
  `is_valid_email()`, `is_valid_mobile()`, `werkzeug.security.generate_password_hash`.

## Routes
- `GET /admin/members` — render the members list page (active tab =
  Members) — admin-only.
- `GET /admin/members/new` — render the **Add Member** form — admin-only.
- `POST /admin/members` — create a new member — admin-only.
  - Validates CSRF, server-side validates name/email/mobile/password,
    inserts via `create_member`, PRG-redirects to `/admin/members` with a
    success flash. On duplicate email (`sqlite3.IntegrityError`) flashes a
    specific error and re-renders the form preserving entered values.
- `GET /admin/members/<int:user_id>` — read-only profile detail for one
  member — admin-only. If the id does not exist or belongs to an admin,
  flashes "Member not found." and redirects to `/admin/members`.

No edit/delete routes here. Delete remains in step 03's Settings page.
Edit (name / email / mobile in-place) is deferred to a future step.

## Database changes
- **Schema migration in `init_db()`** — add an idempotent
  `mobile TEXT` column to `members`, mirroring the existing `role`
  migration block:
  ```python
  if not _column_exists(conn, 'members', 'mobile'):
      conn.execute('ALTER TABLE members ADD COLUMN mobile TEXT')
  ```
  Existing rows keep `mobile = NULL`; no other constraints. The seed in
  `seed_db()` is unchanged (still doesn't set mobile).

- **Existing helpers updated to surface `mobile`:**
  - `get_member_by_id(user_id)` — add `mobile` to the SELECT projection.
  - `get_all_members()` — add `mobile` to the SELECT projection.
  - `get_member_by_email(email)` — leave alone (login flow doesn't need it).

- **Two new helpers in `database/db.py`:**
  - `get_members_by_role(role) -> list[Row]`
    - SQL: `SELECT id, name, email, mobile, role, created_at FROM members
      WHERE role = ? ORDER BY created_at DESC`
    - Used by `/admin/members` so admins are filtered out of the list.
  - `create_member(name, email, password_hash, mobile=None) -> int`
    - SQL: `INSERT INTO members (name, email, password_hash, role, mobile)
      VALUES (?, ?, ?, 'user', ?)`
    - Lower-cases email before insert (matches the `seed_db` and login lookup
      conventions). Returns the new row's `lastrowid`. Lets
      `sqlite3.IntegrityError` propagate so the route can flash a
      duplicate-email error.

All helpers use parameterised queries and the existing `get_db()` /
`try…finally close()` pattern.

## Templates
- **Create:**
  - `templates/admin_members.html` — extends `base.html`, loads `dashboard.css`.
    Sections in order:
    1. `{% include "_admin_tabs.html" %}` (Members tab `is-active`).
    2. Page header `<header class="dash-header">` with `<h1>Members</h1>`,
       short subtitle, and a right-aligned `<a class="admin-hero-btn
       admin-hero-btn-ghost" href="{{ url_for('admin_members_new') }}">+ Add
       Member</a>` button (reuses the hero-button styling already in
       `dashboard.css`).
    3. Stats row `<section class="dash-stats">` reusing the existing
       `.stat-card` rules — one card "Total Members" showing `len(members)`.
    4. `<section class="dash-panel">` with `.dash-panel-header` "All members"
       wrapping a `.dash-table-wrap` + `.dash-table` of columns: `#`, `Name`,
       `Email`, `Mobile`, `Joined`, `Actions`. Each row has a single
       `<a class="user-action-btn" href="{{ url_for('admin_member_detail',
       user_id=m.id) }}">View</a>` in the Actions cell.
       Empty state: render the existing `.dash-empty` row when no members
       exist.
  - `templates/admin_member_new.html` — extends `base.html`. Sections:
    1. Tab bar (Members tab still `is-active`).
    2. Heading `<h1>Add member</h1>` + back link.
    3. `<form method="post" action="{{ url_for('admin_members_create') }}"
       class="member-form">` with CSRF input and fields:
       - `name` (text, required, minlength=2, maxlength=100)
       - `email` (email, required, maxlength=150)
       - `mobile` (tel, optional, maxlength=20)
       - `new_password` (password, required, minlength=6, maxlength=200)
       - `confirm_password` (password, required, minlength=6, maxlength=200)
       Submit button `<button class="user-action-btn">Create member</button>`.
       Cancel link returns to `/admin/members`.
       On validation failure the route re-renders this template with
       `prefill={'name': …, 'email': …, 'mobile': …}` so the admin doesn't
       lose typed values. Password fields are NOT prefilled.
  - `templates/admin_member_detail.html` — extends `base.html`. Sections:
    1. Tab bar (Members tab `is-active`).
    2. `<header>` with member name + role pill.
    3. `<dl class="member-profile">` listing: Email, Mobile (or `—` when null),
       Joined (date), Member ID. Read-only.
    4. Footer link "← Back to members".

- **Modify:** none in this step.
  - `templates/admin_dashboard.html` is **not** edited — it iterates
    `nav_items` already, so changing the Members `endpoint` in `app.py`
    automatically activates both the top tab and the bottom quick-link card.
  - `templates/_admin_tabs.html` is unchanged (its `if item.endpoint` branch
    is what renders the active link automatically).

## Files to change
- `app.py`
  - In `ADMIN_NAV_ITEMS`, change the `Members` entry's `endpoint` from `None`
    to `'admin_members'`. No other entries change.
  - Imports: add `get_members_by_role`, `create_member` from `database.db`.
  - Four new route handlers, all decorated with `@admin_required`:
    - `admin_members()` — `GET /admin/members` — calls
      `get_members_by_role('user')`, renders `admin_members.html` with
      `nav_items=ADMIN_NAV_ITEMS`, `members=…`, `active_tab='Members'`.
    - `admin_members_new()` — `GET /admin/members/new` — renders
      `admin_member_new.html` with `prefill={}`, `active_tab='Members'`.
    - `admin_members_create()` — `POST /admin/members` — CSRF check, server
      validation (see Rules), `try/except sqlite3.IntegrityError` → flash
      duplicate-email error, `try/except sqlite3.Error` → flash generic
      error. On success, redirect to `/admin/members`.
    - `admin_member_detail(user_id)` — `GET /admin/members/<int:user_id>` —
      look up via `get_member_by_id`; if missing or `role != 'user'`, flash
      and redirect to `/admin/members`. Otherwise render
      `admin_member_detail.html`.
  - No changes to existing routes, decorators, or security config.

- `database/db.py`
  - Add the `mobile` column migration in `init_db()`.
  - Update `get_member_by_id` and `get_all_members` SELECT lists to include
    `mobile`.
  - Add `get_members_by_role(role)` and `create_member(name, email,
    password_hash, mobile=None)`.

- `static/css/dashboard.css`
  - Add `.member-form` (a vertical form layout for the new-member page).
    Reuses `.user-pw-input` from step 03 for the inputs (rename optional —
    `.user-pw-input` is already a generic dark-themed input style).
  - Add `.member-profile` (a `<dl>` styled as a 2-column key/value grid for
    the detail page).
  - Add a `.dash-header-actions` flex helper so the existing `.dash-header`
    can hold the right-aligned **Add Member** button.
  - All rules use existing CSS variables — **no new hex literals.**

- `static/css/style.css` — no changes.

## Files to create
- `templates/admin_members.html`
- `templates/admin_member_new.html`
- `templates/admin_member_detail.html`

## New dependencies
No new dependencies. Flask, Werkzeug, and stdlib `sqlite3` only.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only (`?` placeholders) for the two new helpers and
  the migration safety check.
- Passwords hashed with `werkzeug.security.generate_password_hash` — never
  stored in plain text. The new-member form's password is hashed in the
  route, before calling `create_member`.
- **Use CSS variables — never hardcode hex** inside any `.member-*`,
  `.dash-*`, `.admin-*`, or `.user-*` rule.
- All templates `{% extends "base.html" %}`.
- Vanilla JS only — no new JS for this step (the form's `required` /
  `minlength` attributes carry the client-side validation; server is
  authoritative).
- All four new routes decorated with `@admin_required`.
- POST route starts with `if not _valid_csrf(request.form.get('csrf_token')): abort(403)`.
- Server-side validation of the **Add Member** form:
  - `name`: strip → required, length ∈ [2, 100].
  - `email`: strip + lower → required, length ≤ 150, `is_valid_email(email)`.
  - `mobile`: strip → optional; if provided, length ≤ 20 and
    `is_valid_mobile(mobile)`.
  - `new_password`: required, length ∈ [6, 200].
  - `confirm_password`: required, must equal `new_password`.
  - Each failure flashes a specific error and re-renders
    `admin_member_new.html` with the typed values (excluding passwords) in
    `prefill`.
- Email storage and lookup are case-insensitive (the `members.email` column
  is already `COLLATE NOCASE`). Always lower-case before insert/comparison.
- Duplicate email handled at the DB layer: `create_member` lets
  `sqlite3.IntegrityError` propagate; the route catches it and flashes
  "An account with that email already exists." (no stack trace).
- New member's role is hard-coded to `'user'` in `create_member`. To
  promote them, the admin uses the Settings page from step 03.
- Detail-page lookup that returns no row OR a row whose `role != 'user'`
  flashes "Member not found." and redirects — admins are not browsable from
  the Members page (use Settings instead).
- The Members tab is now `endpoint='admin_members'` in `ADMIN_NAV_ITEMS`. The
  bottom quick-links card on `/admin/dashboard` automatically becomes
  navigable. The `_admin_tabs.html` partial filters Settings out of the top
  bar (per the previous step's tweak); Members is unaffected by that filter
  and renders in the top tab bar at position 1.
- No inline `onclick` / `onsubmit` (CSP `script-src 'self'`).
- Errors logged via `app.logger.exception`; users see generic flash text
  only.

## Definition of done
- [ ] `python theroyalgym/app.py` boots cleanly on port 5001 with no
      console errors and no Jinja2 warnings.
- [ ] `PRAGMA table_info(members);` (via `sqlite3 gym.db`) lists a
      `mobile TEXT` column. Existing seeded rows keep `mobile IS NULL`.
- [ ] Logged in as `lakhan@admin.com` / `123456`:
  - [ ] The top admin tab bar's **Members** entry is a real link
        (no `aria-disabled`) pointing at `/admin/members`.
  - [ ] The bottom quick-link card **Members** is a real link too.
  - [ ] Visiting `/admin/members` renders 200 with: tab bar (Members tab
        `is-active`), page header with `+ Add Member` button, "Total Members"
        stat card showing `1`, and a table containing exactly one row for
        `ansh@member.com` (admins are filtered out).
- [ ] **Add Member happy path** — `/admin/members/new` renders the form;
      submitting valid name/email/mobile/passwords creates the row
      (verified via `sqlite3 gym.db "SELECT name, email, mobile, role FROM
      members WHERE email='new@member.com';"`), redirects to
      `/admin/members`, and the new row appears in the table with the
      success flash.
- [ ] **Add Member duplicate email** — submitting an email that already
      exists (e.g. `ansh@member.com`) re-renders the form with an error
      flash, retains the typed name/email/mobile, and does **not** create
      a duplicate (DB row count unchanged).
- [ ] **Add Member validation errors** — each of the following re-renders
      the form with a specific error and creates no row:
  - [ ] empty name
  - [ ] invalid email format
  - [ ] mobile that fails `is_valid_mobile` (e.g. `abc`)
  - [ ] `new_password` length 5
  - [ ] `confirm_password` != `new_password`
- [ ] **CSRF rejection** — `curl -X POST /admin/members` with a valid
      session cookie but no CSRF token returns 403, no row created.
- [ ] **Detail page** — `/admin/members/<id-of-ansh>` renders the read-only
      profile (name, email, mobile or `—`, joined date, member id, role
      pill = `user`). The "Back to members" link works.
- [ ] **Detail page guard** — `/admin/members/<id-of-lakhan>` (an admin)
      flashes "Member not found." and redirects to `/admin/members`.
- [ ] **Detail page 404 path** — `/admin/members/9999` (non-existent id)
      flashes the same and redirects.
- [ ] **Anonymous** — visiting `/admin/members` or `/admin/members/new`
      redirects to `/login`.
- [ ] **Member access** — `ansh@member.com` visiting `/admin/members`
      returns 403.
- [ ] **Login still works** — the new `mobile` column does not break the
      existing login flow (verify by logging in as ansh).
- [ ] At 1440px viewport: table renders inline, action button right-aligned
      in header. At 768px: the form stacks vertically; the table scrolls
      horizontally without page overflow.
- [ ] `curl -s -D - -o /dev/null http://127.0.0.1:5001/admin/members`
      (logged in as admin) returns CSP, X-Frame-Options,
      X-Content-Type-Options, Referrer-Policy headers.
- [ ] **No new hex literals** inside any `.member-*`, `.dash-*`, `.admin-*`,
      or `.user-*` rule. Verify via:
      ```powershell
      git diff main..HEAD -- static/css/dashboard.css `
        | Select-String '^\+' | Select-String -NotMatch '^\+\+\+' `
        | Select-String '#[0-9a-fA-F]{3,6}\b'
      ```
      Output must be empty.
- [ ] **No inline event handlers** in any new template (`Select-String
      'on(click|submit)=' templates/admin_member*.html` returns nothing).
- [ ] `/`, `/login`, `/terms`, `/admin/dashboard`, `/admin/settings`,
      `/member/dashboard`, `/this-route-does-not-exist` all render exactly
      as before — only the Members surface is added.
- [ ] `git diff main..HEAD --name-only` lists exactly: `app.py`,
      `database/db.py`, `static/css/dashboard.css`,
      `templates/admin_members.html`, `templates/admin_member_new.html`,
      `templates/admin_member_detail.html`,
      `.claude/specs/04-create-members-page.md`. No other paths.

## Open questions
- **Edit member** — current spec defers in-place edit (name / email /
  mobile). Alternative: include an `/admin/members/<id>/edit` POST in this
  step. Going without to keep step 04 focused on list + create + view; edit
  becomes step 05 if the demand surfaces.
- **Mobile required vs optional** — current spec is optional (NULL allowed,
  no validation when empty). Alternative: make required for new members.
  Going optional to avoid blocking the admin who only knows email.
- **Stats banner scope** — current spec is one card ("Total Members").
  Alternatives: also show "New this week", "Active subscriptions". Both
  require schema we don't have yet; keeping to the one card.
- **Detail page surface** — current spec shows email, mobile, joined,
  member id. Alternatives: also show last login timestamp (no column),
  membership plan (no table), recent payments (no table). Each is its own
  future step.
- **Reusing `.user-pw-input` for the form** — the class lives in step 03's
  Settings page. Reusing it for the Members new-member form keeps style
  consistent without renaming. Alternative: rename to `.member-form-input`
  and have Settings use the same. Going with reuse for now; cosmetic
  rename can happen if a third caller appears.
