---
name: Footer implementation notes (spec vs actual)
description: Observed divergences between the footer spec and the current base.html implementation
type: project
---

Spec says social links (Instagram/Facebook/X) should be present with target="_blank",
rel="noopener noreferrer", aria-label, aria-disabled="true", href="#".
Current base.html (as of commit at test-writing time) does NOT have social links in the brand
column — the brand column only has the SVG dumbbell mark + wordmark + tagline.

Spec says mailto should be hello@theroyalgym.com.
Current base.html has mailto:info@royalgym.com instead.

Spec says Quick Links column should be headed "Explore".
Current base.html uses "Quick Links" as the heading.

Contact column heading in spec: "Contact".
Current base.html uses "Contact Us".

Tests for social links, the specific mailto address, and the "Explore" heading are
intentionally written to match the SPEC (not the implementation), so they will FAIL
until the implementation is updated to match the spec.

Tests that already pass against the current implementation were written with
the actual markup in mind but are still spec-compliant (e.g., footer element class,
url_for anchor links, CSS classes, security headers).

**Why:** Instructions say "test the spec, not the code". Known-failing tests are correct
— they document missing implementation work.
**How to apply:** When a test fails for the footer, check this note first before assuming
the test is wrong. The test is probably correct and the template needs updating.
