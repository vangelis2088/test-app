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


def _topic_id(title):
    return next(t["id"] for t in db.list_topics() if t["title"] == title)


def _votes(title):
    return next(t["votes"] for t in db.list_topics() if t["title"] == title)


def test_voter_cookie_is_set(client):
    resp = client.get("/")
    assert len(resp.cookies["voter_id"]) == 32


def test_first_vote(client):
    topic_id = _topic_id(ORGANIZER_TITLES[1])
    resp = client.post(f"/topics/{topic_id}/vote")
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert _votes(ORGANIZER_TITLES[1]) == 1
    # Voted topic is highlighted and sorted to the top.
    assert resp.text.index(ORGANIZER_TITLES[1]) < resp.text.index(ORGANIZER_TITLES[0])
    assert f'class="topic voted" id="topic-{topic_id}"' in resp.text


def test_moving_a_vote(client):
    first, second = (_topic_id(t) for t in ORGANIZER_TITLES)
    client.post(f"/topics/{first}/vote")
    resp = client.post(f"/topics/{second}/vote")
    assert resp.status_code == 200
    assert _votes(ORGANIZER_TITLES[0]) == 0
    assert _votes(ORGANIZER_TITLES[1]) == 1
    assert f'class="topic voted" id="topic-{second}"' in resp.text
    assert resp.text.count("topic voted") == 1


def test_repeat_vote_does_nothing(client):
    topic_id = _topic_id(ORGANIZER_TITLES[0])
    client.post(f"/topics/{topic_id}/vote")
    resp = client.post(f"/topics/{topic_id}/vote")
    assert resp.status_code == 200
    assert _votes(ORGANIZER_TITLES[0]) == 1


def test_votes_from_different_browsers_add_up(client):
    topic_id = _topic_id(ORGANIZER_TITLES[0])
    client.post(f"/topics/{topic_id}/vote")
    client.cookies.clear()  # a new browser gets a new voter id
    client.post(f"/topics/{topic_id}/vote")
    assert _votes(ORGANIZER_TITLES[0]) == 2


def test_malformed_voter_cookie_is_replaced(client):
    client.cookies.set("voter_id", "not-a-valid-id")
    resp = client.get("/topics")
    new_id = resp.cookies["voter_id"]
    assert new_id != "not-a-valid-id"
    assert len(new_id) == 32


def test_vote_unknown_topic(client):
    resp = client.post("/topics/999999/vote")
    assert resp.status_code == 404


def test_vote_invalid_topic_id(client):
    resp = client.post("/topics/abc/vote")
    assert resp.status_code == 422


def test_list_sorted_by_votes_then_newest(client):
    client.post("/topics", data={"title": "Old"})
    client.post("/topics", data={"title": "New"})
    client.post(f"/topics/{_topic_id('Old')}/vote")
    text = client.get("/topics").text
    assert text.index("Old") < text.index("New") < text.index(ORGANIZER_TITLES[0])


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    '<i hx-post="/topics/1/vote" hx-trigger="load" hx-target="#topics"></i>',
]


def test_topic_titles_are_html_escaped(client):
    for payload in XSS_PAYLOADS:
        post = client.post("/topics", data={"title": payload, "author": payload})
        assert post.status_code == 200
        for resp in (post, client.get("/topics"), client.get("/")):
            assert payload not in resp.text
            assert "&lt;" in resp.text
    text = client.get("/topics").text
    assert "<script>" not in text
    assert "<img" not in text
    assert "<i hx-post" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
