"""All SQL for the app lives here."""

import os
import sqlite3
from contextlib import closing

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
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)


def create_topic(title: str, author: str | None, source: str = "attendee") -> int:
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO topics (title, author, source) VALUES (?, ?, ?)",
            (title, author, source),
        )
        return cur.lastrowid


def load_organizer_topics(titles: list[str]) -> int:
    """Insert organizer topics, skipping ones already present. Returns rows inserted."""
    with closing(connect()) as conn, conn:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO topics (title, source) VALUES (?, 'organizer')",
            [(t,) for t in titles],
        )
        return conn.total_changes - before


def list_topics() -> list[sqlite3.Row]:
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT id, title, author, source, created_at FROM topics "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
