import json
import logging
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 280


def db_path() -> str:
    return os.environ.get("QA_DB_PATH", "qa.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(connect()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 280),
                author TEXT,
                source TEXT NOT NULL CHECK (source IN ('organizer', 'attendee')),
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS topics_organizer_title
                ON topics(title) WHERE source = 'organizer';
            """
        )


def validate_title(raw: str) -> str:
    title = (raw or "").strip()
    if not title:
        raise ValueError("Title is required.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title must be at most {MAX_TITLE_LENGTH} characters.")
    return title


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_topic(
    title: str, author: str | None = None, source: str = "attendee"
) -> int:
    title = validate_title(title)
    author = (author or "").strip() or None
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO topics (title, author, source, created_at) VALUES (?, ?, ?, ?)",
            (title, author, source, _now()),
        )
        return cur.lastrowid


def list_topics() -> list[sqlite3.Row]:
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT id, title, author, source, created_at FROM topics"
            " ORDER BY created_at DESC, id DESC"
        ).fetchall()


def load_organizer_topics(path: str | Path) -> None:
    path = Path(path)
    if not path.exists():
        logger.warning("Organizer topics file %s not found; skipping", path)
        return
    entries = json.loads(path.read_text())
    rows = []
    for entry in entries:
        try:
            title = validate_title(
                entry.get("title") if isinstance(entry, dict) else None
            )
        except ValueError as exc:
            logger.warning("Skipping invalid organizer topic %r: %s", entry, exc)
            continue
        rows.append((title, _now()))
    with closing(connect()) as conn, conn:
        conn.executemany(
            "INSERT OR IGNORE INTO topics (title, author, source, created_at)"
            " VALUES (?, NULL, 'organizer', ?)",
            rows,
        )
