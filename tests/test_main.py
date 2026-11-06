import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def env(tmp_path, monkeypatch):
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps([{"title": "Organizer topic"}]), encoding="utf-8")
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))


@pytest.fixture
def client(env):
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_shows_form_and_organizer_badge(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'hx-post="/topics"' in response.text
    assert 'hx-trigger="every 3s"' in response.text
    assert "Organizer topic" in response.text
    assert "Organizer's pick" in response.text


def test_create_topic_returns_partial(client):
    response = client.post("/topics", data={"title": "  My topic  ", "author": "Ada"})
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "My topic" in response.text
    assert "by Ada" in response.text
    created = [r for r in db.list_topics() if r["source"] == "attendee"]
    assert [(r["title"], r["author"]) for r in created] == [("My topic", "Ada")]


def test_create_topic_without_author(client):
    response = client.post("/topics", data={"title": "Anon", "author": "  "})
    assert response.status_code == 200
    assert "by anonymous" in response.text
    assert db.list_topics()[0]["author"] is None


@pytest.mark.parametrize("title", ["", "   ", "x" * 281])
def test_create_topic_validation(client, title):
    response = client.post("/topics", data={"title": title})
    assert response.status_code == 422
    assert 'class="error"' in response.text
    assert [r["source"] for r in db.list_topics()] == ["organizer"]


def test_create_topic_missing_title(client):
    response = client.post("/topics", data={})
    assert response.status_code == 422


def test_create_topic_max_length_ok(client):
    response = client.post("/topics", data={"title": "x" * 280})
    assert response.status_code == 200


def test_topics_partial_newest_first(client):
    client.post("/topics", data={"title": "older"})
    client.post("/topics", data={"title": "newer"})
    response = client.get("/topics")
    assert response.status_code == 200
    assert "<html" not in response.text
    text = response.text
    assert text.index("newer") < text.index("older") < text.index("Organizer topic")


def test_restart_does_not_duplicate_organizer_topics(env):
    with TestClient(app):
        pass
    with TestClient(app) as c:
        response = c.get("/topics")
    assert response.text.count("Organizer topic") == 1
    assert len(db.list_topics()) == 1


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    '<div hx-post="/topics/1/vote" hx-trigger="load">x</div>',
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_titles_are_escaped(client, payload):
    """Attendee titles are HTML-escaped in the POST response, the poll partial and the page."""
    post = client.post("/topics", data={"title": payload})
    assert post.status_code == 200
    escaped = (
        payload.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&#34;")
    )
    for response in (post, client.get("/topics"), client.get("/")):
        assert payload not in response.text
        assert escaped in response.text


def test_organizer_titles_are_escaped(tmp_path, monkeypatch):
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps([{"title": "<b>bold</b>"}]), encoding="utf-8")
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))
    with TestClient(app) as c:
        text = c.get("/").text
    assert "<b>bold</b>" not in text
    assert "&lt;b&gt;bold&lt;/b&gt;" in text


def topic_id(title):
    return next(r["id"] for r in db.list_topics() if r["title"] == title)


def votes_by_title():
    return {r["title"]: r["votes"] for r in db.list_topics()}


def test_first_visit_sets_voter_cookie(client):
    response = client.get("/")
    assert len(response.cookies["voter_id"]) == 22


def test_first_vote(client):
    client.post("/topics", data={"title": "A"})
    response = client.post(f"/topics/{topic_id('A')}/vote")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert votes_by_title() == {"A": 1, "Organizer topic": 0}
    assert 'class="topic voted"' in response.text
    assert "1 vote<" in response.text


def test_moving_a_vote(client):
    client.post("/topics", data={"title": "A"})
    client.post(f"/topics/{topic_id('A')}/vote")
    client.post(f"/topics/{topic_id('Organizer topic')}/vote")
    assert votes_by_title() == {"A": 0, "Organizer topic": 1}
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 1
    conn.close()


def test_repeat_vote_does_nothing(client):
    tid = topic_id("Organizer topic")
    client.post(f"/topics/{tid}/vote")
    response = client.post(f"/topics/{tid}/vote")
    assert response.status_code == 200
    assert votes_by_title() == {"Organizer topic": 1}


def test_vote_unknown_topic_returns_404(client):
    response = client.post("/topics/9999/vote")
    assert response.status_code == 404
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
    conn.close()


def test_vote_invalid_topic_id_returns_422(client):
    assert client.post("/topics/abc/vote").status_code == 422


def test_each_browser_has_one_vote_and_list_sorts_by_votes(client):
    client.post("/topics", data={"title": "older"})
    client.post("/topics", data={"title": "newer"})
    for _ in range(2):
        client.cookies.clear()
        client.post(f"/topics/{topic_id('older')}/vote")
    client.cookies.clear()
    client.post(f"/topics/{topic_id('Organizer topic')}/vote")
    assert votes_by_title() == {"older": 2, "Organizer topic": 1, "newer": 0}
    text = client.get("/topics").text
    assert text.index("older") < text.index("Organizer topic") < text.index("newer")


def test_tampered_cookie_is_replaced(client):
    client.cookies.set("voter_id", "not-a-valid-id")
    response = client.post(f"/topics/{topic_id('Organizer topic')}/vote")
    assert response.cookies["voter_id"] != "not-a-valid-id"
    assert votes_by_title() == {"Organizer topic": 1}


def test_highlight_only_for_this_browser(client):
    client.post(f"/topics/{topic_id('Organizer topic')}/vote")
    assert 'class="topic voted"' in client.get("/topics").text
    client.cookies.clear()
    text = client.get("/topics").text
    assert 'class="topic voted"' not in text
    assert "1 vote<" in text
