import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

ORGANIZER_TOPICS = [{"title": "Organizer topic A"}, {"title": "Organizer topic B"}]


@pytest.fixture
def env(tmp_path, monkeypatch):
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps(ORGANIZER_TOPICS))
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))
    return tmp_path


@pytest.fixture
def client(env):
    with TestClient(app) as c:
        yield c
