from app import db


def test_load_organizer_topics_is_idempotent(temp_env):
    db.init_db()
    assert db.load_organizer_topics(["A", "B"]) == 2
    assert db.load_organizer_topics(["A", "B"]) == 0
    assert [t["title"] for t in db.list_topics()].count("A") == 1
    assert len(db.list_topics()) == 2


def test_attendee_can_duplicate_organizer_title(temp_env):
    db.init_db()
    db.load_organizer_topics(["Same"])
    db.create_topic("Same", None)
    assert len(db.list_topics()) == 2


def test_list_topics_newest_first(temp_env):
    db.init_db()
    first = db.create_topic("first", None)
    second = db.create_topic("second", "Ann")
    ids = [t["id"] for t in db.list_topics()]
    assert ids == [second, first]


def test_cast_vote_moves_single_vote(temp_env):
    db.init_db()
    a = db.create_topic("a", None)
    b = db.create_topic("b", None)
    db.cast_vote("v1", a)
    db.cast_vote("v1", a)
    assert db.voted_topic_id("v1") == a
    db.cast_vote("v1", b)
    assert db.voted_topic_id("v1") == b
    counts = {t["title"]: t["votes"] for t in db.list_topics()}
    assert counts == {"a": 0, "b": 1}


def test_cast_vote_unknown_topic_rejected_by_db(temp_env):
    import sqlite3

    import pytest

    db.init_db()
    with pytest.raises(sqlite3.IntegrityError):
        db.cast_vote("v1", 12345)
