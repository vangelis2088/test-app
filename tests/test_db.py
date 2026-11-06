import json

import pytest

from app import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


def write_topics(tmp_path, items):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def test_create_and_list():
    topic_id = db.create_topic("Hello", "Ada")
    rows = db.list_topics()
    assert len(rows) == 1
    assert rows[0]["id"] == topic_id
    assert rows[0]["title"] == "Hello"
    assert rows[0]["author"] == "Ada"
    assert rows[0]["source"] == "attendee"
    assert rows[0]["created_at"]


def test_list_newest_first():
    db.create_topic("first")
    db.create_topic("second")
    db.create_topic("third")
    assert [r["title"] for r in db.list_topics()] == ["third", "second", "first"]


def test_list_same_timestamp_tie_breaks_by_id():
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO topics (title, source, created_at) VALUES (?, 'attendee', ?)",
            [("a", "2026-01-01T00:00:00.000Z"), ("b", "2026-01-01T00:00:00.000Z")],
        )
    conn.close()
    assert [r["title"] for r in db.list_topics()] == ["b", "a"]


def test_load_organizer_topics_is_idempotent(tmp_path):
    path = write_topics(tmp_path, [{"title": "Keynote"}, {"title": "Panel"}])
    db.load_organizer_topics(path)
    db.load_organizer_topics(path)
    rows = db.list_topics()
    assert sorted(r["title"] for r in rows) == ["Keynote", "Panel"]
    assert all(r["source"] == "organizer" for r in rows)


def test_load_organizer_topics_dedupes_within_file(tmp_path):
    path = write_topics(tmp_path, [{"title": "Same"}, {"title": " Same "}])
    db.load_organizer_topics(path)
    assert [r["title"] for r in db.list_topics()] == ["Same"]


def test_attendee_topic_with_organizer_title_is_allowed(tmp_path):
    db.load_organizer_topics(write_topics(tmp_path, [{"title": "Same"}]))
    db.create_topic("Same")
    assert len(db.list_topics()) == 2


@pytest.mark.parametrize(
    "items",
    [
        {"title": "not a list"},
        [{"name": "x"}],
        ["x"],
        [{"title": ""}],
        [{"title": "x" * 281}],
    ],
)
def test_load_organizer_topics_rejects_invalid(tmp_path, items):
    with pytest.raises((TypeError, ValueError)):
        db.load_organizer_topics(write_topics(tmp_path, items))
    assert db.list_topics() == []


def test_validate_title():
    assert db.validate_title("  hi  ") == "hi"
    assert db.validate_title("x" * 280) == "x" * 280
    for bad in ["", "   ", "x" * 281]:
        with pytest.raises(ValueError):
            db.validate_title(bad)


def test_cast_vote_moves_and_is_idempotent():
    a = db.create_topic("a")
    b = db.create_topic("b")
    db.cast_vote("voter1", a)
    db.cast_vote("voter1", a)
    assert db.voted_topic_id("voter1") == a
    db.cast_vote("voter1", b)
    assert db.voted_topic_id("voter1") == b
    assert {r["title"]: r["votes"] for r in db.list_topics()} == {"a": 0, "b": 1}


def test_voted_topic_id_unknown_voter():
    assert db.voted_topic_id("nobody") is None
    assert db.voted_topic_id(None) is None


def test_topic_exists():
    tid = db.create_topic("x")
    assert db.topic_exists(tid)
    assert not db.topic_exists(tid + 1)


def test_list_sorts_by_votes_then_newest():
    old = db.create_topic("old")
    db.create_topic("new")
    db.cast_vote("v1", old)
    assert [r["title"] for r in db.list_topics()] == ["old", "new"]
