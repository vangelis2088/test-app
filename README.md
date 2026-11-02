## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check; returns `{"status": "ok"}`. |
| GET | `/` | Full HTML page listing topics (answered last, then by votes). Sets a `voter_id` cookie if missing or malformed. |
| GET | `/topics` | HTML partial (`_topics.html`) with the current topic list, for htmx. |
| POST | `/topics` | Create a topic from form fields `title` (required, length-limited) and `author` (optional). Returns the topic list partial; responds 422 with an error message if the title is empty or too long. |
| POST | `/topics/{topic_id}/vote` | Cast or move the browser's single vote (identified by the `voter_id` cookie) to the topic. Returns the topic list partial; 404 if the topic does not exist. |
| GET | `/moderate` | Moderator page. HTTP Basic auth with `ADMIN_PASSWORD`; 403 if the variable is unset, 401 on a wrong password. |
| POST | `/moderate/topics/{topic_id}/answer` | Mark a topic as answered. Requires Basic auth and the `HX-Request: true` header. Returns the moderation list partial; 404 if not found. |
| POST | `/moderate/topics/{topic_id}/delete` | Delete a topic. Requires Basic auth and the `HX-Request: true` header. Returns the moderation list partial; 404 if not found. |
| GET | `/export.md` | All topics as Markdown, sorted by votes, with author, vote count and answered status. |
