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


def topic_id(db_path, title):
    conn = db.connect(db_path)
    try:
        return next(r["id"] for r in db.list_topics(conn) if r["title"] == title)
    finally:
        conn.close()


def votes_by_title(db_path):
    conn = db.connect(db_path)
    try:
        return {r["title"]: r["vote_count"] for r in db.list_topics(conn)}
    finally:
        conn.close()


def test_voter_cookie_is_issued(client):
    response = client.get("/")
    assert len(response.cookies["voter_id"]) == 32


def test_invalid_voter_cookie_is_replaced(client):
    client.cookies.set("voter_id", "not-a-valid-id")
    response = client.get("/")
    assert response.cookies["voter_id"] != "not-a-valid-id"


def test_index_shows_vote_buttons_and_counts(client, db_path):
    tid = topic_id(db_path, "Organizer topic one")
    text = client.get("/").text
    assert f'hx-post="/topics/{tid}/vote"' in text
    assert "0 votes" in text


def test_first_vote(client, db_path):
    client.get("/")
    tid = topic_id(db_path, "Organizer topic one")
    response = client.post(f"/topics/{tid}/vote")
    assert response.status_code == 200
    assert 'id="topic-list"' in response.text
    assert "<html" not in response.text
    assert 'class="voted"' in response.text
    assert "1 vote<" in response.text
    assert votes_by_title(db_path)["Organizer topic one"] == 1


def test_moving_a_vote(client, db_path):
    one = topic_id(db_path, "Organizer topic one")
    two = topic_id(db_path, "Organizer topic two")
    client.post(f"/topics/{one}/vote")
    response = client.post(f"/topics/{two}/vote")
    assert response.status_code == 200
    counts = votes_by_title(db_path)
    assert counts["Organizer topic one"] == 0
    assert counts["Organizer topic two"] == 1
    assert response.text.count('class="voted"') == 1


def test_repeat_vote_does_nothing(client, db_path):
    tid = topic_id(db_path, "Organizer topic one")
    client.post(f"/topics/{tid}/vote")
    response = client.post(f"/topics/{tid}/vote")
    assert response.status_code == 200
    assert votes_by_title(db_path)["Organizer topic one"] == 1


def test_vote_unknown_topic(client, db_path):
    response = client.post("/topics/999999/vote")
    assert response.status_code == 404
    assert sum(votes_by_title(db_path).values()) == 0


def test_vote_invalid_topic_id(client):
    response = client.post("/topics/abc/vote")
    assert response.status_code == 422


def test_separate_browsers_each_get_one_vote(client, db_path):
    tid = topic_id(db_path, "Organizer topic one")
    client.post(f"/topics/{tid}/vote")
    client.cookies.clear()
    response = client.post(f"/topics/{tid}/vote")
    assert "2 votes" in response.text
    assert votes_by_title(db_path)["Organizer topic one"] == 2


def test_list_sorted_by_votes_then_newest(client, db_path):
    client.post("/topics", data={"title": "Newest attendee topic"})
    two = topic_id(db_path, "Organizer topic two")
    client.post(f"/topics/{two}/vote")
    text = client.get("/topics").text
    assert (
        text.index("Organizer topic two")
        < text.index("Newest attendee topic")
        < text.index("Organizer topic one")
    )
