"""All SQL for the app lives here."""

import json
import os
import sqlite3
from pathlib import Path

MAX_TITLE_LENGTH = 280

SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 280),
    author TEXT,
    source TEXT NOT NULL CHECK (source IN ('organizer', 'attendee')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_organizer_title
    ON topics (title) WHERE source = 'organizer';
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_votes_topic ON votes (topic_id);
"""


def db_path() -> str:
    return os.environ.get("QA_DB_PATH", "qa.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def validate_title(raw: str) -> str:
    title = raw.strip()
    if not title:
        raise ValueError("Title is required.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title must be at most {MAX_TITLE_LENGTH} characters.")
    return title


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
    conn.close()


def create_topic(
    title: str, author: str | None = None, source: str = "attendee"
) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO topics (title, author, source) VALUES (?, ?, ?)",
            (title, author, source),
        )
    conn.close()
    return cur.lastrowid


def list_topics() -> list[sqlite3.Row]:
    """Return all topics with vote counts, most votes first, then newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.id, t.title, t.author, t.source, t.created_at,"
            " COUNT(v.id) AS votes"
            " FROM topics t LEFT JOIN votes v ON v.topic_id = t.id"
            " GROUP BY t.id"
            " ORDER BY votes DESC, t.created_at DESC, t.id DESC"
        ).fetchall()
    conn.close()
    return rows


def topic_exists(topic_id: int) -> bool:
    """Return True if a topic with this id exists."""
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,)).fetchone()
    conn.close()
    return row is not None


def cast_vote(voter_id: str, topic_id: int) -> None:
    """Record voter's single vote for topic_id, moving any previous vote."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO votes (voter_id, topic_id) VALUES (?, ?)"
            " ON CONFLICT (voter_id) DO UPDATE SET topic_id = excluded.topic_id",
            (voter_id, topic_id),
        )
    conn.close()


def voted_topic_id(voter_id: str | None) -> int | None:
    """Return the topic id this voter currently votes for, if any."""
    if not voter_id:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT topic_id FROM votes WHERE voter_id = ?", (voter_id,)
        ).fetchone()
    conn.close()
    return row["topic_id"] if row else None


def load_organizer_topics(path: str | Path) -> None:
    """Insert organizer topics from a JSON list of {"title": ...}. Idempotent.

    Raises TypeError for a malformed file shape, ValueError for an invalid title.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError(f"{path}: expected a JSON list of topics")
    titles = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or not isinstance(item.get("title"), str):
            raise TypeError(f"{path}: item {i} must be an object with a string 'title'")
        try:
            titles.append(validate_title(item["title"]))
        except ValueError as e:
            raise ValueError(f"{path}: item {i}: {e}") from e
    with connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO topics (title, source) VALUES (?, 'organizer')",
            [(t,) for t in titles],
        )
    conn.close()
