import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def client(app_env):
    with TestClient(app) as client:
        yield client


def count_rows(db_path):
    conn = db.connect(db_path)
    try:
        return len(db.list_topics(conn))
    finally:
        conn.close()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_shows_form_and_organizer_topics(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'hx-post="/topics"' in response.text
    assert "Organizer topic one" in response.text
    assert "Organizer's pick" in response.text


def test_create_topic_returns_partial(client):
    response = client.post("/topics", data={"title": "  New idea  ", "author": "Ada"})
    assert response.status_code == 200
    assert 'id="topic-list"' in response.text
    assert "<html" not in response.text
    assert "New idea" in response.text
    assert "Ada" in response.text


def test_create_topic_without_author(client, db_path):
    response = client.post("/topics", data={"title": "Anonymous idea"})
    assert response.status_code == 200
    conn = db.connect(db_path)
    try:
        row = db.list_topics(conn)[0]
    finally:
        conn.close()
    assert row["title"] == "Anonymous idea"
    assert row["author"] is None


@pytest.mark.parametrize("title", ["", "   ", "x" * 281])
def test_create_topic_validation(client, db_path, title):
    before = count_rows(db_path)
    response = client.post("/topics", data={"title": title})
    assert response.status_code == 422
    assert response.headers["HX-Retarget"] == "#form-error"
    assert 'class="error"' in response.text
    assert count_rows(db_path) == before


def test_create_topic_max_length_ok(client):
    response = client.post("/topics", data={"title": "x" * 280})
    assert response.status_code == 200


def test_topics_newest_first(client):
    client.post("/topics", data={"title": "First attendee topic"})
    client.post("/topics", data={"title": "Second attendee topic"})
    text = client.get("/topics").text
    second = text.index("Second attendee topic")
    first = text.index("First attendee topic")
    organizer = text.index("Organizer topic one")
    assert second < first < organizer


def test_topics_partial_polls(client):
    response = client.get("/topics")
    assert response.status_code == 200
    assert 'hx-trigger="every 3s"' in response.text
    assert "<html" not in response.text


def test_title_is_escaped(client):
    response = client.post("/topics", data={"title": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_restart_does_not_duplicate_organizer_topics(app_env, db_path):
    with TestClient(app):
        pass
    with TestClient(app):
        pass
    assert count_rows(db_path) == 2
