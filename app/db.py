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
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_votes_topic_id ON votes(topic_id);
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
    """Return all topics with vote counts, most votes first, then newest first."""
    return conn.execute(
        "SELECT t.id, t.title, t.author, t.source, t.created_at, "
        "COUNT(v.id) AS vote_count "
        "FROM topics t LEFT JOIN votes v ON v.topic_id = t.id "
        "GROUP BY t.id "
        "ORDER BY vote_count DESC, t.created_at DESC, t.id DESC"
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


def cast_vote(conn: sqlite3.Connection, voter_id: str, topic_id: int) -> bool:
    """Set the voter's single vote to topic_id; return False if the topic is missing."""
    with conn:
        if (
            conn.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,)).fetchone()
            is None
        ):
            return False
        conn.execute(
            "INSERT INTO votes (voter_id, topic_id) VALUES (?, ?) "
            "ON CONFLICT(voter_id) DO UPDATE SET topic_id = excluded.topic_id, "
            "created_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE votes.topic_id != excluded.topic_id",
            (voter_id, topic_id),
        )
    return True


def get_voted_topic_id(conn: sqlite3.Connection, voter_id: str) -> int | None:
    """Return the id of the topic this voter voted for, or None."""
    row = conn.execute(
        "SELECT topic_id FROM votes WHERE voter_id = ?", (voter_id,)
    ).fetchone()
    return row["topic_id"] if row else None
