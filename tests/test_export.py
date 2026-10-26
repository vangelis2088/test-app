import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.export import router


@pytest.fixture
def client(env):
    app = FastAPI()
    app.include_router(router)
    db.init_db()
    with TestClient(app) as c:
        yield c


def test_export_happy_path(client):
    db.add_topic("Hello world", "Ann")
    r = client.get("/export.md")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    assert "**Hello world** — by Ann — 0 votes" in r.text


def test_export_sorted_by_votes_and_anonymous(client):
    a = db.add_topic("Low", None)
    b = db.add_topic("High", "Bob")
    db.cast_vote("v1", b)
    db.cast_vote("v2", b)
    db.cast_vote("v3", a)
    text = client.get("/export.md").text
    assert text.index("High") < text.index("Low")
    assert "by Bob — 2 votes" in text
    assert "by _anonymous_ — 1 vote" in text


def test_export_answered_status(client):
    a = db.add_topic("Done one", "Ann")
    db.add_topic("Open one", "Bob")
    db.mark_answered(a)
    text = client.get("/export.md").text
    assert "Done one** — by Ann — 0 votes — answered" in text
    assert "Open one** — by Bob — 0 votes — unanswered" in text


def test_export_empty(client):
    r = client.get("/export.md")
    assert r.status_code == 200
    assert "No questions yet" in r.text


def test_export_escapes_injection(client):
    db.add_topic("# Heading\n## two [x](http://evil) <script>*b*", "a\n# h")
    text = client.get("/export.md").text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "[x](" not in text
    assert [ln for ln in text.splitlines() if ln.startswith("#")] == ["# Questions"]
    assert "\\[x\\]\\(http\\:\\/\\/evil\\)" in text
    assert r"by a \# h" in text


def test_export_escapes_entities_pipes_backticks(client):
    db.add_topic("&amp; a|b `code`", "x")
    text = client.get("/export.md").text
    assert "&amp;amp; a\\|b \\`code\\`" in text


def test_export_blank_title_and_nosniff(client):
    db.add_topic("   ", "x")
    db.add_topic("***", "y")
    r = client.get("/export.md")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "**_untitled_**" in r.text
    assert "**\\*\\*\\***" in r.text
    assert not any(ln.startswith("#") for ln in r.text.splitlines()[1:])


def test_anonymous_marker_differs_from_typed_anonymous(client):
    db.add_topic("t1", "anonymous")
    db.add_topic("t2", None)
    text = client.get("/export.md").text
    assert "by anonymous —" in text
    assert "by _anonymous_ —" in text
