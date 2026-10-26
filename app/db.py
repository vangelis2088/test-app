import json
import os
import sqlite3
from pathlib import Path

MAX_TITLE_LEN = 280


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ.get("QA_DB_PATH", "qa.db"))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND {MAX_TITLE_LEN}),
                author TEXT,
                source TEXT NOT NULL CHECK(source IN ('organizer', 'attendee')),
                created_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_topics_organizer_title "
            "ON topics(title) WHERE source = 'organizer'"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id TEXT NOT NULL UNIQUE,
                topic_id INTEGER NOT NULL REFERENCES topics(id),
                created_at TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
    conn.close()


def load_organizer_topics() -> None:
    path = Path(os.environ.get("TOPICS_FILE", "data/topics.json"))
    if not path.exists():
        return
    items = json.loads(path.read_text())
    titles = [
        item["title"].strip()
        for item in items
        if isinstance(item, dict) and isinstance(item.get("title"), str)
    ]
    titles = [t for t in titles if 0 < len(t) <= MAX_TITLE_LEN]
    conn = get_conn()
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO topics (title, source) VALUES (?, 'organizer')",
            [(t,) for t in titles],
        )
    conn.close()


def add_topic(title: str, author: str | None) -> int:
    conn = get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO topics (title, author, source) VALUES (?, ?, 'attendee')",
            (title, author),
        )
    topic_id = cur.lastrowid
    conn.close()
    return topic_id


def cast_vote(voter_id: str, topic_id: int) -> bool:
    """Record or move the voter's single vote; False if the topic does not exist."""
    conn = get_conn()
    with conn:
        exists = conn.execute(
            "SELECT 1 FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if exists is not None:
            conn.execute(
                "INSERT INTO votes (voter_id, topic_id) VALUES (?, ?) "
                "ON CONFLICT(voter_id) DO UPDATE SET topic_id = excluded.topic_id "
                "WHERE votes.topic_id != excluded.topic_id",
                (voter_id, topic_id),
            )
    conn.close()
    return exists is not None


def list_topics(voter_id: str | None = None) -> list[sqlite3.Row]:
    """List topics by votes desc then newest first, flagging the voter's own vote."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT t.id, t.title, t.author, t.source, t.created_at,
               (SELECT COUNT(*) FROM votes v WHERE v.topic_id = t.id) AS votes,
               EXISTS(
                   SELECT 1 FROM votes v
                   WHERE v.topic_id = t.id AND v.voter_id = ?
               ) AS voted
        FROM topics t
        ORDER BY votes DESC, t.created_at DESC, t.id DESC
        """,
        (voter_id,),
    ).fetchall()
    conn.close()
    return rows
