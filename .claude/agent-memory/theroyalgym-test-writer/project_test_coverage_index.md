---
name: Test coverage index
description: Which test files cover which routes/features to avoid duplication
type: project
---

| Test file                          | Feature spec                   | Routes / areas covered                              |
|------------------------------------|--------------------------------|-----------------------------------------------------|
| tests/test_01-create-footer.py     | .claude/specs/01-create-footer.md | /, /login, /nope (404), /admin/dashboard, /member/dashboard — footer HTML structure, CSS classes, security headers |

CSS file tested: static/css/style.css (footer class definitions, --bg-footer variable, media queries, no raw hex in footer rules)

**Why:** Prevents duplicate test functions being written for the same routes in later steps.
**How to apply:** Check this index before writing a new test file to know which routes already have coverage.
