import json

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app

ORGANIZER_TOPICS = [{"title": "Keynote: the future of Python"}]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    db_module.init_db()
    return db_module


@pytest.fixture
def topics_file(tmp_path, monkeypatch):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(ORGANIZER_TOPICS))
    monkeypatch.setenv("TOPICS_FILE", str(path))
    return path


@pytest.fixture
def client(db, topics_file):
    with TestClient(app) as c:
        yield c
