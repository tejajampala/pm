import pytest

from app import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    # TestClient does not run the app lifespan, so tests create the schema themselves.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "kanban.db")
    db.init_db()
