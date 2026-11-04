import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from app import db
from app.main import app
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


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    '<div hx-post="/topics/1/vote" hx-trigger="load">x</div>',
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_titles_and_authors_are_html_escaped_everywhere(client, payload):
    """User-supplied text must never reach the page as live HTML."""
    response = client.post("/topics", data={"title": payload, "author": payload})
    assert response.status_code == 200
    escaped = str(escape(payload))
    # Every view that renders the list: POST response, polling partial, full page.
    for page in (response.text, client.get("/topics").text, client.get("/").text):
        assert payload not in page
        assert f'<span class="title">{escaped}</span>' in page
        assert f'<div class="author">by {escaped}</div>' in page


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


def topic_id(title):
    return next(t["id"] for t in db.list_topics() if t["title"] == title)


def counts():
    return {t["title"]: t["vote_count"] for t in db.list_topics()}


def test_first_vote(client):
    a = topic_id(ORGANIZER_TITLES[0])
    response = client.post(f"/topics/{a}/vote")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "voter_id" in response.cookies
    assert counts()[ORGANIZER_TITLES[0]] == 1
    assert f'class="topic voted" id="topic-{a}"' in response.text
    assert "Your vote" in response.text


def test_moving_a_vote(client):
    a, b = (topic_id(t) for t in ORGANIZER_TITLES)
    client.post(f"/topics/{a}/vote")
    response = client.post(f"/topics/{b}/vote")
    assert response.status_code == 200
    assert counts() == {ORGANIZER_TITLES[0]: 0, ORGANIZER_TITLES[1]: 1}
    assert f'class="topic voted" id="topic-{b}"' in response.text
    assert f'class="topic voted" id="topic-{a}"' not in response.text


def test_repeat_vote_does_nothing(client):
    a = topic_id(ORGANIZER_TITLES[0])
    client.post(f"/topics/{a}/vote")
    response = client.post(f"/topics/{a}/vote")
    assert response.status_code == 200
    assert counts()[ORGANIZER_TITLES[0]] == 1


def test_vote_unknown_topic(client):
    response = client.post("/topics/99999/vote")
    assert response.status_code == 404
    assert sum(counts().values()) == 0


def test_vote_invalid_topic_id(client):
    response = client.post("/topics/abc/vote")
    assert response.status_code == 422
    assert sum(counts().values()) == 0


def test_votes_from_different_browsers_add_up(client):
    a = topic_id(ORGANIZER_TITLES[0])
    client.post(f"/topics/{a}/vote")
    other = TestClient(app)
    other.post(f"/topics/{a}/vote")
    assert counts()[ORGANIZER_TITLES[0]] == 2


def test_malformed_voter_cookie_is_replaced(client):
    a = topic_id(ORGANIZER_TITLES[0])
    client.cookies.set("voter_id", "not-a-uuid")
    response = client.post(f"/topics/{a}/vote")
    assert response.status_code == 200
    assert response.cookies["voter_id"] != "not-a-uuid"
    assert counts()[ORGANIZER_TITLES[0]] == 1


def test_index_sets_voter_cookie_once(client):
    first = client.get("/")
    assert "voter_id" in first.cookies
    second = client.get("/")
    assert "voter_id" not in second.cookies


def test_list_sorted_by_votes_then_newest(client):
    client.post("/topics", data={"title": "older topic"})
    client.post("/topics", data={"title": "newer topic"})
    client.post(f"/topics/{topic_id('older topic')}/vote")
    text = client.get("/topics").text
    assert text.index("older topic") < text.index("newer topic")
    # Among zero-vote topics, newest first still applies.
    assert text.index("newer topic") < text.index(ORGANIZER_TITLES[0])
