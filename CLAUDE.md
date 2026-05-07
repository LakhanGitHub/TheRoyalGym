# 🏋️ The Royal Gym – Flask App (FIGMA-ALIGNED BUILD PROMPT)

# Read figma design
- https://wired-heap-51917594.figma.site/


You are a senior full-stack developer and UI engineer.

You are given a **Figma design prototype** for a landing page.

Your task is to convert it into a **pixel-accurate Flask web application**.

---

# 🎯 PRIMARY RULE (VERY IMPORTANT)

The Figma design is the **single source of truth**.

* Do NOT redesign
* Do NOT improvise layout
* Match spacing, alignment, and proportions exactly
* Use Figma values for:

  * padding
  * margin
  * font sizes
  * colors
  * border radius

---

# 🧱 PROJECT ARCHITECTURE (STRICT)

theroyalgym/
├── app.py
├── database/
│   └── db.py
├── templates/
│   ├── base.html
│   ├── landing.html
│   ├── register.html
│   └── login.html
├── static/
│   ├── css/
│   │   ├── style.css
│   │   └── landing.css
│   └── js/
│       └── main.js
└── requirements.txt

---

# 🎨 FIGMA IMPLEMENTATION RULES

## 1. Layout System

* Use Flexbox or Grid based on Figma auto-layout
* Maintain exact spacing between elements
* Do NOT guess spacing

---

## 2. Typography

Extract from Figma:

* Font family
* Font weight
* Font size
* Line height

Apply consistently using CSS variables

---

## 3. Colors (IMPORTANT)

Define CSS variables in `style.css`:

:root {
--primary-gradient: linear-gradient(...);
--text-primary: ...;
--text-secondary: ...;
--card-bg: ...;
}

---

## 4. Components (CRITICAL)

Convert repeated UI into reusable components:

* Navbar
* Hero section
* Feature card
* Info card
* Form input group

---

# 🌈 HERO SECTION (MATCH FIGMA EXACTLY)

* Gradient background (use exact colors from Figma)
* Left content:

  * Label
  * Heading
  * Description
  * Buttons
* Right:

  * Image with border radius and shadow

Spacing must match Figma exactly.

---

# 🧩 FEATURE CARDS

* 4 cards in a row
* Equal width
* Same height
* Same padding
* Icon + text alignment must match design

---

# 📌 MAIN SECTION

## LEFT:

* Heading
* Paragraph
* Two info cards

## RIGHT:

* Contact form card

---

# 🧾 FORM DESIGN RULES

Each input:

* Icon aligned left
* Padding consistent
* Rounded borders
* Focus state styling

---

# 🛠️ TECH CONSTRAINTS

* Flask only
* SQLite only
* No ORM
* Vanilla JS only
* No Bootstrap

---

# 🧠 BACKEND RULES

* Routes in `app.py`
* DB logic in `database/db.py`
* Use parameterized SQL only

---

# ⚡ JAVASCRIPT

* Navbar scroll behavior
* Mobile menu
* Form validation

---

# 📱 RESPONSIVENESS (MATCH FIGMA BREAKPOINTS)

* Desktop
* Tablet
* Mobile

Stack sections exactly as in design.

---

# 🎯 OUTPUT REQUIREMENTS

Generate:

1. Full Flask app
2. Pixel-accurate HTML
3. CSS using variables
4. JS interactions
5. DB setup (basic)

---

# ❗ STRICT RULES

* DO NOT redesign UI
* DO NOT change spacing
* DO NOT skip sections
* FOLLOW FIGMA EXACTLY

---

# 🚀 EXECUTION

1. Build base layout
2. Implement hero
3. Add feature cards
4. Add main section
5. Add responsiveness
6. Final polish

---

# 🔥 FINAL NOTE

This is NOT a generic landing page.

This is a **Figma-to-code conversion task**.

Precision is more important than creativity.

---

Start building now.


# Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **`database/db.py` is currently empty** — do not assume helpers exist until the step that implements them
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection
- The app runs on **port 5001**, not the Flask default 5000 — don't change this
- Use Flask session for authentication (no external auth libraries)
- Store passwords using werkzeug.security.generate_password_hash() and check_password_hash()
- Protect all POST routes with basic CSRF protection (token stored in session and validated manually)
- Validate and sanitize all form inputs (length, format, required fields)
- Use parameterized SQL queries only (?) to prevent SQL injection
- Do not expose stack traces or internal errors to users (use generic error messages)
- Add basic login protection (session-based access control for future routes like /profile)
- Set secure session config:
    - SESSION_COOKIE_HTTPONLY = True
    - SESSION_COOKIE_SAMESITE = 'Lax'
- Never store sensitive data in plain text (especially passwords)