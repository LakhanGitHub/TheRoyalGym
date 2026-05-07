---
name: Known test files
description: Test files that exist under tests/ and what spec each covers
type: project
---

- `tests/test_01-create-footer.py` — covers spec `.claude/specs/01-create-footer.md` (footer HTML structure, CSS classes, accessibility, security headers, responsive breakpoints)

**Why:** Avoids re-verifying file existence in future runs.
**How to apply:** When asked to run footer tests, go straight to this file. When asked whether a test file exists for a given spec, consult this list first.
