---
name: No BeautifulSoup — use plain string / regex assertions
description: requirements.txt only has Flask and Werkzeug; no HTML parsing library available
type: feedback
---

Use plain string contains checks (assert 'footer-grid' in body) and re.search() / re.findall()
for structural assertions.  Do not import bs4 or lxml — they are not in requirements.txt
(Flask==3.0.3, Werkzeug==3.0.3 only).

**Why:** Installing new packages mid-feature is explicitly forbidden per project rules.
**How to apply:** Whenever a test needs to check HTML structure, use body.find('<footer') slicing plus string/regex checks, not an HTML parser.
