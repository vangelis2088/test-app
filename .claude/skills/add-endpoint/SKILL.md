---
name: add-endpoint
description: Add a new HTTP endpoint to the Voting app following our house recipe. Use whenever the user asks for a new route, API endpoint, or action (e.g. upvote, delete, export).
---

# Add an endpoint

Requested endpoint: $ARGUMENTS

Follow these steps in order:

1. **Data layer**: add a function to `app/db.py` with a one-line docstring.
   Parameterized SQL only, never string formatting.
2. **Route**: add the route to `app/main.py`.
   - Validate input; return 422 for bad input and 404 for a missing resource.
   - Endpoints that change state and are called from the page return the
     `_topics.html` partial so htmx can swap it in.
3. **Tests**: in the matching test file add at least:
   happy path, not-found (if an id is involved), invalid input.
4. **Changelog**: add a line under `## Unreleased` in `CHANGELOG.md`
   (create the file if missing): `- Added METHOD /path: short description`.
5. **Verify**: run ruff and the tests as described in CLAUDE.md.
6. **Report** in exactly this format and nothing else:

   ✅ Endpoint added: `METHOD /path`
   🧪 Tests: <N passed>
   📝 Changelog updated