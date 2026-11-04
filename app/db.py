import json
import logging
import os
import sqlite3
from contextlib import closing
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 280

SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 280),
    author TEXT,
    source TEXT NOT NULL CHECK (source IN ('organizer', 'attendee')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_organizer_title
    ON topics(title) WHERE source = 'organizer';
"""


def db_path() -> str:
    return os.environ.get("QA_DB_PATH", "qa.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(connect()) as conn, conn:
        conn.executescript(SCHEMA)


def is_valid_title(title: str) -> bool:
    return 0 < len(title) <= MAX_TITLE_LENGTH


def add_topic(title: str, author: str | None, source: str = "attendee") -> int:
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO topics (title, author, source) VALUES (?, ?, ?)",
            (title, author, source),
        )
        return cur.lastrowid


def list_topics() -> list[sqlite3.Row]:
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT id, title, author, source, created_at FROM topics "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()


def load_organizer_topics(path: str | Path) -> None:
    path = Path(path)
    if not path.exists():
        logger.warning("Organizer topics file %s not found; skipping", path)
        return
    entries = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for entry in entries:
        title = str(entry.get("title", "")).strip()
        if not is_valid_title(title):
            logger.warning("Skipping invalid organizer topic: %r", entry)
            continue
        rows.append((title,))
    with closing(connect()) as conn, conn:
        conn.executemany(
            "INSERT OR IGNORE INTO topics (title, source) VALUES (?, 'organizer')",
            rows,
        )
