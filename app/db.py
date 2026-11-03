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
CREATE TABLE IF NOT EXISTS votes (
    voter_id TEXT PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_votes_topic ON votes(topic_id);
"""


def db_path() -> str:
    return os.environ.get("QA_DB_PATH", "qa.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
    """Return all topics with vote counts, most votes first, then newest first."""
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT t.id, t.title, t.author, t.source, t.created_at, "
            "COUNT(v.voter_id) AS votes "
            "FROM topics t LEFT JOIN votes v ON v.topic_id = t.id "
            "GROUP BY t.id "
            "ORDER BY votes DESC, t.created_at DESC, t.id DESC"
        ).fetchall()


def topic_exists(topic_id: int) -> bool:
    """Return True if a topic with this id exists."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,)).fetchone()
        return row is not None


def cast_vote(voter_id: str, topic_id: int) -> None:
    """Record the voter's single vote, moving it if they already voted elsewhere."""
    with closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO votes (voter_id, topic_id) VALUES (?, ?) "
            "ON CONFLICT(voter_id) DO UPDATE SET topic_id = excluded.topic_id "
            "WHERE votes.topic_id != excluded.topic_id",
            (voter_id, topic_id),
        )


def voted_topic_id(voter_id: str | None) -> int | None:
    """Return the id of the topic this voter voted for, if any."""
    if not voter_id:
        return None
    with closing(connect()) as conn:
        row = conn.execute(
            "SELECT topic_id FROM votes WHERE voter_id = ?", (voter_id,)
        ).fetchone()
        return row["topic_id"] if row else None
