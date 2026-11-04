import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

ORGANIZER_TITLES = ["Organizer topic A", "Organizer topic B"]


@pytest.fixture(autouse=True)
def temp_env(tmp_path, monkeypatch):
    """Point the app at a temporary DB and topics file for every test."""
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps([{"title": t} for t in ORGANIZER_TITLES]))
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))
    return topics_file


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
