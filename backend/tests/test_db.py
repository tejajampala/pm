from helpers import client

from app import db
from app.models import FIXED_COLUMN_IDS


def test_database_is_created_and_board_exists_for_demo_user():
    response = client.get("/api/users/user/board")

    assert response.status_code == 200
    payload = response.json()
    assert payload["columns"][0]["title"] == "Backlog"
    assert len(payload["cards"]) >= 1


def test_legacy_board_is_restored_to_five_columns_without_losing_existing_data():
    with db.get_connection() as connection:
        connection.execute("UPDATE columns SET title = 'Ready' WHERE id = 'col-backlog'")
        connection.execute("UPDATE columns SET title = 'Doing' WHERE id = 'col-progress'")
        for column_id in ("col-discovery", "col-review", "col-done"):
            connection.execute("DELETE FROM cards WHERE column_id = ?", (column_id,))
            connection.execute("DELETE FROM columns WHERE id = ?", (column_id,))

    db.init_db()
    response = client.get("/api/users/user/board")

    assert response.status_code == 200
    payload = response.json()
    assert [column["id"] for column in payload["columns"]] == FIXED_COLUMN_IDS
    assert payload["columns"][0]["title"] == "Ready"
    assert payload["columns"][2]["title"] == "Doing"
    assert payload["cards"]["card-1"]["title"] == "Align roadmap themes"
    assert "card-3" in payload["cards"]
