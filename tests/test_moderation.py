import base64
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.moderation import router

PASSWORD = "s3cret"


def auth(password=PASSWORD):
    token = base64.b64encode(f"mod:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "HX-Request": "true"}


def auth_no_htmx():
    return {"Authorization": auth()["Authorization"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    db.init_db()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_page_requires_auth(client):
    r = client.get("/moderate")
    assert r.status_code == 401
    assert "Basic" in r.headers["www-authenticate"]


def test_wrong_password(client):
    assert client.get("/moderate", headers=auth("nope")).status_code == 401


def test_denied_when_password_unset(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD")
    assert client.get("/moderate").status_code == 403
    assert client.get("/moderate", headers=auth("")).status_code == 403


def test_non_ascii_password_rejected(client):
    assert client.get("/moderate", headers=auth("pässword")).status_code == 401


def test_post_requires_auth(client):
    tid = db.add_topic("Q", None)
    assert client.post(f"/moderate/topics/{tid}/answer").status_code == 401
    assert client.post(f"/moderate/topics/{tid}/delete").status_code == 401
    assert len(db.list_topics()) == 1
    assert db.list_topics()[0]["answered"] == 0


@pytest.mark.parametrize("action", ["answer", "delete"])
def test_post_without_htmx_header_rejected(client, action):
    tid = db.add_topic("Q", None)
    r = client.post(f"/moderate/topics/{tid}/{action}", headers=auth_no_htmx())
    assert r.status_code == 403
    assert len(db.list_topics()) == 1
    assert db.list_topics()[0]["answered"] == 0


@pytest.mark.parametrize("action", ["answer", "delete"])
def test_post_denied_when_password_unset(client, monkeypatch, action):
    tid = db.add_topic("Q", None)
    monkeypatch.delenv("ADMIN_PASSWORD")
    r = client.post(f"/moderate/topics/{tid}/{action}", headers=auth(""))
    assert r.status_code == 403
    assert len(db.list_topics()) == 1


def test_no_store_on_all_responses(client):
    assert client.get("/moderate").headers["cache-control"] == "no-store"
    ok = client.get("/moderate", headers=auth())
    assert ok.headers["cache-control"] == "no-store"
    bad = client.post("/moderate/topics/1/answer", headers=auth_no_htmx())
    assert bad.headers["cache-control"] == "no-store"


def test_titles_are_escaped(client):
    db.add_topic("<script>x</script>", "<b>me</b>")
    r = client.get("/moderate", headers=auth())
    assert "<script>x</script>" not in r.text
    assert "&lt;script&gt;x&lt;/script&gt;" in r.text
    assert "<b>me</b>" not in r.text


def test_deleted_organizer_topic_stays_deleted(client, tmp_path, monkeypatch):
    topics_file = tmp_path / "topics.json"
    topics_file.write_text('[{"title": "Organizer A"}, {"title": "Organizer B"}]')
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))
    db.load_organizer_topics()
    target = next(t for t in db.list_topics() if t["title"] == "Organizer A")
    assert (
        client.post(
            f"/moderate/topics/{target['id']}/delete", headers=auth()
        ).status_code
        == 200
    )
    db.init_db()
    db.load_organizer_topics()
    assert [t["title"] for t in db.list_topics()] == ["Organizer B"]


def test_page_lists_topics(client):
    db.add_topic("Hello topic", "Ann")
    r = client.get("/moderate", headers=auth())
    assert r.status_code == 200
    assert "Hello topic" in r.text


def test_answer_moves_to_bottom(client):
    first = db.add_topic("First", None)
    second = db.add_topic("Second", None)
    db.cast_vote("a" * 32, first)
    r = client.post(f"/moderate/topics/{first}/answer", headers=auth())
    assert r.status_code == 200
    assert r.text.index("Second") < r.text.index("First")
    rows = db.list_topics()
    assert [row["id"] for row in rows] == [second, first]
    assert rows[1]["answered"] == 1


def test_delete_removes_topic_and_votes(client):
    tid = db.add_topic("Gone", None)
    db.cast_vote("b" * 32, tid)
    r = client.post(f"/moderate/topics/{tid}/delete", headers=auth())
    assert r.status_code == 200
    assert "Gone" not in r.text
    assert db.list_topics() == []
    conn = db.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize("action", ["answer", "delete"])
def test_not_found(client, action):
    r = client.post(f"/moderate/topics/999/{action}", headers=auth())
    assert r.status_code == 404


@pytest.mark.parametrize("action", ["answer", "delete"])
def test_invalid_id(client, action):
    r = client.post(f"/moderate/topics/abc/{action}", headers=auth())
    assert r.status_code == 422


def test_migrates_existing_db(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE topics (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " title TEXT NOT NULL, author TEXT, source TEXT NOT NULL,"
        " created_at TEXT NOT NULL DEFAULT 'x')"
    )
    conn.execute("INSERT INTO topics (title, source) VALUES ('old', 'attendee')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("QA_DB_PATH", str(path))
    db.init_db()
    db.init_db()
    assert db.list_topics()[0]["answered"] == 0
