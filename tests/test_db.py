import json
from contextlib import closing

from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.conftest import ORGANIZER_TITLES


def organizer_titles():
    return sorted(t["title"] for t in db.list_topics() if t["source"] == "organizer")


def test_load_organizer_topics_is_idempotent(temp_env):
    db.init_db()
    db.load_organizer_topics(temp_env)
    db.load_organizer_topics(temp_env)
    assert organizer_titles() == sorted(ORGANIZER_TITLES)


def test_app_restart_does_not_duplicate_organizer_topics():
    for _ in range(3):
        with TestClient(app):
            pass
    assert organizer_titles() == sorted(ORGANIZER_TITLES)


def test_load_skips_invalid_entries(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps([{"title": "  "}, {"title": "x" * 281}, {"title": "ok"}])
    )
    db.init_db()
    db.load_organizer_topics(path)
    assert organizer_titles() == ["ok"]


def test_load_missing_file_is_ignored(tmp_path):
    db.init_db()
    db.load_organizer_topics(tmp_path / "missing.json")
    assert db.list_topics() == []


def test_attendee_can_reuse_organizer_title(temp_env):
    db.init_db()
    db.load_organizer_topics(temp_env)
    db.add_topic(ORGANIZER_TITLES[0], None)
    db.load_organizer_topics(temp_env)
    titles = [t["title"] for t in db.list_topics()]
    assert titles.count(ORGANIZER_TITLES[0]) == 2


def test_list_topics_newest_first():
    db.init_db()
    for title in ["first", "second", "third"]:
        db.add_topic(title, None)
    assert [t["title"] for t in db.list_topics()] == ["third", "second", "first"]


def test_list_topics_same_timestamp_tiebreak_by_id():
    db.init_db()
    for title in ["first", "second"]:
        db.add_topic(title, None)
    with closing(db.connect()) as conn, conn:
        conn.execute("UPDATE topics SET created_at = '2026-01-01T00:00:00.000Z'")
    assert [t["title"] for t in db.list_topics()] == ["second", "first"]


def test_cast_vote_unknown_topic_returns_false():
    db.init_db()
    assert db.cast_vote("voter-1", 12345) is False
    assert db.get_vote("voter-1") is None


def test_cast_vote_one_vote_per_voter():
    db.init_db()
    a = db.add_topic("a", None)
    b = db.add_topic("b", None)
    assert db.cast_vote("voter-1", a)
    assert db.cast_vote("voter-1", a)
    assert db.cast_vote("voter-1", b)
    assert db.get_vote("voter-1") == b
    assert {t["title"]: t["vote_count"] for t in db.list_topics()} == {"a": 0, "b": 1}
