#!/bin/bash
# Stop: Claude can't finish while tests fail.
input=$(cat)
# Avoid infinite loops: if we already forced a retry, let it stop.
if echo "$input" | grep -q '"stop_hook_active": *true'; then exit 0; fi
cd "$CLAUDE_PROJECT_DIR" || exit 0
out=$(uv run pytest -q 2>&1)
if [ $? -ne 0 ]; then
  echo "Tests are failing. Fix them before finishing:" >&2
  echo "$out" | tail -n 30 >&2
  exit 2
fi
exit 0