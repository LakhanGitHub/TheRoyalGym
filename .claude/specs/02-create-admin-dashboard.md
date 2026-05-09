# Spec: Create Admin Dashboard

## Overview
Replace the current minimal admin dashboard scaffold (a header + three stat cards + two
tables) with a Figma-aligned operational console. The new layout introduces an
**admin tab bar** (placeholder navigation strip with 10 future-feature tabs), a
**gradient hero card** ("Overview & Controls" with two action buttons), a **metric
tile grid** of seven KPI tiles (Total Members, Total Trainers, Today Registrations,
Subscription Expire This Month, Men, Women, Birthday Today), and a **quick-links
section** at the bottom that mirrors the top tab bar so admins can jump to any feature
from anywhere on the page. The existing Members and Enquiries tables are preserved
beneath the new chrome so this step is purely additive on the data side.

This step is **visual-redesign only**. Operational features (delete member, enquiry
status workflow, search, pagination, bulk actions) are explicitly deferred to a later
step. The objective here is to get the admin's information-architecture right before
wiring up actions.

## Depends on
- Initial Flask scaffold and `base.html` layout (already shipped in `5db9bed`).
- Code-review hardening pass — CSRF helpers, `admin_required` decorator, security
  headers (already shipped in `1860712`).
- Step 01 footer (already shipped in `3dd4536`) — admin dashboard inherits the new
  footer for free; no footer changes here.

This is step 02 of the roadmap. Subsequent steps will add the per-feature admin
sub-pages (Members CRUD, Plans, Trainers, Payments, Attendance, Diet, Equipment,
Enquiries detail, Workout Plans, Feedback) and operational features.

## Out of scope
- **All operational actions on the dashboard** — no delete member, no enquiry status
  toggle, no search filter, no pagination, no bulk actions. These belong to a future
  step.
- **All 10 admin sub-pages** — Members, Plans, Trainers, Payments, Attendance, Diet,
  Equipment, Enquiries (detail page), Workout Plans, Feedback. Tabs and quick-links
  point to placeholder `href="#"` until each respective spec ships.
- **New schema** — no `gender`, `date_of_birth`, `subscription_end_date` columns on
  `members`; no `trainers` table; no `payments` table. Tiles whose data depends on
  these schema additions display `0` for now.
- **Real "Add Member" / "Record Payment" forms** — the two hero buttons are visual
  placeholders only (see Open Questions for the exact form they take).
- **Real-time updates** — no WebSocket / SSE / polling. The dashboard is plain
  request/response.
- **Charts or time-series widgets** beyond the seven KPI tiles.
- **Export to CSV / PDF / print stylesheet** — not in this step.
- **Tab "active" state machinery** — only the implicit "Dashboard" position is
  active. Future specs add `is-active` toggling per sub-page.

## Routes

- `GET /admin/dashboard` — **modify** existing route — admin-only.
  - Continues to use `@admin_required` decorator from `app.py`.
  - Renders `admin_dashboard.html` with these template variables:
    - `members` — `get_all_members()` (existing helper, unchanged).
    - `enquiries` — `get_all_enquiries()` (existing helper, unchanged).
    - `nav_items` — the shared list of 10 admin sections (single source of truth so
      the top tab bar and the bottom quick-links cannot drift).
    - `metrics` — a dict with seven keys: `total_members`, `total_trainers`,
      `today_registrations`, `subscription_expiring`, `men`, `women`,
      `birthday_today`. Real values for `total_members` and `today_registrations`;
      the other five are literally `0` (sourced from a Python placeholder, not from
      the DB).

**No new routes.** No new POST endpoints in this step.

## Database changes

- **No schema changes.** No new tables, columns, or constraints.

- **One new helper** in `database/db.py`:
  - `count_members_registered_today() -> int`
  - SQL: `SELECT COUNT(*) FROM members WHERE date(created_at) = date('now', 'localtime')`
  - Parameterised (no user input flows in). Returns the integer count.
  - Use the existing `get_db()` connection pattern; close the connection in `finally`.

## Templates

- **Create:** None.

- **Modify:**
  - `templates/admin_dashboard.html` — full rewrite of layout. Final structure:

    1. **Admin tab bar** — `<nav class="admin-tabs" aria-label="Admin sections">`
       containing a horizontal `<ul>` of 10 `<li><a class="admin-tab" href="#"
       aria-disabled="true">{{ item }}</a></li>` items, iterating over `nav_items`.
       The first tab is implicitly "active" (Dashboard) — render it with
       `class="admin-tab is-active"` and **omit the placeholder Dashboard from the
       `nav_items` list itself**, since the user is already on it. Tab order:
       Members, Plans, Trainers, Payments, Attendance, Diet, Equipment, Enquiries,
       Workout Plans, Feedback.

    2. **Hero card** — `<section class="admin-hero">` with:
       - `<h1 class="admin-hero-title">Overview & Controls</h1>`
       - `<p class="admin-hero-subtitle">Manage members, memberships, registrations,
         payments, attendance and more</p>`
       - `<div class="admin-hero-actions">` containing two buttons (see Open
         Questions for the exact element — current decision: rendered as
         `<button type="button" class="admin-hero-btn admin-hero-btn-primary"
         disabled aria-disabled="true">Add Member</button>` and a matching ghost
         variant for "Record Payment". Disabled until those routes exist.

    3. **Tile grid** — `<section class="dash-tiles">` containing seven tiles. Each
       tile is a `<article class="dash-tile">` with:
       - `<span class="dash-tile-icon" aria-hidden="true">…inline SVG…</span>`
       - `<h2 class="dash-tile-label">{{ label }}</h2>`
       - `<div class="dash-tile-value">{{ metrics[key] }}</div>`
       - `<a class="dash-tile-link" href="#" aria-disabled="true">Details</a>`

       Tile order and source key:
       | # | Label | Metrics key | Value source |
       |---|---|---|---|
       | 1 | Total Members | `total_members` | `len(members)` |
       | 2 | Total Trainers | `total_trainers` | `0` (placeholder) |
       | 3 | Today Registrations | `today_registrations` | `count_members_registered_today()` |
       | 4 | Subscription Expire This Month | `subscription_expiring` | `0` (placeholder) |
       | 5 | Men | `men` | `0` (placeholder) |
       | 6 | Women | `women` | `0` (placeholder) |
       | 7 | Birthday Today | `birthday_today` | `0` (placeholder) |

    4. **Quick-links section** — `<section class="dash-quicklinks-section">`:
       - `<h2 class="dash-quicklinks-heading">Quick Links</h2>`
       - `<nav class="dash-quicklinks" aria-label="Admin quick links">` containing
         a grid of `<a class="dash-quicklink" href="#"
         aria-disabled="true">{{ item }}</a>` items. **Iterates over the same
         `nav_items` list** used by the top tab bar, guaranteeing the labels stay
         in lock-step.

    5. **Members table** — kept as-is from the current dashboard. Column set
       unchanged: `#`, `Name`, `Email`, `Role`, `Joined`. Existing classes
       (`.dash-panel`, `.dash-panel-header`, `.dash-table-wrap`, `.dash-table`,
       `.role-pill`) remain.

    6. **Enquiries table** — kept as-is from the current dashboard. Column set
       unchanged: `#`, `Name`, `Email`, `Mobile`, `Message`, `Date`. No status
       column added in this step.

  - `templates/base.html` — **no changes.** The global navbar is unchanged. The
    admin tab bar lives inside `admin_dashboard.html`, not in `base.html`, so
    other pages stay clean.

## Files to change
- `app.py`
  - Add a module-level constant `ADMIN_NAV_ITEMS = ['Members', 'Plans', 'Trainers',
    'Payments', 'Attendance', 'Diet', 'Equipment', 'Enquiries', 'Workout Plans',
    'Feedback']`.
  - Import `count_members_registered_today` from `database.db`.
  - Modify `admin_dashboard()` to build the `metrics` dict and pass `nav_items` and
    `metrics` to `render_template`.
  - No other changes to `app.py` — security headers, decorators, CSRF helpers all
    untouched.

- `database/db.py`
  - Add the `count_members_registered_today()` helper described in **Database
    changes**.
  - Export it (no `__all__` in this module today; just make sure `app.py` can import
    it).

- `templates/admin_dashboard.html`
  - Full rewrite of the `{% block content %}` body per **Templates** above.
  - Continues to extend `base.html` and continues to load `dashboard.css` via
    `{% block extra_css %}`.

- `static/css/dashboard.css`
  - Add new classes for the admin tab bar, hero, tile grid, and quick links (full
    list in **CSS additions** below).
  - Use existing CSS variables only. No raw hex inside any `.admin-*` or `.dash-*`
    rule.
  - Keep the existing `.dash-section`, `.dash-container`, `.dash-header`,
    `.stat-card`, `.dash-panel`, `.dash-table`, `.role-pill`, `.dash-empty` rules
    intact — Members and Enquiries tables continue to use them. The legacy
    `.dash-stats` / `.stat-card` rules remain in place but are no longer rendered
    in the admin template (they may still be rendered by `member_dashboard.html` —
    do **not** delete them).

## Files to create
None.

## New dependencies
No new dependencies. Flask, Werkzeug, and stdlib `sqlite3` only — same as today.

## CSS additions (`static/css/dashboard.css`)

All new classes use only variables already defined in `:root` of `style.css`:
`--accent-gold`, `--accent-gold-hover`, `--surface`, `--surface-2`, `--body-bg`,
`--text-primary`, `--text-secondary`, `--text-muted`, `--border-color`,
`--radius-sm`, `--radius-md`, `--radius-lg`, `--shadow-sm`, `--shadow-md`,
`--shadow-lg`, `--t`, `--font`, `--white`.

- `.admin-tabs` — flex row, horizontally scrollable on overflow, sticky below the
  navbar at `top: var(--nav-h)`, background `var(--surface)`, bottom border
  `1px solid var(--border-color)`, padding around the row, full-bleed inside
  `.dash-container`.
- `.admin-tab` — pill-style anchor: padding, `border-radius: var(--radius-sm)`,
  color `var(--text-secondary)`, transition `var(--t)`, no underline. Hover:
  color `var(--accent-gold)`; underline via `box-shadow: inset 0 -2px 0 0
  var(--accent-gold)` (no separate `border-bottom` to avoid layout shift).
- `.admin-tab.is-active` — color `var(--accent-gold)`, persistent gold underline
  using the same inset `box-shadow` rule.
- `.admin-tab[aria-disabled="true"]` — `cursor: not-allowed`, `opacity: .85` on
  hover; suppress the underline.
- `.admin-hero` — full-width banner with
  `background: linear-gradient(135deg, var(--accent-gold), var(--accent-gold-hover))`,
  color `var(--body-bg)` (dark text on gold gradient for contrast), padding,
  `border-radius: var(--radius-lg)`, `box-shadow: var(--shadow-md)`. Flex layout:
  text on the left, action buttons on the right.
- `.admin-hero-title` — large, weight 700, color `var(--body-bg)`.
- `.admin-hero-subtitle` — color `rgba(13,13,13,.78)` — **NOTE:** this is the only
  near-hex value, expressed as `rgba()` over the existing `--body-bg` value. To stay
  hex-free inside `.admin-*` rules, declare a new variable `--admin-hero-text-soft:
  rgba(13,13,13,.78)` in `:root` and reference it via `var(--admin-hero-text-soft)`.
- `.admin-hero-actions` — flex row, gap, wraps on small viewports.
- `.admin-hero-btn` — base button: padding, `border-radius: var(--radius-sm)`,
  font-weight 600, transition, no border by default.
- `.admin-hero-btn-primary` — `background: var(--white)`, color `var(--body-bg)`,
  hover lifts via `box-shadow: var(--shadow-md)`.
- `.admin-hero-btn-ghost` — transparent background, `border: 1.5px solid
  var(--white)`, color `var(--white)`, hover swaps to white background and dark text.
- `.admin-hero-btn[disabled]` — `cursor: not-allowed`, `opacity: .65`, no hover
  effects.
- `.dash-tiles` — `display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;
  margin-block: 28px;`.
- `.dash-tile` — `background: var(--surface)`, border `1px solid var(--border-color)`,
  `border-radius: var(--radius-md)`, padding, transition. Hover lifts via
  `transform: translateY(-2px); box-shadow: var(--shadow-md);`.
- `.dash-tile-icon` — flex-aligned, color `var(--accent-gold)`, line-height 0.
- `.dash-tile-label` — color `var(--text-secondary)`, font-size `0.875rem`,
  font-weight 500, margin 0.
- `.dash-tile-value` — color `var(--text-primary)`, font-size `2.25rem`,
  font-weight 700, margin-block `8px`.
- `.dash-tile-link` — small ghost link, color `var(--accent-gold)`, hover
  underlines. Honour `aria-disabled="true"` with `cursor: not-allowed; opacity:
  .55;`.
- `.dash-quicklinks-section` — `margin-block: 36px`.
- `.dash-quicklinks-heading` — color `var(--text-primary)`, font-size `1.1rem`,
  font-weight 600, margin-bottom `14px`.
- `.dash-quicklinks` — `display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 12px;`.
- `.dash-quicklink` — `background: var(--surface-2)`, border `1px solid
  var(--border-color)`, `border-radius: var(--radius-sm)`, padding, color
  `var(--text-secondary)`, text-align center, transition. Hover: color
  `var(--accent-gold)`, border-color `var(--accent-gold)`.
- `.dash-quicklink[aria-disabled="true"]` — cursor not-allowed; reduced contrast.

Responsive breakpoints (in the same file, after the new rules):

- `@media (max-width: 1024px)`:
  - `.dash-tiles { grid-template-columns: repeat(2, 1fr); }`
  - `.dash-quicklinks { grid-template-columns: repeat(3, 1fr); }`
  - `.admin-hero { flex-direction: column; align-items: flex-start; }`
- `@media (max-width: 640px)`:
  - `.dash-tiles { grid-template-columns: 1fr; }`
  - `.dash-quicklinks { grid-template-columns: repeat(2, 1fr); }`
  - `.admin-tabs { overflow-x: auto; -webkit-overflow-scrolling: touch; }`
  - `.admin-hero-actions { width: 100%; }`
  - `.admin-hero-btn { flex: 1 1 0; }`

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only — the new `count_members_registered_today()` uses
  `date('now', 'localtime')` inline (no user input flows in).
- Passwords hashed with werkzeug — unchanged in this step.
- **Use CSS variables — never hardcode hex values inside any `.admin-*` or
  `.dash-*` rule.** If a new colour is genuinely needed (e.g., the hero subtitle
  near-black `rgba` value), declare it as a `--…` variable in `:root` of
  `style.css` first, then reference via `var(--…)`.
- All templates extend `base.html`.
- Vanilla JS only — no frameworks. **No new JS for this step** (the dashboard is
  static markup; tab/link clicks resolve to `href="#"` placeholders). Do **not**
  edit `static/js/main.js`.
- No inline `onclick` / `onsubmit` handlers (CSP `script-src 'self'`).
- The `nav_items` Python list is the single source of truth for the 10 admin
  section names. The top tab bar and bottom quick-links must both iterate over it
  — never hardcode the labels in the template.
- The implicit "Dashboard" tab is rendered separately (with `is-active` class)
  before the `{% for item in nav_items %}` loop, so `nav_items` does **not**
  contain "Dashboard".
- Action buttons in the hero (`Add Member`, `Record Payment`) render as
  `<button type="button" disabled aria-disabled="true">` until the relevant routes
  exist. Do not introduce placeholder `POST` routes that flash "coming soon" —
  cleaner to keep the buttons disabled.
- Inline SVGs use `currentColor` for stroke / fill so they inherit
  `var(--accent-gold)` from `.dash-tile-icon` via the parent's `color`.
- All decorative SVGs include `aria-hidden="true"`.
- The admin tab bar uses `<nav aria-label="Admin sections">` and the quick-links
  block uses `<nav aria-label="Admin quick links">` for assistive tech.

## Open questions
- **"Add Member" / "Record Payment" buttons** — current spec says render as
  `<button type="button" disabled aria-disabled="true">`. Alternative: render as
  forms `POST`-ing to placeholder routes that flash "Coming soon" and redirect
  back. The disabled-button approach was chosen because it requires no new routes,
  no new CSRF tokens, and no flash noise on every accidental click.
- **Tile icons** — proposed Tabler-style monoline SVGs:
  - Total Members → `users` (group of three figures).
  - Total Trainers → `whistle` or `barbell`.
  - Today Registrations → `user-plus`.
  - Subscription Expire This Month → `calendar-clock`.
  - Men → `gender-male` (Mars symbol).
  - Women → `gender-female` (Venus symbol).
  - Birthday Today → `cake`.
  Final SVG paths chosen from [Tabler Icons](https://tabler.io/icons) (MIT).
- **`--admin-hero-text-soft` variable** — the only near-hex addition required by
  the hero subtitle. Confirm naming convention (`--admin-hero-text-soft` vs
  `--text-on-gold`) before declaring.
- **Tab bar "Dashboard" label** — current decision: render the active first tab
  as literally "Dashboard". Alternative: omit it entirely and rely on the global
  navbar's "Admin Dashboard" link to indicate location. Going with the explicit
  Dashboard tab for visual symmetry with the reference image.

## Definition of done
- [ ] `python theroyalgym/app.py` starts cleanly on port 5001 with no console
      errors and no Jinja2 warnings.
- [ ] Logging in as admin (`lakhan@admin.com` / `123456`) and visiting
      `http://127.0.0.1:5001/admin/dashboard` shows, top to bottom: global navbar →
      admin tab bar → "Overview & Controls" hero → seven tiles → "Quick Links"
      heading + 10 quick-link cards → Members table → Enquiries table → footer
      (from step 01).
- [ ] **Total Members** tile shows `SELECT COUNT(*) FROM members` (cross-check via
      `sqlite3 gym.db "SELECT COUNT(*) FROM members;"`).
- [ ] **Today Registrations** tile shows the correct count: insert a member with
      `created_at` = today via the SQLite CLI and confirm the tile increments by 1
      after a page refresh.
- [ ] **Total Trainers**, **Subscription Expire This Month**, **Men**, **Women**,
      **Birthday Today** tiles each display `0`.
- [ ] The string **"Subscription Expire This Month"** appears verbatim as a tile
      label (literal copy match — no variant casing or wording).
- [ ] All 10 top tabs render in the order: Members, Plans, Trainers, Payments,
      Attendance, Diet, Equipment, Enquiries, Workout Plans, Feedback. Each has
      `href="#"` and `aria-disabled="true"`.
- [ ] An additional 11th tab labelled "Dashboard" renders before the 10 above with
      `class="admin-tab is-active"`.
- [ ] All 10 quick-link cards at the bottom render with the same labels and order
      as the top tabs (sourced from the same Python list — verify by changing one
      label in `ADMIN_NAV_ITEMS` and confirming both top and bottom update on
      refresh).
- [ ] Hero buttons "Add Member" and "Record Payment" render as `<button
      disabled aria-disabled="true">` and produce no network request when clicked.
- [ ] At 1440 px viewport: tiles render 4-up; quick-links render 5-up; tab bar
      fits without scrolling.
- [ ] At 1024 px viewport: tiles render 2-up; quick-links render 3-up; hero stacks
      title above buttons.
- [ ] At 600 px viewport: tiles render 1-up; quick-links render 2-up; tab bar
      becomes horizontally scrollable; no horizontal page overflow.
- [ ] Member account (role=`user`) visiting `/admin/dashboard` receives 403.
- [ ] Anonymous user visiting `/admin/dashboard` is redirected to `/login`.
- [ ] `curl -s -D - -o /dev/null http://127.0.0.1:5001/admin/dashboard` (logged in
      as admin) still returns all security headers from the previous step (CSP,
      X-Frame-Options, X-Content-Type-Options, Referrer-Policy).
- [ ] `/`, `/login`, `/member/dashboard`, `/terms`, `/this-route-does-not-exist`
      all render unchanged — only the admin dashboard layout is altered.
- [ ] Footer from step 01 (multi-column layout, social icons, bottom bar) renders
      below the dashboard tables exactly as on other pages.
- [ ] **No new hardcoded hex values inside any `.admin-*` or `.dash-*` rule.**
      Verify via:
      ```powershell
      git diff main..HEAD -- static/css/dashboard.css `
        | Select-String '^\+' | Select-String -NotMatch '^\+\+\+' `
        | Select-String '#[0-9a-fA-F]{3,6}\b'
      ```
      Output must be empty (or contain only new `--…` variable declarations under
      `:root` in `style.css`).
- [ ] DevTools accessibility check: every decorative SVG has `aria-hidden="true"`;
      tab bar uses `<nav aria-label="Admin sections">`; quick-links uses
      `<nav aria-label="Admin quick links">`; disabled tabs/links carry
      `aria-disabled="true"`.
- [ ] `git diff main..HEAD --name-only` lists exactly: `app.py`,
      `database/db.py`, `templates/admin_dashboard.html`,
      `static/css/dashboard.css`, `.claude/specs/02-create-admin-dashboard.md`,
      and (if used) `static/css/style.css` for the new `--admin-hero-text-soft`
      variable. No other paths.
- [ ] follow the tile order:
      1-Total Members 
      2-today Registrations
      3-Active Membership
      4-men
      5-wonmen
      6-Subscription Expire This Month.
