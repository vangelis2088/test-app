#!/usr/bin/env python3
"""PreToolUse guard: secrets, HTML escaping, guardrail files, and shell edits."""

import json
import os
import re
import sys

data = json.load(sys.stdin)
tool = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

UNSAFE = {
    r"\|\s*safe\b": "the Jinja '|safe' filter",
    r"\bMarkup\(": "markupsafe.Markup()",
    r"autoescape\s*=\s*False": "autoescape=False",
    r"{%\s*autoescape\s+false": "{% autoescape false %}",
}
PROTECTED = ("/.claude/hooks/", "/.claude/settings.json")


def block(msg):
    print(f"BLOCKED by project policy: {msg}", file=sys.stderr)
    sys.exit(2)


def check_unsafe(text):
    for pattern, label in UNSAFE.items():
        if re.search(pattern, text):
            block(
                f"{label} disables HTML escaping (this caused the XSS fixed in "
                "Stage 3). User content must stay escaped. For line breaks use "
                "CSS `white-space: pre-wrap`; for rich text, propose a sanitizer "
                "and ask the human first."
            )


if tool == "Bash":
    cmd = tool_input.get("command", "")
    if re.search(r"(^|[\s/'\"=])\.env\b", cmd):
        block(".env holds secrets; the agent may never read or change it.")
    if re.search(r"\b(sed|perl)\b[^|;&]*\s-i", cmd) or re.search(
        r"(>|\btee\b)\s*[^\s|;&]*(templates|app|tests|\.claude)/", cmd
    ):
        block(
            "edit project files with the Edit/Write tools, not shell commands "
            "(sed -i, perl -i, redirects, tee), so every edit passes the guardrails."
        )
    check_unsafe(cmd)
    sys.exit(0)

path = tool_input.get("file_path", "")
name = os.path.basename(path)
if name == ".env" or name.startswith(".env."):
    block(".env holds secrets; the agent may never read or change it, even if asked.")
if any(p in path for p in PROTECTED):
    block("hooks and project settings are guardrails; the agent may not modify them.")
check_unsafe(tool_input.get("new_string") or tool_input.get("content") or "")
sys.exit(0)