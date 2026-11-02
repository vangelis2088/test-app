import json

import pytest

from app import db


@pytest.fixture
def conn(db_path):
    conn = db.connect(db_path)
    db.init_db(conn)
    yield conn
    conn.close()


def test_create_and_list(conn):
    topic_id = db.create_topic(conn, "Hello", "Ada")
    [row] = db.list_topics(conn)
    assert row["id"] == topic_id
    assert row["title"] == "Hello"
    assert row["author"] == "Ada"
    assert row["source"] == "attendee"
    assert row["created_at"]


def test_list_newest_first(conn):
    db.create_topic(conn, "A", None)
    db.create_topic(conn, "B", None)
    db.create_topic(conn, "C", None)
    assert [r["title"] for r in db.list_topics(conn)] == ["C", "B", "A"]


def test_load_organizer_topics_is_idempotent(conn, topics_file):
    db.load_organizer_topics(conn, topics_file)
    db.load_organizer_topics(conn, topics_file)
    rows = db.list_topics(conn)
    assert len(rows) == 2
    assert {r["source"] for r in rows} == {"organizer"}


def test_load_organizer_topics_dedupes_and_skips_invalid(conn, tmp_path):
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps(
            [
                {"title": "Same"},
                {"title": " Same "},
                {"title": ""},
                {"title": "x" * 281},
            ]
        )
    )
    db.load_organizer_topics(conn, path)
    assert [r["title"] for r in db.list_topics(conn)] == ["Same"]


def test_attendee_can_duplicate_organizer_title(conn, topics_file):
    db.load_organizer_topics(conn, topics_file)
    db.create_topic(conn, "Organizer topic one", None)
    assert len(db.list_topics(conn)) == 3
