import json
import sqlite3

import pytest

from app import db


@pytest.fixture
def conn_ready(env):
    db.init_db()


def test_add_and_list(conn_ready):
    topic_id = db.add_topic("Hello", "Ann")
    rows = db.list_topics()
    assert len(rows) == 1
    assert rows[0]["id"] == topic_id
    assert rows[0]["title"] == "Hello"
    assert rows[0]["author"] == "Ann"
    assert rows[0]["source"] == "attendee"
    assert rows[0]["created_at"]


def test_title_constraints(conn_ready):
    with pytest.raises(sqlite3.IntegrityError):
        db.add_topic("", None)
    with pytest.raises(sqlite3.IntegrityError):
        db.add_topic("x" * 281, None)
    db.add_topic("x" * 280, None)


def test_list_newest_first(conn_ready):
    first = db.add_topic("first", None)
    second = db.add_topic("second", None)
    third = db.add_topic("third", None)
    assert [r["id"] for r in db.list_topics()] == [third, second, first]


def test_load_organizer_topics_is_idempotent(conn_ready):
    db.load_organizer_topics()
    db.load_organizer_topics()
    db.init_db()
    db.load_organizer_topics()
    rows = db.list_topics()
    assert sorted(r["title"] for r in rows) == [
        "Organizer topic A",
        "Organizer topic B",
    ]
    assert all(r["source"] == "organizer" for r in rows)


def test_attendee_may_reuse_organizer_title(conn_ready):
    db.load_organizer_topics()
    db.add_topic("Organizer topic A", None)
    assert len(db.list_topics()) == 3


def test_load_skips_invalid_entries_and_missing_file(conn_ready, env, monkeypatch):
    bad = env / "bad.json"
    bad.write_text(
        json.dumps([{"title": ""}, {"title": "y" * 281}, {"nope": 1}, "str"])
    )
    monkeypatch.setenv("TOPICS_FILE", str(bad))
    db.load_organizer_topics()
    assert db.list_topics() == []
    monkeypatch.setenv("TOPICS_FILE", str(env / "missing.json"))
    db.load_organizer_topics()
    assert db.list_topics() == []


def _id(title):
    return next(r["id"] for r in db.list_topics() if r["title"] == title)


def test_cast_vote_unknown_topic(conn_ready):
    assert db.cast_vote("voter-1", 999) is False
    assert db.list_topics() == []


def test_vote_counts_and_one_vote_per_voter(conn_ready):
    a = db.add_topic("A", None)
    b = db.add_topic("B", None)
    assert db.cast_vote("v1", a)
    assert db.cast_vote("v1", a)
    assert db.cast_vote("v2", a)
    counts = {r["id"]: r["votes"] for r in db.list_topics()}
    assert counts == {a: 2, b: 0}
    assert db.cast_vote("v1", b)
    counts = {r["id"]: r["votes"] for r in db.list_topics()}
    assert counts == {a: 1, b: 1}


def test_list_sorted_by_votes_then_newest(conn_ready):
    old = db.add_topic("old", None)
    mid = db.add_topic("mid", None)
    new = db.add_topic("new", None)
    db.cast_vote("v1", old)
    assert [r["id"] for r in db.list_topics()] == [old, new, mid]


def test_voted_flag_is_per_voter(conn_ready):
    a = db.add_topic("A", None)
    db.cast_vote("v1", a)
    assert db.list_topics("v1")[0]["voted"] == 1
    assert db.list_topics("v2")[0]["voted"] == 0
    assert db.list_topics()[0]["voted"] == 0
