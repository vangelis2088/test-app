from app import db


def test_load_organizer_topics_is_idempotent(temp_env):
    db.init_db()
    assert db.load_organizer_topics(["A", "B"]) == 2
    assert db.load_organizer_topics(["A", "B"]) == 0
    assert [t["title"] for t in db.list_topics()].count("A") == 1
    assert len(db.list_topics()) == 2


def test_attendee_can_duplicate_organizer_title(temp_env):
    db.init_db()
    db.load_organizer_topics(["Same"])
    db.create_topic("Same", None)
    assert len(db.list_topics()) == 2


def test_list_topics_newest_first(temp_env):
    db.init_db()
    first = db.create_topic("first", None)
    second = db.create_topic("second", "Ann")
    ids = [t["id"] for t in db.list_topics()]
    assert ids == [second, first]
