---
name: DB fixture pattern for in-memory isolation
description: How to isolate the SQLite DB in tests (DB_PATH is module-level, not config-driven)
type: project
---

database/db.py uses a module-level DB_PATH constant pointing to gym.db in the project root.
get_db() calls sqlite3.connect(DB_PATH) directly — it does NOT read app.config['DATABASE'].

Correct fixture pattern:

```python
import database.db as _db_module
from database.db import init_db, seed_db

@pytest.fixture()
def app(tmp_path, monkeypatch):
    db_file = str(tmp_path / 'test_gym.db')
    monkeypatch.setattr(_db_module, 'DB_PATH', db_file)
    flask_app.config.update({'TESTING': True, 'SECRET_KEY': 'test-secret'})
    with flask_app.app_context():
        init_db()
        seed_db()
        yield flask_app
```

Using ':memory:' would NOT work across multiple get_db() calls (each call returns a new
connection to a fresh in-memory DB — init_db() and subsequent queries would see different DBs).

**Why:** DB_PATH is module-level; flask app config['DATABASE'] key is ignored by get_db().
**How to apply:** Always monkeypatch _db_module.DB_PATH to a tmp_path file in every test fixture.
