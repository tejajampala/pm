import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "kanban.db")
    main.init_db()
    yield


client = TestClient(main.app)


def test_database_is_created_and_board_exists_for_demo_user():
    response = client.get("/api/users/user/board")

    assert response.status_code == 200
    payload = response.json()
    assert payload["columns"][0]["title"] == "Backlog"
    assert len(payload["cards"]) >= 1


def test_legacy_board_is_restored_to_five_columns_without_losing_existing_data():
    with main.get_connection() as connection:
        connection.execute("UPDATE columns SET title = 'Ready' WHERE id = 'col-backlog'")
        connection.execute("UPDATE columns SET title = 'Doing' WHERE id = 'col-progress'")
        for column_id in ("col-discovery", "col-review", "col-done"):
            connection.execute("DELETE FROM cards WHERE column_id = ?", (column_id,))
            connection.execute("DELETE FROM columns WHERE id = ?", (column_id,))

    response = client.get("/api/users/user/board")

    assert response.status_code == 200
    payload = response.json()
    assert [column["id"] for column in payload["columns"]] == [
        "col-backlog",
        "col-discovery",
        "col-progress",
        "col-review",
        "col-done",
    ]
    assert payload["columns"][0]["title"] == "Ready"
    assert payload["columns"][2]["title"] == "Doing"
    assert payload["cards"]["card-1"]["title"] == "Align roadmap themes"
    assert "card-3" in payload["cards"]


def test_board_update_persists_and_updates_existing_data():
    payload = {
        "columns": [
            {"id": "col-backlog", "title": "Ready", "cardIds": ["card-1"]},
            {"id": "col-discovery", "title": "Discovery", "cardIds": []},
            {"id": "col-progress", "title": "Doing", "cardIds": []},
            {"id": "col-review", "title": "Review", "cardIds": []},
            {"id": "col-done", "title": "Done", "cardIds": []},
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "Ship plan", "details": "Final review"}
        },
    }

    response = client.put("/api/users/user/board", json=payload)

    assert response.status_code == 200
    assert response.json()["columns"][0]["title"] == "Ready"

    follow_up = client.get("/api/users/user/board")
    assert follow_up.status_code == 200
    assert follow_up.json()["columns"][0]["title"] == "Ready"
    assert follow_up.json()["cards"]["card-1"]["title"] == "Ship plan"


def test_board_update_rejects_missing_fixed_columns():
    original_board = client.get("/api/users/user/board").json()
    incomplete_board = {
        "columns": original_board["columns"][:2],
        "cards": original_board["cards"],
    }

    response = client.put("/api/users/user/board", json=incomplete_board)

    assert response.status_code == 400
    assert "five fixed columns" in response.json()["detail"]
    assert client.get("/api/users/user/board").json() == original_board


def test_ai_chat_accepts_valid_structured_response(monkeypatch):
    monkeypatch.setattr(
        main,
        "query_openrouter",
        lambda *args, **kwargs: {
            "reply": "I added the release card.",
            "boardUpdate": {
                "columns": [
                    {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-99"]},
                    {"id": "col-discovery", "title": "Discovery", "cardIds": []},
                    {"id": "col-progress", "title": "In Progress", "cardIds": ["card-1"]},
                    {"id": "col-review", "title": "Review", "cardIds": []},
                    {"id": "col-done", "title": "Done", "cardIds": []},
                ],
                "cards": {
                    "card-1": {"id": "card-1", "title": "Ship plan revised", "details": "QA before release"},
                    "card-99": {"id": "card-99", "title": "Launch checklist", "details": "QA, approvals, ship"},
                },
            },
        },
    )

    response = client.post(
        "/api/ai/chat",
        json={
            "username": "user",
            "message": "Add a launch checklist card.",
            "board": {
                "columns": [
                    {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1"]},
                    {"id": "col-discovery", "title": "Discovery", "cardIds": []},
                    {"id": "col-progress", "title": "In Progress", "cardIds": []},
                    {"id": "col-review", "title": "Review", "cardIds": []},
                    {"id": "col-done", "title": "Done", "cardIds": []},
                ],
                "cards": {
                    "card-1": {"id": "card-1", "title": "Ship plan", "details": "Final review"}
                },
            },
            "history": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"] == "I added the release card."
    assert payload["boardUpdate"]["cards"]["card-99"]["title"] == "Launch checklist"
    persisted = client.get("/api/users/user/board").json()
    assert persisted["cards"]["card-99"]["title"] == "Launch checklist"
    assert persisted["cards"]["card-1"]["title"] == "Ship plan revised"
    assert persisted["columns"][2]["cardIds"] == ["card-1"]


def test_ai_chat_returns_answer_without_board_update(monkeypatch):
    monkeypatch.setattr(
        main,
        "query_openrouter",
        lambda *args, **kwargs: {"reply": "4", "boardUpdate": None},
    )

    response = client.post(
        "/api/ai/chat",
        json={
            "username": "user",
            "message": "What is 2 + 2?",
            "board": {"columns": [], "cards": {}},
            "history": [],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "4", "boardUpdate": None}


def test_ai_chat_surfaces_openrouter_errors(monkeypatch):
    class FailedResponse:
        status_code = 429
        text = "rate limited"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main.httpx, "post", lambda *args, **kwargs: FailedResponse())

    response = client.post(
        "/api/ai/chat",
        json={
            "username": "user",
            "message": "What is 2 + 2?",
            "board": {"columns": [], "cards": {}},
            "history": [],
        },
    )

    assert response.status_code == 502
    assert "rate limited" in response.json()["detail"]


def test_ai_chat_rejects_malformed_response(monkeypatch):
    monkeypatch.setattr(
        main,
        "query_openrouter",
        lambda *args, **kwargs: {"reply": "oops", "boardUpdate": {"cards": {}}},
    )

    original_board = client.get("/api/users/user/board").json()
    response = client.post(
        "/api/ai/chat",
        json={
            "username": "user",
            "message": "Please fix the board.",
            "board": {"columns": [], "cards": {}},
            "history": [],
        },
    )

    assert response.status_code == 400
    assert "columns and cards" in response.json()["detail"]
    assert client.get("/api/users/user/board").json() == original_board
