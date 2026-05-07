---
name: Routes and auth model
description: All app routes, their auth requirements, and role values used in session
type: project
---

Routes defined in app.py:

| Route                  | Method     | Auth Required | Role        |
|------------------------|------------|---------------|-------------|
| /                      | GET        | None          | public      |
| /login                 | GET, POST  | None (redirect if already logged in) | public |
| /logout                | GET        | None          | clears session |
| /terms                 | GET        | None          | public      |
| /enquiry               | POST       | None          | public      |
| /admin/dashboard       | GET        | admin_required | 'admin'    |
| /member/dashboard      | GET        | member_required | 'user'    |

Error handlers: 403, 404, 500 — all render templates and include base.html footer.

Auth mechanism:
- session key: user_id (int), user_role (str), user_name (str)
- role values: 'admin' or 'user'
- CSRF: session['csrf_token'] generated on GET /login; submitted via form field csrf_token

Seeded credentials (seed_db):
- admin: lakhan@admin.com / 123456 / role='admin'
- member: ansh@member.com / 123456 / role='user'

**Why:** Needed to write correct auth fixtures and avoid accidental 302/403 surprises.
**How to apply:** Use these routes when deciding which pages to hit in tests. Always POST csrf_token when hitting POST endpoints.
