import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

ORGANIZER_TITLES = ["Organizer topic one", "Organizer topic two"]


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    """Point the app at a temporary DB and topics file (never qa.db)."""
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps([{"title": t} for t in ORGANIZER_TITLES]))
    monkeypatch.setenv("QA_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))
    return tmp_path


@pytest.fixture
def client(temp_env):
    with TestClient(app) as c:
        yield c
