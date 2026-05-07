---
name: Footer test run — test_01-create-footer.py result summary
description: First run of footer tests: 52 passed, 4 failed — all failures are implementation bugs (missing HTML/CSS spec items)
type: project
---

Run date: 2026-05-07
Command: `<venv>/python.exe -m pytest tests/test_01-create-footer.py -v`
Result: 52 passed, 4 failed

Failures (all classified as Bug — implementation deviates from spec):

1. `test_footer_explore_link_contact` — `href="/#contact"` absent from rendered HTML. Footer Quick Links column in base.html has no link to `#contact`; the four links are `#home`, `#why`, `#programs`, `#plans` only. Spec requires a `#contact` anchor link.

2. `test_css_footer_socials_class_defined` — `.footer-socials` class absent from style.css. Spec requires it; implementation never added a social icons row.

3. `test_css_footer_social_link_class_defined` — `.footer-social-link` class absent from style.css. Same root cause as above (social icons feature not implemented).

4. `test_css_footer_bottom_links_class_defined` — `.footer-bottom-links` class absent from style.css. Bottom bar uses `.footer-bottom-sep` / inline `<a>` but never defines the `.footer-bottom-links` wrapper class specified in the spec.

**Why:** Useful baseline for the next fix iteration.
**How to apply:** When re-running after a fix, verify exactly these four items changed status to PASSED.
