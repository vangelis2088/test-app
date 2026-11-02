## API Reference

All endpoints return HTML (or JSON for `/health`); there is no JSON API for topics. FastAPI's auto-generated `/docs`, `/redoc` and `/openapi.json` are not covered here.

### Voter cookie (middleware)

Every request passes through middleware that reads the `voter_id` cookie. If it is missing or not 32 lowercase hex characters, a new random id is generated and the response sets `voter_id` (`HttpOnly`, `SameSite=Lax`, max age 1 year). The id only identifies the browser; there is one vote per `voter_id`, and voting again moves that vote to the new topic.

### `GET /health`

Returns `200` with JSON `{"status": "ok"}`.

### `GET /`

Returns `200` with the full HTML page (`index.html`), which includes the topic list (`_topics.html`). Topics are ordered by vote count (desc), then newest first. The caller's current vote is highlighted.

### `GET /topics`

Returns `200` with the htmx partial `_topics.html` (the `#topic-list` element). The list polls this endpoint every 3 seconds.

### `POST /topics`

Creates an attendee topic. Form fields (`application/x-www-form-urlencoded`):

| Field | Required | Default | Notes |
|---|---|---|---|
| `title` | yes (non-empty after trim) | `""` | Trimmed; max 280 characters |
| `author` | no | `""` | Trimmed; stored as null if empty |

- `200`: htmx partial `_topics.html` with the updated list.
- `422`: partial `_form_error.html` with a message (`Please enter a topic.` or `Topics can be at most 280 characters.`). Sent with headers `HX-Retarget: #form-error` and `HX-Reswap: innerHTML`.

### `POST /topics/{topic_id}/vote`

Casts or moves the caller's single vote. Path parameter `topic_id` is an integer (non-integer values give `422` from FastAPI validation).

- `200`: htmx partial `_topics.html` with the updated list. Voting for the topic already voted for is a no-op.
- `404`: JSON `{"detail": "Topic not found"}` if the topic does not exist.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `QA_DB_PATH` | `qa.db` | SQLite database file path |
| `TOPICS_FILE` | `data/topics.json` | JSON list of organizer topics (`[{"title": ...}]`), loaded at startup; duplicates are ignored |
