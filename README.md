## API reference

Source of truth: `app/main.py` (routes), `app/db.py` (SQL), `templates/` (HTML).

### Cross-cutting behaviour

- **`voter_id` cookie** (`voter_cookie` middleware in `app/main.py`, applies to every request including `/health`): if the request has no `voter_id` cookie, or its value is not 32 lowercase hex characters, a new random id (`uuid4().hex`) is generated and returned via `Set-Cookie` (`Max-Age` 1 year, `HttpOnly`, `SameSite=Lax`). The id only identifies the voter: it is the key of the single vote each voter may hold (`votes.voter_id` is the primary key), and is used to mark the voter's chosen topic as "Your vote".
- **htmx polling**: `templates/index.html` loads htmx 2.0.4 from unpkg and polls `GET /topics` every **3 seconds** (`hx-trigger="every 3s"`), replacing the inner HTML of `#topics`. htmx is configured to swap 2xx/3xx and 422 responses, so validation errors from `POST /topics` are rendered; other 4xx/5xx responses are not swapped.
- **Topic list order** (all endpoints returning the topics partial): most votes first, then newest `created_at`, then highest id.
- Topic titles and authors are rendered through Jinja2 autoescaping.

### `GET /health`

Liveness check.

| | |
|---|---|
| Inputs | none |
| Response | `200` JSON `{"status": "ok"}` |
| Side effects | none (the `voter_id` cookie may be set) |

### `GET /`

Full HTML page (`index.html`): the suggestion form, plus the topic list (embedded `_topics.html`) that polls `/topics`.

| | |
|---|---|
| Inputs | none |
| Response | `200` HTML page |
| Side effects | none (the `voter_id` cookie may be set) |

### `GET /topics`

htmx partial with the current topic list; the target of the 3-second poll.

| | |
|---|---|
| Inputs | none |
| Response | `200` HTML partial (`_topics.html`): a list of topics with vote count, Vote/"Your vote" button, title, "Organizer's pick" badge for organizer topics, and author (or "Anonymous"); or "No topics yet. Suggest the first one!" when empty |
| Side effects | none (the `voter_id` cookie may be set) |

### `POST /topics`

Suggest a new topic (source `attendee`).

| | |
|---|---|
| Inputs (form fields) | `title` — required in practice; trimmed; must be non-empty and at most 280 characters. `author` — optional; trimmed; empty becomes `NULL` (shown as "Anonymous"). A missing field is treated as an empty string. |
| Response `200` | HTML partial (`_topics.html`) with the updated list |
| Response `422` | HTML partial with the list and an error message: `Please enter a topic.` (empty title) or `Topics can be at most 280 characters.` (too long). No topic is created. |
| Side effects | Inserts a row into `topics` on success. |

### `POST /topics/{topic_id}/vote`

Cast (or move) the caller's single vote.

| | |
|---|---|
| Path parameter | `topic_id` — integer |
| Response `200` | HTML partial (`_topics.html`) with the updated list |
| Response `404` | JSON `{"detail": "Topic not found"}` if no topic has this id |
| Response `422` | FastAPI validation error JSON if `topic_id` is not an integer |
| Side effects | Upserts the caller's row in `votes`: a first vote is recorded; voting for another topic moves the vote; repeating the same vote changes nothing. Each `voter_id` has at most one vote. |

### Startup

On startup (`lifespan`), the DB is initialised (path from `QA_DB_PATH`, default `qa.db`) and organizer topics are loaded from the JSON file in `TOPICS_FILE` (default `data/topics.json`). Entries with an empty title or a title over 280 characters are skipped with a warning; a missing file loads nothing; titles already present as organizer topics are not duplicated.
