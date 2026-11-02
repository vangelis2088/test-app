import json

import pytest

ORGANIZER_TOPICS = [{"title": "Organizer topic one"}, {"title": "Organizer topic two"}]


@pytest.fixture
def topics_file(tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(ORGANIZER_TOPICS), encoding="utf-8")
    return path


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def app_env(monkeypatch, db_path, topics_file):
    monkeypatch.setenv("QA_DB_PATH", str(db_path))
    monkeypatch.setenv("TOPICS_FILE", str(topics_file))
