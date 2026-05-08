# Spec: Create Payment Page

## Objective

Create a fully functional and professional **Payments Management Page** for TheRoyalGym admin dashboard.

The page design, table structure, toolbar filters, badges, and compact dashboard styling should follow the provided reference image and maintain consistency with:

* Members
* Plans
* Settings
* Dashboard

The Payments module should support:

* recording payments,
* tracking pending invoices,
* managing payment history,
* searching/filtering transactions,
* editing/deleting payment records,
* and maintaining full SQLite database synchronization.

---

# Route

Create admin-only route:

```python
/admin/payments
```

Only authenticated admins can access this page.

---

# Payments Table Structure

The Payments table must contain the following columns in this exact order:

| Column       | Description                             |
| ------------ | --------------------------------------- |
| #            | Serial number                           |
| Member       | Member full name + small username/email |
| Plan         | Membership plan badge                   |
| Amount       | Amount in INR format                    |
| Joining Date | Member join date from database          |
| Payment Date | Payment recorded date                   |
| Mode         | Cash / UPI / Card / Online              |
| Status       | Paid / Pending                          |
| Notes        | Additional notes                        |
| Actions      | Edit/Delete icon buttons                |

---

# Important Date Logic

## Joining Date

* Joining Date must come directly from:

  * `members.join_date`
* This field is readonly/display-only.
* It is NOT entered during payment recording.

## Payment Date

* Payment Date is filled only during:

  * Add Payment
  * Record Payment
* Must support:

  * calendar picker
  * manual editable input
* Stored in `payments.paid_on`

---

# Compact Professional Table Layout

Since additional columns are added:

* table rows must remain compact
* all important information should fit in a single row
* reduce font size slightly for professional admin dashboard appearance
* avoid unnecessary text wrapping
* use ellipsis where necessary
* maintain readability and spacing

Recommended:

* font-size: `13px–14px`
* compact badge styling
* smaller table cell padding
* consistent alignment

---

# Database Data Population

The following information must dynamically populate from database:

* Member Name
* Username/Email
* Membership Plan
* Plan Amount
* Joining Date

Data sources:

* `members`
* `membership_plans`
* `payments`

No hardcoded values.

---

# Add / Record Payment Form

Top-right button:

```text
+ Record Payment
```

should open Add Payment page.

For now:

* button may behave as placeholder navigation
* full form structure and validation must still be implemented

---

# Payment Form Fields

## Required Fields

### Payment Date

* Calendar date picker required
* Manual editing allowed
* ISO date validation required

### Payment Mode

Options:

* Cash
* UPI
* Card
* Online

Rules:

* Store lowercase in database
* Each mode should have professional color-coded badge

Example:

* Cash → Gray
* UPI → Purple
* Card → Blue
* Online → Cyan

---

### Payment Status

Options:

* Paid
* Pending

Color coding:

* Paid → Green
* Pending → Amber/Orange

---

### Notes

* Optional textarea
* Capture admin remarks
* Max length validation required

Examples:

* Full payment received
* ₹500 pending
* Renewal requested

---

# Search & Filter Toolbar

Add professional toolbar above payments table.

## Filters Required

### Search by Member

* Search using:

  * member name
  * email/username
* Dynamic filtering without reload
* Include search icon prefix

---

### Search by Status

Dropdown:

* All
* Paid
* Pending

Must dynamically filter table rows.

---

# UI/UX Design Rules

## Table Styling

* Compact professional admin dashboard appearance
* Responsive design
* Sticky table header preferred
* Row hover highlight
* Professional spacing/alignment

---

## Action Buttons

Use professional SVG icon buttons only.

### Edit

Suggested icons:

* pencil
* square-pen

### Delete

Suggested icons:

* trash
* trash-2

Rules:

* Horizontal alignment
* Tooltip support
* Same styling as Members module

---

# Membership Plan Badge Colors

Each plan should have unique consistent color:

| Plan      | Color  |
| --------- | ------ |
| Trial     | Blue   |
| Monthly   | Purple |
| Quarterly | Orange |
| Yearly    | Green  |

Use soft dashboard theme colors only.

---

# Validation Rules

## Frontend + Backend Validation Required

Never rely only on frontend validation.

Both:

* JavaScript
* Flask backend

must validate all fields.

---

# Validation Criteria

## member_id

* Must exist in members table
* Must belong to normal member role

---

## plan_id

* Optional
* If provided, must exist in membership_plans table

---

## amount

* Numeric only
* Greater than 0
* Reasonable max limit validation

---

## payment_date

* Required
* Valid ISO date
* Past/current/future dates allowed

---

## payment_mode

* Must match allowed mode list only

---

## payment_status

* Must match allowed statuses only

---

## notes

* Optional
* Max length validation required

---

# Database Requirements

Create payments table:

```sql
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    plan_id INTEGER,
    amount REAL NOT NULL,
    paid_on TEXT NOT NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:

* member_id
* paid_on

---

# Delete Behavior

Delete must:

* permanently remove payment from SQLite database
* not reappear after refresh/restart
* use confirmation modal
* synchronize UI and DB correctly

---

# Expected Features

* Professional compact dashboard layout
* Dynamic filters
* Color-coded badges
* Compact single-line table rows
* Responsive design
* Sticky toolbar/table header
* Real database synchronization
* Professional admin experience

---

# Definition of Done

* Payments tab works correctly
* Add/Edit/Delete fully functional
* Filters/search operational
* Joining Date loads correctly from database
* Payment Date recorded separately during payment entry
* Table remains compact and aligned in single row
* Data persists correctly in SQLite database
* Role-based admin protection working
* No fake frontend-only updates
* All validation rules working
* UI matches professional gym dashboard quality
