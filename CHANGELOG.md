# Changelog

## Unreleased

- Added POST /topics/{id}/vote: cast or move the browser's single vote (cookie-based voter id, stored server-side)
- Added GET /moderate and POST /moderate/topics/{id}/answer|delete: Basic-auth moderator page to mark topics answered or delete them (answered topics sink to the bottom, greyed out)
- Added GET /export.md: all questions as Markdown sorted by votes, with author, vote count and answered status
