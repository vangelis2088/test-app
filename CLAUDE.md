## Stack
- FastAPI + Jinja2 templates + htmx (from CDN). No frontend build step.
- SQLite via the standard library `sqlite3`. No ORM.
- Python tooling is `uv`. Never use pip directly.

## Structure
- `app/main.py`: routes only
- `app/db.py`: all SQL lives here
- `templates/`: Jinja2 templates; htmx partials start with `_` (e.g. `_topics.html`)
- `data/topics.json`: organizer topics, loaded at startup
- `tests/`: one test file per module

## Rules
- Every new endpoint gets a test in the same change.
- DB path comes from env var `QA_DB_PATH` (default `qa.db`). Tests use a temporary DB, never `qa.db`.
- Organizer topics file path comes from env var `TOPICS_FILE` (default `data/topics.json`). Tests use a temporary file.
- Dependencies: never run `uv add` in the same turn a new package comes up, even
  if I ask for it directly. First say which package, why, and whether the
  standard library would do; then wait for me to reply "approved".
- Never read or modify `.env`.
- Run tests and ruff before saying a task is done.