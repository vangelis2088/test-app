import json
import sqlite3
from pathlib import Path

MAX_TITLE_LENGTH = 280

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND {MAX_TITLE_LENGTH}),
    author TEXT,
    source TEXT NOT NULL CHECK (source IN ('organizer', 'attendee')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_topics_organizer_title
    ON topics(title) WHERE source = 'organizer';
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def create_topic(conn: sqlite3.Connection, title: str, author: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO topics (title, author, source) VALUES (?, ?, 'attendee')",
        (title, author),
    )
    conn.commit()
    return cur.lastrowid


def list_topics(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, title, author, source, created_at FROM topics "
        "ORDER BY created_at DESC, id DESC"
    ).fetchall()


def load_organizer_topics(conn: sqlite3.Connection, path: str | Path) -> None:
    """Insert organizer topics from a JSON list; safe to call repeatedly."""
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for entry in entries:
        title = str(entry.get("title", "")).strip()
        if 1 <= len(title) <= MAX_TITLE_LENGTH:
            rows.append((title,))
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO topics (title, source) VALUES (?, 'organizer')",
            rows,
        )
