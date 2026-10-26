#!/bin/bash
# PostToolUse: auto-format any Python file Claude just edited.
path=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')
if [[ "$path" == *.py ]]; then
  cd "$CLAUDE_PROJECT_DIR" || exit 0
  uv run ruff check --fix --quiet "$path" >/dev/null 2>&1
  uv run ruff format --quiet "$path" >/dev/null 2>&1
fi
exit 0