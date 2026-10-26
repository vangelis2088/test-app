import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from app import db
from app.main import app


def test_index_renders_form_and_organizer_badge(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'hx-post="/topics"' in response.text
    assert 'hx-trigger="every 3s"' in response.text
    assert "Organizer topic A" in response.text
    assert response.text.count("Organizer's pick") == 2


def test_create_topic_returns_partial(client):
    response = client.post("/topics", data={"title": "My idea", "author": "Bob"})
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "My idea" in response.text
    assert "by Bob" in response.text
    assert "Organizer topic A" in response.text


def test_blank_author_is_stored_as_null(client):
    client.post("/topics", data={"title": "No author", "author": "  "})
    row = next(r for r in db.list_topics() if r["title"] == "No author")
    assert row["author"] is None


def test_empty_title_rejected(client):
    for title in ("", "   "):
        response = client.post("/topics", data={"title": title})
        assert response.status_code == 422
        assert "Please enter a topic" in response.text
    assert len(db.list_topics()) == 2


def test_missing_title_rejected(client):
    assert client.post("/topics", data={}).status_code == 422


def test_title_length_limit(client):
    response = client.post("/topics", data={"title": "x" * 281})
    assert response.status_code == 422
    assert "280" in response.text
    assert client.post("/topics", data={"title": "x" * 280}).status_code == 200


def test_title_is_escaped(client):
    response = client.post("/topics", data={"title": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_new_topic_is_listed_first(client):
    client.post("/topics", data={"title": "Newest"})
    text = client.get("/topics").text
    assert text.index("Newest") < text.index("Organizer topic A")


def test_restart_does_not_duplicate_organizer_topics(env):
    for _ in range(2):
        with TestClient(app) as c:
            assert c.get("/").text.count("Organizer's pick") == 2


def _topic_id(title):
    return next(r["id"] for r in db.list_topics() if r["title"] == title)


def _votes(title):
    return next(r["votes"] for r in db.list_topics() if r["title"] == title)


def test_first_vote(client):
    topic_id = _topic_id("Organizer topic A")
    response = client.post(f"/topics/{topic_id}/vote")
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "1 vote<" in response.text
    assert 'class="voted"' in response.text
    assert "voter_id" in client.cookies
    assert _votes("Organizer topic A") == 1


def test_vote_moves_between_topics(client):
    a = _topic_id("Organizer topic A")
    b = _topic_id("Organizer topic B")
    client.post(f"/topics/{a}/vote")
    client.post(f"/topics/{b}/vote")
    assert _votes("Organizer topic A") == 0
    assert _votes("Organizer topic B") == 1
    voted = [
        r["title"] for r in db.list_topics(client.cookies["voter_id"]) if r["voted"]
    ]
    assert voted == ["Organizer topic B"]


def test_repeat_vote_does_nothing(client):
    a = _topic_id("Organizer topic A")
    client.post(f"/topics/{a}/vote")
    response = client.post(f"/topics/{a}/vote")
    assert response.status_code == 200
    assert _votes("Organizer topic A") == 1


def test_vote_unknown_topic(client):
    response = client.post("/topics/9999/vote")
    assert response.status_code == 404


def test_vote_invalid_id(client):
    assert client.post("/topics/abc/vote").status_code == 422


def test_separate_browsers_have_separate_votes(client):
    a = _topic_id("Organizer topic A")
    client.post(f"/topics/{a}/vote")
    with TestClient(app) as other:
        other.post(f"/topics/{a}/vote")
    assert _votes("Organizer topic A") == 2


def test_malformed_cookie_is_replaced_not_trusted(client):
    a = _topic_id("Organizer topic A")
    response = client.post(
        f"/topics/{a}/vote", headers={"Cookie": "voter_id=not-a-valid-id"}
    )
    assert response.status_code == 200
    issued = response.cookies["voter_id"]
    assert issued != "not-a-valid-id"
    assert [r["voted"] for r in db.list_topics("not-a-valid-id")] == [0, 0]
    assert sum(r["voted"] for r in db.list_topics(issued)) == 1


def test_list_sorted_by_votes(client):
    b = _topic_id("Organizer topic B")
    client.post(f"/topics/{b}/vote")
    text = client.get("/topics").text
    assert text.index("Organizer topic B") < text.index("Organizer topic A")


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>',
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_stored_html_is_escaped_everywhere(client, payload):
    client.post("/topics", data={"title": payload, "author": payload})
    for path in ("/", "/topics"):
        text = client.get(path).text
        assert payload not in text
        assert str(escape(payload)) in text
