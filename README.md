## API reference

<!-- api-reference:start -->
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check (JSON). |
| GET | `/` | Full HTML page with the topic list and submission form. |
| GET | `/topics` | htmx partial: the current topic list. |
| POST | `/topics` | Submit a new attendee topic; returns the refreshed topic list partial. |
| POST | `/topics/{topic_id}/vote` | Cast or move the caller's single vote; returns the refreshed topic list partial. |

Topics are ordered by vote count (descending), then newest first. Each voter (identified by the `voter_id` cookie) has at most one vote.

### `GET /health`
- **Parameters:** none.
- **Response:** JSON `{"status": "ok"}`, status 200.

### `GET /`
- **Parameters:** none.
- **Response:** full HTML page (`index.html`) including the topics, the voter's current vote, and the maximum title length (280).
- **Side effects:** sets the `voter_id` cookie if the request has no valid one (see below).

### `GET /topics`
- **Parameters:** none.
- **Response:** HTML partial (`_topics.html`) with all topics and the voter's current vote.
- **Side effects:** sets the `voter_id` cookie if missing or malformed.

### `POST /topics`
- **Form fields** (`application/x-www-form-urlencoded`):
  - `title` (optional in the signature, but must be non-empty after trimming): 1–280 characters after whitespace is stripped.
  - `author` (optional): whitespace is stripped; an empty value is stored as no author.
- **Response:** on success, HTML partial (`_topics.html`), status 200. The topic is stored with source `attendee`.
- **Status codes:**
  - `422`: invalid title. Returns the HTML fragment `_form_error.html` with the message "Please enter a topic." (empty) or "Topics can be at most 280 characters." (too long), and the headers `HX-Retarget: #form-error` and `HX-Reswap: innerHTML`. No cookie is set on this response.
- **Side effects:** inserts a topic; sets the `voter_id` cookie on success if missing or malformed.

### `POST /topics/{topic_id}/vote`
- **Path parameters:** `topic_id` (integer).
- **Response:** HTML partial (`_topics.html`), status 200. Voting again for a different topic moves the vote; voting for the same topic changes nothing.
- **Status codes:**
  - `404`: no topic with that id (`{"detail": "Topic not found"}`).
  - `422`: `topic_id` is not an integer (FastAPI validation error).
- **Side effects:** records or moves the voter's vote; sets the `voter_id` cookie if missing or malformed.

### Voter cookie
When a request has no valid `voter_id` cookie (it must be a UUID), the endpoints that render topics (`GET /`, `GET /topics`, successful `POST /topics`, `POST /topics/{topic_id}/vote`) issue a new random UUID: `HttpOnly`, `SameSite=Lax`, max age 1 year.
<!-- api-reference:end -->
