---
name: Environment setup — pytest not in requirements.txt
description: pytest is absent from requirements.txt and must be pip-installed into .venv before tests can run
type: project
---

`requirements.txt` contains only `Flask==3.0.3` and `Werkzeug==3.0.3`. pytest is not listed.
The project venv is at `.venv\Scripts\python.exe` (Windows). Standard shell commands (ls, python, which) are unavailable in this bash environment; use the full Windows path to the venv Python directly.

Run command:
```
"<abs_project_root>\.venv\Scripts\python.exe" -m pytest tests/<file>.py -v
```

Install if missing:
```
"<abs_project_root>\.venv\Scripts\python.exe" -m pip install pytest
```

**Why:** The bash environment is a thin POSIX layer on Windows — most system binaries (ls, python, head) are unavailable. PATH includes `.venv\Scripts` but bash cannot resolve Windows-style paths without the full path.
**How to apply:** Always invoke pytest via the full .venv Python path. Never rely on `python` or `pytest` as bare commands.
