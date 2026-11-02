from fastapi.testclient import TestClient

from app.main import app


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders_form_and_organizer_topics(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'hx-post="/topics"' in response.text
    assert 'hx-trigger="every 3s"' in response.text
    assert "Keynote: the future of Python" in response.text
    assert "Organizer's pick" in response.text


def test_get_topics_returns_partial(client):
    response = client.get("/topics")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "Keynote: the future of Python" in response.text


def test_post_topic_returns_updated_list_newest_first(client):
    client.post("/topics", data={"title": "Older"})
    response = client.post("/topics", data={"title": "Newer", "name": "Ada"})
    assert response.status_code == 200
    assert "<html" not in response.text
    text = response.text
    assert text.index("Newer") < text.index("Older") < text.index("Keynote")
    assert "Ada" in text


def test_post_topic_without_name_is_anonymous(client):
    response = client.post("/topics", data={"title": "No name"})
    assert "Anonymous" in response.text


def _post_invalid(client, db, title):
    before = len(db.list_topics())
    response = client.post("/topics", data={"title": title})
    assert response.status_code == 422
    assert response.headers["HX-Retarget"] == "#form-error"
    assert len(db.list_topics()) == before
    return response


def test_post_topic_rejects_empty_title(client, db):
    response = _post_invalid(client, db, "   ")
    assert "required" in response.text


def test_post_topic_rejects_missing_title(client, db):
    response = client.post("/topics", data={})
    assert response.status_code == 422


def test_post_topic_rejects_long_title(client, db):
    response = _post_invalid(client, db, "x" * 281)
    assert "280" in response.text


def test_post_topic_escapes_html(client):
    response = client.post("/topics", data={"title": "<script>alert(1)</script>"})
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_restart_does_not_duplicate_organizer_topics(client, db):
    with TestClient(app):
        pass
    with TestClient(app):
        pass
    organizer = [t for t in db.list_topics() if t["source"] == "organizer"]
    assert len(organizer) == 1
