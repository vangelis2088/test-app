import json

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

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


def _topic_id(db, title):
    return next(t["id"] for t in db.list_topics() if t["title"] == title)


def _count(db, title):
    return next(t["vote_count"] for t in db.list_topics() if t["title"] == title)


def test_first_visit_sets_voter_cookie(client):
    response = client.get("/")
    assert len(response.cookies["voter_id"]) == 32


def test_vote_first_vote(client, db):
    client.post("/topics", data={"title": "Pick me"})
    topic_id = _topic_id(db, "Pick me")
    response = client.post(f"/topics/{topic_id}/vote")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert _count(db, "Pick me") == 1
    assert 'class="topic voted"' in response.text
    assert "Your vote" in response.text


def test_vote_moves_vote(client, db):
    client.post("/topics", data={"title": "A"})
    client.post("/topics", data={"title": "B"})
    client.post(f"/topics/{_topic_id(db, 'A')}/vote")
    client.post(f"/topics/{_topic_id(db, 'B')}/vote")
    assert _count(db, "A") == 0
    assert _count(db, "B") == 1


def test_vote_repeat_does_nothing(client, db):
    client.post("/topics", data={"title": "A"})
    topic_id = _topic_id(db, "A")
    client.post(f"/topics/{topic_id}/vote")
    response = client.post(f"/topics/{topic_id}/vote")
    assert response.status_code == 200
    assert _count(db, "A") == 1


def test_vote_unknown_topic_returns_404(client, db):
    response = client.post("/topics/99999/vote")
    assert response.status_code == 404
    assert db.voted_topic_id(client.cookies["voter_id"]) is None


def test_vote_invalid_topic_id_returns_422(client):
    response = client.post("/topics/not-a-number/vote")
    assert response.status_code == 422


def test_votes_from_different_browsers_add_up(client, db):
    client.post("/topics", data={"title": "Popular"})
    topic_id = _topic_id(db, "Popular")
    client.post(f"/topics/{topic_id}/vote")
    other = TestClient(app)
    other.post(f"/topics/{topic_id}/vote")
    assert _count(db, "Popular") == 2


def test_list_sorted_by_votes(client, db):
    client.post("/topics", data={"title": "Older"})
    client.post("/topics", data={"title": "Newer"})
    response = client.post(f"/topics/{_topic_id(db, 'Older')}/vote")
    text = response.text
    assert text.index("Older") < text.index("Newer")


def test_malformed_voter_cookie_is_replaced(client):
    client.cookies.set("voter_id", "../../evil")
    response = client.get("/topics")
    assert response.cookies["voter_id"] != "../../evil"
    assert len(response.cookies["voter_id"]) == 32


XSS_TITLES = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '<div hx-post="/topics/1/vote" hx-trigger="load">x</div>',
    '"><b onmouseover="alert(1)">',
]


@pytest.mark.parametrize("title", XSS_TITLES)
@pytest.mark.parametrize("path", ["/", "/topics"])
def test_attendee_titles_are_html_escaped(client, path, title):
    client.post("/topics", data={"title": title})
    text = client.get(path).text
    assert title not in text
    assert str(escape(title)) in text


def test_organizer_titles_are_html_escaped(db, tmp_path, monkeypatch):
    title = "<img src=x onerror=alert(1)>"
    path = tmp_path / "evil.json"
    path.write_text(json.dumps([{"title": title}]))
    monkeypatch.setenv("TOPICS_FILE", str(path))
    with TestClient(app) as c:
        text = c.get("/topics").text
    assert title not in text
    assert str(escape(title)) in text


def test_title_line_breaks_are_preserved(client):
    client.post("/topics", data={"title": "Line one\r\nLine two"})
    page = client.get("/").text
    assert ".title { white-space: pre-wrap; }" in page
    assert '<div class="title">Line one\r\nLine two</div>' in page
