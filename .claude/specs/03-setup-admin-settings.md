# Spec: Setup Admin Settings

## Overview
Adds an admin-only **Settings** page at `/admin/settings` that lets an admin
operate on user accounts: view every account (admins + members) with role and
join date, promote a member to admin, demote an admin back to member, reset any
user's password (admin-initiated, no email flow), and delete a user. This is
the first non-placeholder destination for the admin tab bar introduced in step
02 — wiring up the Settings tab end-to-end establishes the pattern that all
future admin sub-pages (Members, Plans, Trainers, …) will follow. The existing
`members.role` column is sufficient; no schema changes are needed. Every
destructive action is gated by CSRF, server-side self-targeting checks, a
last-admin guard, and a vanilla-JS `confirm()` prompt.

The user described the actor as a "super-admin", but the existing role schema
only has `admin` and `user` — `admin` is treated as the super-admin for this
spec. A separate super-admin tier is out of scope.

## Depends on
- Step 01 — Footer (`3dd4536`).
- Step 02 — Admin Dashboard layout, including the admin tab bar and
  `ADMIN_NAV_ITEMS` (`a4bb8f5`, merged in `cf480e9`).
- Existing auth scaffolding: `admin_required` decorator, `_valid_csrf()`
  helper, `members.role` column, werkzeug password hashing — all already in
  `app.py` / `database/db.py`.

## Routes
- `GET /admin/settings` — render the user-management page — admin-only.
- `POST /admin/settings/users/<int:user_id>/role` — flip the target user's
  role (`admin` ↔ `user`). Rejects self-targeting and last-admin demotion.
  Admin-only.
- `POST /admin/settings/users/<int:user_id>/password` — set the target user's
  password to an admin-supplied value. Hashes via werkzeug. Admin-only.
- `POST /admin/settings/users/<int:user_id>/delete` — delete the target user.
  Rejects self-targeting. Admin-only.

All POSTs validate CSRF, require an admin session, and PRG-redirect back to
`/admin/settings` with a flash message.

## Database changes
No schema changes. `members` already carries `role` and `password_hash`.

**New helpers in `database/db.py`:**
- `update_member_role(user_id, new_role) -> None`
  - `UPDATE members SET role = ? WHERE id = ?`
  - Raises `ValueError` if `new_role not in ('admin', 'user')` so app-layer
    bugs surface fast.
- `update_member_password(user_id, new_hash) -> None`
  - `UPDATE members SET password_hash = ? WHERE id = ?`
- `delete_member(user_id) -> None`
  - `DELETE FROM members WHERE id = ?`
  - SQLite FK enforcement is on (set in `get_db()`); when future tables add
    user-scoped FKs (payments, attendance, etc.) they must declare
    `ON DELETE CASCADE` or be cleaned up here. For step 03, only the `members`
    row is removed — `enquiries` has no FK to `members`, so it's untouched.
- `count_admins() -> int`
  - `SELECT COUNT(*) FROM members WHERE role = 'admin'` — used by the
    last-admin guard.

All four use parameterised queries and the existing `get_db()` /
`try…finally close()` pattern.

## Templates
- **Create:**
  - `templates/admin_settings.html` — extends `base.html`, loads
    `dashboard.css` via `{% block extra_css %}`. Structure:
    1. Admin tab bar (reuses `.admin-tabs` / `.admin-tab` from step 02) — the
       Settings tab is rendered with `class="admin-tab is-active"`.
    2. Page heading: `<h1>User Management</h1>` + short subtitle.
    3. Flash region inherited from `base.html` (no change).
    4. `<section class="dash-panel">` containing:
       - `.dash-panel-header` with the heading "All users".
       - `.dash-table-wrap` + `.dash-table` columns: `#`, `Name`, `Email`,
         `Role` (existing `.role-pill` styles), `Joined`, `Actions`.
    5. Each row's `Actions` cell renders three forms inline inside
       `<div class="user-actions">`:
       - Role-toggle form — `<form method="post"
         action="{{ url_for('admin_settings_role', user_id=u.id) }}"
         data-confirm="…">` with CSRF token + a single button labelled
         "Make admin" or "Demote to user" depending on current role.
       - Password-reset trigger — a `<details>` element whose summary opens an
         inline `<form>` with `new_password` + `confirm_password` inputs and a
         submit button. (No JS needed for `<details>`.)
       - Delete form — `<form method="post"
         action="{{ url_for('admin_settings_delete', user_id=u.id) }}"
         data-confirm="…">` with CSRF token + delete button.
    6. The current admin's own row: every action button rendered as
       `<button … disabled aria-disabled="true">` and the `<details>`
       element is omitted — server-side checks back this up.

- **Modify:**
  - `templates/admin_dashboard.html` — update the `{% for item in nav_items %}`
    blocks (top tab bar + bottom quick-links) to handle the new
    dict-shaped nav items (see `app.py` change). For each item:
    - `href="{{ url_for(item.endpoint) if item.endpoint else '#' }}"`
    - drop `aria-disabled` when `item.endpoint` is set
    - keep `aria-disabled="true"` when `item.endpoint` is `None`
    No visual change to the dashboard — only the Settings tab/quick-link
    becomes navigable; the other 10 remain placeholders.
  - `templates/base.html` — **no changes.**

## Files to change
- `app.py`
  - Convert `ADMIN_NAV_ITEMS` from `list[str]` to `list[dict]`:
    ```python
    ADMIN_NAV_ITEMS = [
        {'label': 'Members',       'endpoint': None},
        {'label': 'Plans',         'endpoint': None},
        {'label': 'Trainers',      'endpoint': None},
        {'label': 'Payments',      'endpoint': None},
        {'label': 'Attendance',    'endpoint': None},
        {'label': 'Diet',          'endpoint': None},
        {'label': 'Equipment',     'endpoint': None},
        {'label': 'Enquiries',     'endpoint': None},
        {'label': 'Workout Plans', 'endpoint': None},
        {'label': 'Feedback',      'endpoint': None},
        {'label': 'Settings',      'endpoint': 'admin_settings'},
    ]
    ```
    11 items now. Settings is the only non-placeholder.
  - Import `get_member_by_id`, `update_member_role`, `update_member_password`,
    `delete_member`, `count_admins` from `database.db` (the first is already
    imported).
  - Add four new route handlers, all decorated with `@admin_required`:
    - `admin_settings()` — `GET /admin/settings` — calls `get_all_members()`
      and renders `admin_settings.html` with `nav_items=ADMIN_NAV_ITEMS`,
      `users=...`, `current_user_id=session['user_id']`.
    - `admin_settings_role(user_id)` — `POST` — validates CSRF, rejects
      `user_id == session['user_id']` (flash error), looks up the target's
      current role, computes the new role, and if demoting calls
      `count_admins()` to ensure at least one admin remains. Calls
      `update_member_role` and flashes success/error.
    - `admin_settings_password(user_id)` — `POST` — validates CSRF, reads
      `new_password` and `confirm_password` from the form, validates length
      (6–200 chars) and equality, hashes via
      `generate_password_hash`, calls `update_member_password`, flashes
      success/error. Self-targeting is allowed here (admin can reset their
      own password).
    - `admin_settings_delete(user_id)` — `POST` — validates CSRF, rejects
      self-targeting (flash error), calls `delete_member`, flashes
      success/error.
  - Each POST handler ends with `return redirect(url_for('admin_settings'))`
    (PRG pattern).
  - Import `generate_password_hash` from `werkzeug.security`.

- `database/db.py`
  - Add the four helpers (`update_member_role`, `update_member_password`,
    `delete_member`, `count_admins`).
  - No changes to existing helpers.

- `templates/admin_dashboard.html`
  - Update the two `{% for item in nav_items %}` blocks to handle the dict
    shape (resolve `item.endpoint` to a URL when set; placeholder otherwise).
    Apply the same change to **both** the top `.admin-tabs` block and the
    bottom `.dash-quicklinks` block — they iterate the same list per step 02.

- `static/css/dashboard.css`
  - Add `.user-actions` (flex row, gap, wrap) for the actions column.
  - Add `.user-action-btn` (base small-button class — reusing existing
    button-radius and padding tokens) and `.user-action-btn-danger` (red
    accent for the delete button — uses a new `--danger` variable; see
    `static/css/style.css` change below).
  - Add `.user-pw-form` (the inline `<details>`-revealed password form —
    `display: grid; gap: 8px;` with `.dash-input` styling on the two
    inputs).
  - Reuse existing `.dash-panel`, `.dash-table`, `.role-pill` rules — no
    duplication.
  - Add the `@media (max-width: 768px)` rule that collapses
    `.user-actions` to `flex-direction: column` so buttons don't squash on
    narrow viewports.
  - **No new hex literals inside any `.user-*`, `.admin-*`, or `.dash-*`
    rule.**

- `static/css/style.css`
  - Add two new `:root` variables for the danger button (red theme so the
    Delete affordance is unambiguous):
    - `--danger: #c0392b`
    - `--danger-hover: #a3301f`
    These are the **only** new hex literals introduced in this step, and they
    live exclusively in `:root`. All `.user-*` rules reference them via
    `var(--danger)` / `var(--danger-hover)`.

- `static/js/main.js`
  - Add a vanilla submit-event handler bound at module load:
    ```js
    document.querySelectorAll('form[data-confirm]').forEach(form => {
      form.addEventListener('submit', e => {
        if (!window.confirm(form.dataset.confirm)) e.preventDefault();
      });
    });
    ```
    CSP-compatible (no inline `onclick`). Used by role-toggle and delete
    forms; password-reset is not gated by `confirm()` because the
    new-password fields are themselves an explicit confirmation.

## Files to create
- `templates/admin_settings.html` — described in **Templates** above.

## New dependencies
No new dependencies. Flask, Werkzeug, and stdlib `sqlite3` only.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only (`?` placeholders) for all four new DB helpers.
- Passwords hashed with `werkzeug.security.generate_password_hash()` — never
  stored in plain text. Existing `check_password_hash` flow in `login()`
  must continue to work after a password reset (verify by logging in as the
  affected user post-reset).
- **Use CSS variables — never hardcode hex values** inside any `.user-*`,
  `.admin-*`, or `.dash-*` rule. The two `--danger…` variables are added in
  `:root` of `style.css` first, then referenced via `var(--…)`.
- All templates `{% extends "base.html" %}`.
- Vanilla JS only — `confirm()`-based UX guard via `data-confirm` attribute,
  bound in `main.js`. No frameworks. No inline `onclick` / `onsubmit`
  handlers (CSP `script-src 'self'`).
- All four new routes decorated with `@admin_required`.
- All POST routes start with `if not _valid_csrf(request.form.get('csrf_token')): abort(403)`.
- Self-targeting rejection (server-side, not just UI):
  - Role-change route: `if user_id == session['user_id']: flash('You cannot change your own role.', 'error'); return redirect(...)`.
  - Delete route: same pattern, message "You cannot delete your own account."
  - Password-reset route: self-targeting **allowed** (admin resets own
    password is a valid operation).
- Last-admin guard: before demoting from `admin` to `user`, call
  `count_admins()`; if it would drop to 0, flash error and redirect.
- Password validation server-side: non-empty, length ∈ [6, 200],
  `new_password == confirm_password`. Mismatches and out-of-range lengths
  flash specific errors and skip the DB write.
- Use `flash(..., 'success' | 'error')` for every action outcome — admin gets
  explicit feedback on every action.
- All decorative SVGs `aria-hidden="true"`; icon-only buttons get
  `aria-label`.
- The admin tab bar on `/admin/settings` renders the Settings tab with
  `class="admin-tab is-active"`. The `Dashboard` literal tab (rendered
  before the loop in step 02) drops its `is-active` on this page — keeping
  exactly one active tab per page.
- After role/password/delete, redirect (PRG) back to `/admin/settings`.
- Logging: catch `sqlite3.Error` around DB writes and call
  `app.logger.exception(...)` + flash a generic "Action failed" — never
  surface stack traces to the user.

## Definition of done
  - [ ] Admin settings page where a super-admin can:
  - View a list of all users (admins and members) with their current role
  - Promote an existing member to admin role
  - Demote an admin back to member role
  - Change any user's password (admin-initiated reset, no email flow)
  - Delete a user entirely (removes all their records)

Rules:
- Only admins can access this page (non-admins get 403)
- An admin cannot delete or demote themselves
- Confirmation required before delete or role change
- [ ] `python theroyalgym/app.py` boots cleanly on port 5001 with no console
      errors and no Jinja2 warnings.
- [ ] `http://127.0.0.1:5001/admin/dashboard` (logged in as
      `lakhan@admin.com` / `123456`) shows the **Settings** tab in both the
      top admin tab bar and the bottom quick-links grid as a real link
      (no `aria-disabled`); clicking it navigates to `/admin/settings`.
- [ ] `/admin/settings` renders a `.dash-panel` with a table listing both
      seeded users (`lakhan@admin.com` / admin and `ansh@member.com` /
      user) with name, email, role pill, joined date, and three action
      affordances per row.
- [ ] On the row for the current admin (`lakhan@admin.com`), all three
      action buttons render with the `disabled` attribute and
      `aria-disabled="true"`; the `<details>` password form is omitted.
- [ ] **Promote** — clicking "Make admin" on `ansh@member.com` shows a JS
      `confirm()` prompt; on accept, the page reloads with a success flash
      and `sqlite3 gym.db "SELECT role FROM members WHERE email='ansh@member.com';"`
      returns `admin`.
- [ ] **Demote** — clicking "Demote to user" on a non-self admin flips
      the role back to `user` and flashes a success message.
- [ ] **Last-admin guard** — with only one admin in the DB, attempting to
      demote that admin via curl with a valid CSRF token is rejected
      (flash error), and the row's role remains `admin` in DB.
- [ ] **Reset password** — submitting mismatched `new_password` /
      `confirm_password` flashes an error and does not change the hash.
      Submitting matching valid-length values flashes success, and the
      target user can log in with the new password (`/login` succeeds).
- [ ] **Reset password length guard** — submitting a 5-char password is
      rejected with an error flash and the hash is unchanged.
- [ ] **Delete user** — clicking "Delete" on `ansh@member.com` triggers a
      JS confirm; on accept, the page reloads with a success flash and
      `sqlite3 gym.db "SELECT COUNT(*) FROM members WHERE email='ansh@member.com';"`
      returns 0.
- [ ] **Self-target rejection (delete)** — `curl -X POST` against
      `POST /admin/settings/users/<self_id>/delete` with a valid session
      cookie and CSRF token returns a redirect with an error flash; the
      admin row remains in the DB.
- [ ] **Self-target rejection (role)** — same curl shape against
      `/role` is rejected with an error flash; admin's role stays `admin`.
- [ ] **CSRF rejection** — any POST to a `/admin/settings/users/...`
      endpoint without a valid `csrf_token` form field returns 403.
- [ ] **Anonymous access** — visiting `/admin/settings` while logged out
      redirects to `/login` with the standard "Please log in" flash.
- [ ] **Member access** — visiting `/admin/settings` as `ansh@member.com`
      (role=`user`) returns 403 (renders `errors/403.html`).
- [ ] At 1440px: actions render on a single row per user.
- [ ] At 768px: actions stack vertically per the new media query; no
      horizontal page overflow.
- [ ] `curl -s -D - -o /dev/null http://127.0.0.1:5001/admin/settings`
      (logged in as admin) returns CSP, X-Frame-Options,
      X-Content-Type-Options, Referrer-Policy headers.
- [ ] **No new hex literals** inside any `.user-*`, `.admin-*`, or
      `.dash-*` rule. Verify via:
      ```powershell
      git diff main..HEAD -- static/css/dashboard.css `
        | Select-String '^\+' | Select-String -NotMatch '^\+\+\+' `
        | Select-String '#[0-9a-fA-F]{3,6}\b'
      ```
      Output must be empty. The two `--danger…` declarations are
      permitted in `static/css/style.css` `:root` only.
- [ ] **No inline event handlers** — `Select-String 'on(click|submit)='
      templates/admin_settings.html` returns nothing.
- [ ] DevTools accessibility check: every decorative SVG has
      `aria-hidden="true"`; the admin tab bar uses
      `<nav aria-label="Admin sections">`; disabled buttons carry
      `aria-disabled="true"`; the role / delete forms carry the
      `data-confirm` attribute.
- [ ] `git diff main..HEAD --name-only` lists exactly: `app.py`,
      `database/db.py`, `templates/admin_settings.html`,
      `templates/admin_dashboard.html`, `static/css/dashboard.css`,
      `static/css/style.css`, `static/js/main.js`,
      `.claude/specs/03-setup-admin-settings.md`. No other paths.

## Open questions
- **Password reset UX** — current decision: inline `<details>` element per
  row reveals a small two-input form. Alternative: dedicated page
  `/admin/settings/users/<id>/password` with its own form. The inline
  approach is denser and avoids an extra route; the dedicated-page
  approach is cleaner if password policy grows (rules display, strength
  meter). Going with inline `<details>` for this step.
- **Confirmation UX** — current decision: vanilla `confirm()` for role
  toggle + delete. Alternative: a two-step page that re-renders with an
  explicit confirm form. `confirm()` is sufficient for an admin-only,
  low-traffic surface and matches the "vanilla JS, no frameworks" rule.
- **Last-admin guard scope** — applied only to demotion, not to deletion.
  An admin could still delete the last admin (their own row), but
  self-deletion is already rejected, so in practice the only admin
  cannot delete themselves either. Documented for future-self.
- **`Settings` tab position** — current decision: 11th and final position
  in `ADMIN_NAV_ITEMS`. Alternative: render Settings outside the tab bar
  (e.g., a gear icon in the navbar). Going with 11th tab — cheapest, and
  the dict-shaped nav items make subsequent specs (Members, Plans, …) a
  one-line change to flip `endpoint: None` → `endpoint: 'admin_members'`.
