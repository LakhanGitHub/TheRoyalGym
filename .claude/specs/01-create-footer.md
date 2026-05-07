# Spec: Create Footer

## Overview
Replace the current single-line copyright footer with a multi-column footer that appears
site-wide via `base.html`. The footer is the first roadmap step that elevates the global
chrome of The Royal Gym from a placeholder to the Figma-aligned design — it surfaces brand
identity, quick navigation, contact information, and a copyright bar consistently across the
landing page, login page, dashboards, and error pages. Because the footer lives in `base.html`,
every existing template inherits it for free.

## Depends on
- Initial Flask scaffold and `base.html` layout (already shipped in `5db9bed`).
- Code-review hardening pass (already shipped in `1860712`).

No dependencies on later steps. This is step 01 of the roadmap.

## Out of scope
- Privacy Policy and Terms of Service pages or routes — placeholder `href="#"` links only.
- Footer animations or JavaScript interactions of any kind.
- Any change to `main.js`.
- Any new route, DB call, or Flask Blueprint.
- Wiring up real social media URLs (placeholders used until client confirms them).
- Print stylesheet changes (footer background is class-scoped so a future print stylesheet
  can override it without touching this step's code).

## Routes
No new routes.

## Database changes
No database changes.

## Templates

- **Create:** None.
- **Modify:**
  - `theroyalgym/templates/base.html` — replace the current
    `<footer class="footer">…</footer>` block (lines ~77–81) with a four-region footer:

    1. **Brand column** — logo (reusing the navbar `&#127947;` brand mark + "The Royal Gym"
       wordmark), one-sentence tagline, and 3 social icon links (Instagram, Facebook,
       X/Twitter) using inline SVGs sourced from
       [Tabler Icons](https://tabler.io/icons) (MIT-licensed). Do not attempt to reproduce
       brand logos pixel-perfectly; use the closest Tabler icon path. Social links must use
       `rel="noopener noreferrer"` and `target="_blank"`, with `aria-label` on each `<a>`.
       All decorative SVGs must include `aria-hidden="true"`. Social link `href` values must
       be `href="#"` with an `aria-disabled="true"` attribute and an HTML comment
       `<!-- TODO: replace with real URL -->` until real URLs are provided by the client.

    2. **Quick Links column** — heading "Explore", a `<nav aria-label="Footer navigation">`
       containing a `<ul>`/`<li>` list of anchor links to `#why`, `#programs`, `#plans`,
       `#contact`. Before writing these slugs, verify that those exact anchor IDs exist in
       `landing.html`; if any ID differs, use the actual ID. Each link must use
       `url_for('index', _anchor='<id>')` so it routes correctly from non-landing pages —
       never hardcode `/#why` or similar.

    3. **Contact column** — heading "Contact", wrapped in `<address>` (correct semantic use:
       this is the site's own contact info, scoped to the page body). Three lines:
       plain-text address (`123 Royal Avenue, Mumbai`), phone (`+91 98765 43210`) using
       `href="tel:+919876543210"`, email (`hello@theroyalgym.com`) using
       `href="mailto:hello@theroyalgym.com"`.

    4. **Bottom bar** — `&copy; 2026 The Royal Gym. All rights reserved.` on the left; on
       the right, two text links (`Privacy Policy`, `Terms of Service`) pointing at `href="#"`
       for now (placeholder — no routes yet). At viewport widths ≤ 768px, the bottom bar must
       stack: copyright above links, both centered, with no horizontal overflow.

  - The footer must be wrapped in `<footer class="footer" role="contentinfo">` and use
    semantic markup throughout (`<nav>` for the links column, `<address>` for contact,
    `<ul>`/`<li>` for all link lists).

## Files to change
- `theroyalgym/templates/base.html` — swap in the new footer markup as described above.
- `theroyalgym/static/css/style.css`:
  - **Before writing any CSS**, check whether `--bg-footer` (or an equivalent dark-black
    variable) already exists in `:root`. If it does, use it. If it does not, add
    `--bg-footer: #0a0a0a;` to the `:root` block first, then use `var(--bg-footer)`
    everywhere — never write `#0a0a0a` directly in a rule.
  - Replace existing `.footer` / `.footer-inner` rules with the multi-column layout.
  - New classes to add: `.footer-grid`, `.footer-col`, `.footer-brand`, `.footer-tagline`,
    `.footer-socials`, `.footer-social-link`, `.footer-heading`, `.footer-links`,
    `.footer-link`, `.footer-contact`, `.footer-contact-line`, `.footer-bottom`,
    `.footer-bottom-links`.
  - Use only existing CSS variables from `:root` (`--accent-gold`, `--text-primary`,
    `--text-secondary`, `--text-muted`, `--border-color`, `--surface`, `--body-bg`,
    `--radius-md`, `--font`, `--t`, and the newly-added `--bg-footer`).
  - The footer inner content must be wrapped in a container whose `max-width` matches the
    existing site-wide container value in `base.html` (inspect the current `.container` or
    equivalent class before writing), with `margin: 0 auto` and appropriate horizontal
    padding so the footer does not stretch edge-to-edge on wide or ultrawide displays.
  - Add `@media (max-width: 1024px)` to collapse `.footer-grid` from 4 columns to 2.
  - Add `@media (max-width: 768px)` to collapse `.footer-grid` to a single column with
    centered content, and to stack the bottom bar (copyright above links, centered).

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs.
- Parameterised queries only.
- Passwords hashed with werkzeug.
- **CSS variables mandatory, no hardcoded hex values.** If `#0a0a0a` is not already a
  variable in `:root`, add `--bg-footer: #0a0a0a` first. Every color in new CSS rules
  must reference a CSS variable — no exceptions.
- All templates extend `base.html`.
- No JavaScript framework. The footer must be pure HTML/CSS — no `main.js` changes.
- All anchor links to landing-page sections must use `url_for('index', _anchor='<id>')`.
  Verify the anchor IDs exist in `landing.html` before hardcoding them.
- Social icons must be inline SVG using paths from Tabler Icons (MIT). SVGs use
  `currentColor` so they inherit color from the parent via CSS.
- Decorative SVGs must include `aria-hidden="true"`. Social `<a>` elements must have
  `aria-label`. Social `href` values must be `href="#"` with `aria-disabled="true"` and
  a `<!-- TODO: replace with real URL -->` comment.
- Do not introduce new templates, routes, or DB calls — this step is presentation-only.
- The footer must render without horizontal overflow or layout breakage on every existing
  page that extends `base.html`: `landing.html`, `login.html`, `admin_dashboard.html`,
  `member_dashboard.html`, `errors/403.html`, `errors/404.html`, `errors/500.html`.

## Open questions
- **Social URLs** — real Instagram, Facebook, and X/Twitter handles not yet provided.
  Placeholder `href="#"` used. Confirm with client before the next step.
- **Site-wide container max-width** — inspect `base.html` / `style.css` for the current
  `.container` max-width before writing footer container CSS; do not guess.

## Definition of done
- [ ] `git diff main..HEAD -- theroyalgym/templates/base.html theroyalgym/static/css/style.css`
      shows changes **only** in those two files and no other paths.
- [ ] `python theroyalgym/app.py` starts cleanly on port 5001 with no console errors or
      Jinja2 warnings.
- [ ] Visiting `http://127.0.0.1:5001/` shows a four-column footer (brand, Explore, Contact,
      bottom bar) at the bottom of the landing page with no horizontal scrollbar.
- [ ] Visiting `http://127.0.0.1:5001/login` shows the identical footer.
- [ ] Visiting `http://127.0.0.1:5001/nope` (404) shows the identical footer below the error
      template.
- [ ] After logging in with the admin credentials from `CLAUDE.md` or `.env`, visiting
      `/admin/dashboard` shows the identical footer.
- [ ] View-source on any page confirms Explore links render as `/#why`, `/#programs`,
      `/#plans`, `/#contact` in their `href` (verifying `url_for(_anchor=)` works correctly).
- [ ] Clicking **Explore → Programs** from the login page navigates to `/#programs` and
      scrolls to the Programs section on the landing page.
- [ ] Clicking the Contact → Email link opens the system mail client addressed to
      `hello@theroyalgym.com`.
- [ ] Clicking any social icon link opens a new tab and does not navigate the current tab.
- [ ] **No new hardcoded hex in CSS** — verified by diffing only new lines:
      ```bash
      git diff main..HEAD -- theroyalgym/static/css/style.css | grep "^+" | grep -E "#[0-9a-fA-F]{3,6}"
      ```
      Output must be empty (or contain only the `--bg-footer: #0a0a0a` variable declaration
      in `:root`, not usage in rules).
- [ ] At 600px viewport width: footer columns collapse to a single column with centered
      content; bottom bar stacks copyright above Privacy/Terms links, centered, no overflow.
- [ ] At 900px viewport width: footer shows a 2-column grid layout (or the designed
      intermediate breakpoint per implementation).
- [ ] At 1440px and 2560px viewport widths: footer inner content is constrained by the
      max-width container and does not stretch edge-to-edge.
- [ ] Browser DevTools accessibility check shows no new violations: every social `<a>` has
      `aria-label`, every decorative SVG has `aria-hidden="true"`, text color contrast passes
      WCAG AA against `var(--bg-footer)`.
- [ ] `curl -s -D - -o /dev/null http://127.0.0.1:5001/` still returns all security headers
      from the previous step (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy).
      The CSP `img-src` directive does not need relaxing — no new external image sources are
      introduced by the footer.