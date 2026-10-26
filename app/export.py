import re

from fastapi import APIRouter
from fastapi.responses import Response

from app import db

router = APIRouter()

_HTML = {"<": "&lt;", ">": "&gt;", "&": "&amp;"}
_ESCAPE = set("\\`*_{}[]()#+-.!|~:\"'=^$%@/")


def md_escape(text: str) -> str:
    """Flatten whitespace and neutralize Markdown/HTML-significant characters."""
    flat = re.sub(r"\s+", " ", text).strip()
    return "".join(_HTML.get(c) or ("\\" + c if c in _ESCAPE else c) for c in flat)


def render_markdown(rows) -> str:
    lines = ["# Questions", ""]
    if not rows:
        lines.append("_No questions yet._")
    for n, row in enumerate(rows, 1):
        author = md_escape(row["author"] or "") or "_anonymous_"
        title = md_escape(row["title"]) or "_untitled_"
        count = row["votes"]
        line = (
            f"{n}\\. **{title}** — by {author}"
            f" — {count} vote{'' if count == 1 else 's'}"
        )
        line += " — " + ("answered" if row["answered"] else "unanswered")
        lines.append(line)
    return "\n".join(lines) + "\n"


@router.get("/export.md")
def export_markdown():
    rows = db.list_topics_for_export()
    return Response(
        render_markdown(rows),
        media_type="text/markdown; charset=utf-8",
        headers={"X-Content-Type-Options": "nosniff"},
    )
