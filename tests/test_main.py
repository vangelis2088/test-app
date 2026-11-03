from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.conftest import ORGANIZER_TITLES


def test_index_shows_form_and_organizer_badge(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'hx-post="/topics"' in resp.text
    assert 'hx-trigger="every 3s"' in resp.text
    for title in ORGANIZER_TITLES:
        assert title in resp.text
    assert "Organizer's pick" in resp.text


def test_topics_partial(client):
    resp = client.get("/topics")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert ORGANIZER_TITLES[0] in resp.text


def test_create_topic(client):
    resp = client.post("/topics", data={"title": "  My topic  ", "author": "Ann"})
    assert resp.status_code == 200
    assert "My topic" in resp.text
    assert "Ann" in resp.text
    assert "<html" not in resp.text
    row = db.list_topics()[0]
    assert (row["title"], row["author"], row["source"]) == (
        "My topic",
        "Ann",
        "attendee",
    )


def test_author_is_optional(client):
    resp = client.post("/topics", data={"title": "No name"})
    assert resp.status_code == 200
    assert db.list_topics()[0]["author"] is None
    assert "Anonymous" in resp.text


def test_empty_title_rejected(client):
    before = len(db.list_topics())
    for title in ["", "   "]:
        resp = client.post("/topics", data={"title": title})
        assert resp.status_code == 422
        assert "Please enter a topic" in resp.text
    assert len(db.list_topics()) == before


def test_title_length_limit(client):
    before = len(db.list_topics())
    resp = client.post("/topics", data={"title": "x" * 281})
    assert resp.status_code == 422
    assert "at most 280" in resp.text
    assert len(db.list_topics()) == before

    resp = client.post("/topics", data={"title": "y" * 280})
    assert resp.status_code == 200
    assert len(db.list_topics()) == before + 1


def test_topics_newest_first(client):
    client.post("/topics", data={"title": "Topic A"})
    client.post("/topics", data={"title": "Topic B"})
    text = client.get("/topics").text
    assert (
        text.index("Topic B") < text.index("Topic A") < text.index(ORGANIZER_TITLES[0])
    )


def test_restart_does_not_duplicate_organizer_topics(temp_env):
    for _ in range(3):
        with TestClient(app):
            pass
    organizer = [t for t in db.list_topics() if t["source"] == "organizer"]
    assert sorted(t["title"] for t in organizer) == sorted(ORGANIZER_TITLES)
