import json

import pytest


def test_create_and_list_topic(db):
    topic_id = db.create_topic("  Async all the things  ", "  Ada ")
    [topic] = db.list_topics()
    assert topic["id"] == topic_id
    assert topic["title"] == "Async all the things"
    assert topic["author"] == "Ada"
    assert topic["source"] == "attendee"
    assert topic["created_at"]


def test_blank_author_is_stored_as_null(db):
    db.create_topic("Topic", "   ")
    assert db.list_topics()[0]["author"] is None


@pytest.mark.parametrize("title", ["", "   ", "x" * 281])
def test_validate_title_rejects(title):
    from app.db import validate_title

    with pytest.raises(ValueError):
        validate_title(title)


def test_validate_title_accepts_max_length():
    from app.db import validate_title

    assert validate_title("x" * 280) == "x" * 280


def test_create_topic_rejects_invalid_title(db):
    with pytest.raises(ValueError):
        db.create_topic("")
    assert db.list_topics() == []


def test_list_topics_newest_first(db, monkeypatch):
    db.create_topic("first")
    db.create_topic("second")
    db.create_topic("third")
    assert [t["title"] for t in db.list_topics()] == ["third", "second", "first"]


def test_list_topics_same_timestamp_uses_id(db, monkeypatch):
    monkeypatch.setattr(db, "_now", lambda: "2026-01-01T00:00:00+00:00")
    db.create_topic("a")
    db.create_topic("b")
    assert [t["title"] for t in db.list_topics()] == ["b", "a"]


def test_load_organizer_topics_is_idempotent(db, tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps([{"title": "One"}, {"title": "Two"}]))
    db.load_organizer_topics(path)
    db.load_organizer_topics(path)
    topics = db.list_topics()
    assert sorted(t["title"] for t in topics) == ["One", "Two"]
    assert {t["source"] for t in topics} == {"organizer"}


def test_attendee_topic_may_match_organizer_title(db, tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps([{"title": "One"}]))
    db.load_organizer_topics(path)
    db.create_topic("One")
    assert len(db.list_topics()) == 2


def test_load_organizer_topics_skips_invalid_entries(db, tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps([{"title": ""}, {"nope": 1}, "bad", {"title": "Good"}]))
    db.load_organizer_topics(path)
    assert [t["title"] for t in db.list_topics()] == ["Good"]


def test_load_organizer_topics_missing_file(db, tmp_path):
    db.load_organizer_topics(tmp_path / "missing.json")
    assert db.list_topics() == []
