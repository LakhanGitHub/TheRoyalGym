# Agent Memory Index

- [Routes and auth model](project_routes_and_auth.md) — All routes, auth roles, seeded credentials, CSRF flow
- [DB fixture pattern](project_db_fixture_pattern.md) — monkeypatch DB_PATH to tmp_path file; :memory: does NOT work
- [CSRF fixture pattern](project_csrf_fixture_pattern.md) — GET page first to seed token, read from session_transaction()
- [Test coverage index](project_test_coverage_index.md) — Which test files cover which routes/features
- [No BeautifulSoup](feedback_no_beautifulsoup.md) — Only Flask + Werkzeug in requirements; use string/regex assertions
- [Footer spec vs implementation](project_implementation_notes_footer.md) — Known divergences between spec and current base.html
