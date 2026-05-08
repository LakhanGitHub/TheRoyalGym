# Final Spec – Professional Member Profile & Membership Page

## Objective

Create a modern and professional **Member Profile Page** for TheRoyalGym member dashboard.

The page design should follow the premium dashboard aesthetic shown in the provided reference images while improving:

* readability,
* information hierarchy,
* compact layout,
* responsive behavior,
* and dynamic database-driven content.

The page should feel like a real premium gym membership portal.

---

# Route

Create member-only route:

```python
/member/profile
```

Rules:

* Accessible only for logged-in members
* Admin users must not access this page
* `/member/dashboard` should redirect to `/member/profile`

---

# Overall Page Structure

The page should contain:

## Top Summary Tiles

Professional dashboard cards showing important membership information.

## Section 1 — My Profile

Member personal information section.

## Section 2 — Membership Details

Detailed membership plan and payment information.

---

# Top Summary Tiles

Create compact professional tiles/cards at the top of the page.

All data must come dynamically from database.

---

## Tile 1 — Current Plan

Display:

* Plan Name
* Plan Duration
* Plan Status Badge

Data Source:

* `membership_plans`
* `members.plan_id`

Example:

```text
Monthly Plan
Duration: 1 Month
Status: Active
```

---

## Tile 2 — Days Remaining

Display:

* Remaining days before plan expiry
* Dynamic status badge

Calculation:

```python
days_remaining = plan_expire_date - today
```

Rules:

* Active → Green
* Expiring Soon → Amber
* Expired → Red

---

## Tile 3 — Remaining Amount

Display:

* Remaining pending amount
* Total paid amount

Calculation:

```python
remaining_amount = plan_amount - total_payment_received
```

Data Source:

* `payments`
* `membership_plans`

Example:

```text
Remaining: ₹600
Paid: ₹600
```

---

## Tile 4 — Plan Expiry Date

Display:

* Membership expiry date
* Dynamic expiry badge

Rules:

* Expired plans should show red badge
* Expiring within current month should show amber warning
* Active future plans should show green

---

# Section 1 — My Profile

Section title:

```text
My Profile
```

This section displays member personal information.

---

# Profile Information Rules

Show:

* Full Name
* Username
* Mobile Number
* Age
* Gender
* Address
* Join Date
* Email

All values must come dynamically from database.

No placeholder/static data allowed.

---

# Profile UI Design

Layout should follow professional dashboard design:

* left-side profile summary card
* right-side detailed information table/card
* compact spacing
* professional typography
* mobile responsive layout

Use:

* profile avatar icon
* info icons
* subtle borders
* dashboard theme colors

---

# Section 2 — Membership Details

Section title:

```text
Membership Details
```

This section should display complete membership and payment information.

---

# Membership Details Fields

Display:

* Plan Name
* Duration
* Plan Amount
* Total Paid
* Remaining Amount
* Start Date
* End Date
* Days Remaining
* Membership Status

All values must be dynamically calculated or fetched from database.

---

# Membership Status Logic

Status must NEVER be stored in database.

Status should be dynamically derived:

```python
if no_plan:
    status = "No Active Plan"
elif expired:
    status = "Expired"
elif expiring_within_7_days:
    status = "Expiring Soon"
else:
    status = "Active"
```

---

# Payment Information Section

Display latest payment information dynamically from payments table.

Show:

* Payment Date
* Payment Mode
* Amount Paid
* Payment Status
* Notes

Rules:

* Show latest 5 payment records only
* Use compact professional payment table
* Status badges should use color coding

---

# Change Password Button

## Important UI Rule

There should be ONLY ONE button on the top-right side:

```text
Change Password
```

Rules:

* Remove all other buttons
* No Edit Profile button
* No Save Profile button visible on top section
* No extra action buttons

---

# Change Password Functionality

Member should be able to:

* change own password
* securely update password in database
* use hashed password storage only

Validation:

* old password required
* new password minimum length validation
* confirm password match validation

Use:

```python
generate_password_hash()
check_password_hash()
```

---

# Self Editable Fields

Members may update ONLY:

* Mobile
* Age
* Gender
* Address

Members must NOT edit:

* Name
* Username
* Email
* Role
* Plan
* Join Date
* Expiry Date
* Payment History

---

# Validation Rules

## Mobile Number

* Must follow Indian mobile validation
* 10 digits only
* Support +91 format if existing helper allows

---

## Age

Allowed range:

```python
5 <= age <= 120
```

---

## Gender

Must match allowed gender options only.

---

## Address

* Optional
* Max length validation required

---

# Security Rules

## CSRF Protection

All POST forms must validate CSRF token.

---

## Authorization

Always use:

```python
session['user_id']
```

Never allow member_id in URL or form body.

Members can access ONLY their own data.

---

## Database Rules

* Parameterized queries only
* No SQLAlchemy
* No ORM
* No raw SQL concatenation

---

# CSS / UI Rules

Use:

* existing dashboard design system
* existing CSS variables
* compact professional spacing
* responsive layout
* reusable dashboard cards/pills

Rules:

* No hardcoded hex colors
* Use CSS variables only
* Reuse dashboard theme

---

# Responsive Layout Rules

The page must render properly on:

* desktop
* tablet
* mobile

Rules:

* tiles stack properly on mobile
* tables remain readable
* compact spacing preserved
* no layout breaking

---

# Files to Create

```text
templates/member_profile.html
static/css/member_profile.css
```

---

# Files to Modify

```text
app.py
database/db.py
templates/base.html
templates/member_dashboard.html
```

---

# Database Helper Required

Create helper:

```python
update_member_self(member_id, mobile, age, gender, address)
```

Rules:

* update ONLY editable fields
* never modify protected member fields

---

# Expected Features

* Professional premium gym member portal
* Dynamic membership calculations
* Real payment tracking
* Compact dashboard layout
* Responsive design
* Secure password change flow
* Real SQLite synchronization
* No hardcoded placeholder data

---

# Definition of Done

* `/member/profile` loads successfully
* `/member/dashboard` redirects correctly
* All profile data loads dynamically from database
* Membership calculations work correctly
* Remaining amount calculates correctly
* Days remaining calculates correctly
* Plan expiry status updates dynamically
* Latest payments render correctly
* Change password updates hashed password in SQLite
* Only editable fields can be modified
* Validation rules work correctly
* CSRF protection enforced
* Responsive layout works properly
* UI matches premium gym dashboard quality
* No placeholder/static data remains anywhere on page
