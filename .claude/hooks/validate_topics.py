#!/usr/bin/env python3
"""PostToolUse: validate data/topics.json after Claude edits it."""

import json
import sys

data = json.load(sys.stdin)
path = data.get("tool_input", {}).get("file_path", "")
if not path.endswith("data/topics.json"):
    sys.exit(0)


def fail(msg):
    print(f"INVALID data/topics.json: {msg} Fix the file so it passes.", file=sys.stderr)
    sys.exit(2)


try:
    with open(path, encoding="utf-8") as f:
        topics = json.load(f)
except (OSError, json.JSONDecodeError) as e:
    fail(f"not valid JSON ({e}).")
if not isinstance(topics, list):
    fail("the top level must be a list.")

seen = set()
for i, t in enumerate(topics, 1):
    title = t.get("title", "").strip() if isinstance(t, dict) else ""
    if not title:
        fail(f"entry {i} has no title.")
    if len(title) > 280:
        fail(f"entry {i} is {len(title)} characters; the limit is 280.")
    if title.casefold() in seen:
        fail(f"entry {i} duplicates '{title}'.")
    seen.add(title.casefold())
sys.exit(0)