from app import db
from tests.conftest import ORGANIZER_TITLES


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_shows_form_and_organizer_topics(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'hx-post="/topics"' in response.text
    assert 'hx-trigger="every 3s"' in response.text
    assert ORGANIZER_TITLES[0] in response.text
    assert "Organizer's pick" in response.text


def test_topics_partial(client):
    response = client.get("/topics")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert ORGANIZER_TITLES[0] in response.text


def test_create_topic(client):
    response = client.post("/topics", data={"title": "  My topic  ", "author": "Ana"})
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "My topic" in response.text
    assert "by Ana" in response.text
    created = [t for t in db.list_topics() if t["source"] == "attendee"]
    assert [(t["title"], t["author"]) for t in created] == [("My topic", "Ana")]


def test_create_topic_author_optional(client):
    response = client.post("/topics", data={"title": "Anonymous topic"})
    assert response.status_code == 200
    created = [t for t in db.list_topics() if t["source"] == "attendee"]
    assert created[0]["author"] is None


def test_create_topic_escapes_html(client):
    response = client.post("/topics", data={"title": "<script>x</script>"})
    assert "<script>x</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def attendee_count():
    return sum(1 for t in db.list_topics() if t["source"] == "attendee")


def test_create_topic_rejects_empty(client):
    for title in ["", "   "]:
        response = client.post("/topics", data={"title": title})
        assert response.status_code == 422
        assert response.headers["HX-Retarget"] == "#form-error"
    response = client.post("/topics", data={})
    assert response.status_code == 422
    assert attendee_count() == 0


def test_create_topic_rejects_too_long(client):
    response = client.post("/topics", data={"title": "x" * 281})
    assert response.status_code == 422
    assert "280" in response.text
    assert attendee_count() == 0


def test_create_topic_accepts_max_length(client):
    response = client.post("/topics", data={"title": "x" * 280})
    assert response.status_code == 200
    assert attendee_count() == 1


def test_list_is_newest_first(client):
    for title in ["older topic", "newer topic"]:
        client.post("/topics", data={"title": title})
    text = client.get("/topics").text
    assert text.index("newer topic") < text.index("older topic")
