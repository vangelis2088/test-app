## API reference

Every request is assigned a `voter_id` cookie (22-character URL-safe random string, `HttpOnly`, `SameSite=Lax`, one-year lifetime) if it does not already carry a valid one. The cookie is set on the response of whichever endpoint is hit first. It identifies the browser for voting; each `voter_id` has at most one vote.

### `GET /health`

Health check.

**Parameters:** none.

**Responses**

| Status | Body |
| --- | --- |
| 200 | JSON: `{"status": "ok"}` |

### `GET /`

Full HTML page (`index.html`) listing all topics.

**Parameters:** none.

**Responses**

| Status | Body |
| --- | --- |
| 200 | HTML page. Topics are ordered by vote count (descending), then newest first. The topic the current browser voted for is marked as "Your vote". |

### `GET /topics`

Returns the topic list as an htmx partial (`_topics.html`), with the same ordering and "Your vote" marking as `GET /`.

**Parameters:** none.

**Responses**

| Status | Body |
| --- | --- |
| 200 | HTML partial (`_topics.html`). Shows "No topics yet" when there are none. |

### `POST /topics`

Creates an attendee topic and returns the updated topic list.

**Parameters** (form fields, `application/x-www-form-urlencoded`)

| Name | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | yes (defaults to `""`, which fails validation) | Whitespace is trimmed. Must be 1–280 characters after trimming. |
| `author` | string | no | Whitespace is trimmed; an empty value is stored as no author (shown as "anonymous"). |

**Responses**

| Status | Body |
| --- | --- |
| 200 | HTML partial (`_topics.html`) including the new topic. |
| 422 | HTML partial (`_topics.html`) with an error message ("Title is required." or "Title must be at most 280 characters."). No topic is created. |

### `POST /topics/{topic_id}/vote`

Casts the current browser's vote for a topic. If the browser already voted, the vote is moved to this topic (one vote per `voter_id`). Voting for the same topic again leaves the vote unchanged.

**Parameters**

| Name | In | Type | Required | Notes |
| --- | --- | --- | --- | --- |
| `topic_id` | path | integer | yes | A non-integer value returns 422 (FastAPI validation error, JSON). |

**Responses**

| Status | Body |
| --- | --- |
| 200 | HTML partial (`_topics.html`) with updated counts. |
| 404 | Plain text/HTML body `Topic not found` when no topic has this id. |
| 422 | JSON validation error when `topic_id` is not an integer. |
