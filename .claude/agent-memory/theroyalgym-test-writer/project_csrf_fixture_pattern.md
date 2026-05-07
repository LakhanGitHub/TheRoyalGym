---
name: CSRF fixture pattern for POST routes
description: How to obtain and submit a valid CSRF token in test clients
type: project
---

All POST routes (login, enquiry) validate a csrf_token form field against session['csrf_token'].
The token is generated on first access via the generate_csrf_token() Jinja global.
In tests it is seeded when a GET to /login is made (the template renders and calls csrf_token()).

Correct pattern to obtain the CSRF token for a POST:

```python
resp = client.get('/login')          # seeds session['csrf_token']
with client.session_transaction() as sess:
    token = sess.get('csrf_token', '')
client.post('/login', data={
    'email': '...',
    'password': '...',
    'csrf_token': token,
})
```

Without this, the POST returns 403 (abort(403) on CSRF mismatch).

**Why:** The app uses hmac.compare_digest for CSRF validation; an empty/missing token always fails.
**How to apply:** Every test that POSTs to a protected endpoint must first GET the page to seed the token, then read it from session_transaction().
