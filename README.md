# test-app

## API reference

<!-- api-reference:start -->
| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check (JSON). |
| GET | `/` | Full HTML page listing topics. |
| GET | `/topics` | htmx partial with the topic list. |
| POST | `/topics` | Create an attendee topic; returns the updated topic list partial. |
| POST | `/topics/{topic_id}/vote` | Cast or move the caller's single vote; returns the updated topic list partial. |

**All endpoints:** an HTTP middleware reads the `voter_id` cookie. If it is missing or not 32 lowercase hex characters, a new UUID hex is generated and the response sets `voter_id` (max-age 1 year, `HttpOnly`, `SameSite=Lax`). The voter id is used to track the caller's single vote.

### `GET /health`

- **Parameters:** none.
- **Response:** `200` JSON `{"status": "ok"}`.

### `GET /`

- **Parameters:** none.
- **Response:** `200` HTML page rendered from `index.html`, with `topics` (ordered by vote count descending, then newest first) and `voted_topic_id` (the topic the caller currently votes for, or none).

### `GET /topics`

- **Parameters:** none.
- **Response:** `200` htmx partial rendered from `_topics.html`, with the same context as `GET /`.

### `POST /topics`

- **Form parameters:**
  - `title` (string, default `""`): trimmed; required, at most 280 characters.
  - `name` (string, default `""`): trimmed and stored as the topic author; blank is stored as no author.
- **Response (success):** `200` htmx partial rendered from `_topics.html`. The topic is stored with source `attendee`.
- **Response (validation error):** `422` htmx partial rendered from `_form_error.html` with headers `HX-Retarget: #form-error` and `HX-Reswap: innerHTML`. Error messages: `Title is required.` or `Title must be at most 280 characters.`

### `POST /topics/{topic_id}/vote`

- **Path parameters:** `topic_id` (integer).
- **Behavior:** each voter has one vote; voting for a different topic moves it, and voting for the same topic again changes nothing.
- **Response (success):** `200` htmx partial rendered from `_topics.html`.
- **Status codes:** `404` with detail `Topic not found` if the topic does not exist; `422` (FastAPI's standard validation error) if `topic_id` is not an integer.
<!-- api-reference:end -->
