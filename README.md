## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check; returns `{"status": "ok"}`. |
| GET | `/` | Renders the full topics page (`index.html`), with topics ordered by votes (highest first), then newest first. Sets a `voter_id` cookie if the browser has no valid one. |
| GET | `/topics` | Returns the topics list as an htmx partial (`_topics.html`). Sets a `voter_id` cookie if missing or invalid. |
| POST | `/topics` | Adds an attendee topic from form fields `title` (required, trimmed, max 280 characters) and `author` (optional). Returns the topics partial; responds 422 with an error message if the title is empty or too long. |
| POST | `/topics/{topic_id}/vote` | Casts the browser's single vote (identified by the `voter_id` cookie) for the topic, or moves it there from another topic. Returns the topics partial; responds 404 if the topic does not exist. |
