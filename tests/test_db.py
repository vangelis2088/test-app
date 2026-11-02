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


def vote_counts(conn):
    return {r["title"]: r["vote_count"] for r in db.list_topics(conn)}


def test_cast_vote_first_vote(conn):
    topic_id = db.create_topic(conn, "A", None)
    assert db.cast_vote(conn, "voter1", topic_id) is True
    assert vote_counts(conn) == {"A": 1}
    assert db.get_voted_topic_id(conn, "voter1") == topic_id


def test_cast_vote_moves_vote(conn):
    a = db.create_topic(conn, "A", None)
    b = db.create_topic(conn, "B", None)
    db.cast_vote(conn, "voter1", a)
    db.cast_vote(conn, "voter1", b)
    assert vote_counts(conn) == {"A": 0, "B": 1}
    assert db.get_voted_topic_id(conn, "voter1") == b


def test_cast_vote_repeat_is_noop(conn):
    a = db.create_topic(conn, "A", None)
    db.cast_vote(conn, "voter1", a)
    db.cast_vote(conn, "voter1", a)
    assert vote_counts(conn) == {"A": 1}


def test_cast_vote_unknown_topic(conn):
    assert db.cast_vote(conn, "voter1", 999) is False
    assert db.get_voted_topic_id(conn, "voter1") is None


def test_list_sorted_by_votes_then_newest(conn):
    a = db.create_topic(conn, "A", None)
    db.create_topic(conn, "B", None)
    c = db.create_topic(conn, "C", None)
    db.create_topic(conn, "D", None)
    db.cast_vote(conn, "v1", a)
    db.cast_vote(conn, "v2", a)
    db.cast_vote(conn, "v3", c)
    assert [r["title"] for r in db.list_topics(conn)] == ["A", "C", "D", "B"]
