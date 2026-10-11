import pytest
from helpers import board as _board
from helpers import client


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
    original_board = _board()
    incomplete_board = {
        "columns": original_board["columns"][:2],
        "cards": original_board["cards"],
    }

    response = client.put("/api/users/user/board", json=incomplete_board)

    assert response.status_code == 400
    assert "five fixed columns" in response.json()["detail"]
    assert _board() == original_board


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda b: b["columns"][0]["cardIds"].append("ghost"), "exactly one column"),
        (lambda b: b["columns"][1]["cardIds"].append("card-1"), "exactly one column"),
        (lambda b: b["columns"][0].update(title=""), "title"),
        (lambda b: b["columns"][0].update(cardIds="card-1"), "cardIds"),
        (lambda b: b["cards"]["card-1"].pop("title"), "title"),
        (lambda b: b["cards"]["card-1"].update(id="card-x"), "match"),
        (lambda b: b["cards"]["card-1"].update(details="x" * 6000), "details"),
    ],
)
def test_board_update_rejects_invalid_payloads_without_changing_data(mutate, expected):
    original = _board()
    payload = _board()
    mutate(payload)

    response = client.put("/api/users/user/board", json=payload)

    assert response.status_code == 400
    assert expected in response.json()["detail"]
    assert _board() == original


def test_card_order_within_a_column_is_persisted():
    payload = _board()
    payload["columns"][0]["cardIds"] = ["card-2", "card-1"]

    assert client.put("/api/users/user/board", json=payload).status_code == 200
    assert _board()["columns"][0]["cardIds"] == ["card-2", "card-1"]


def test_card_can_move_to_another_column_and_be_deleted():
    payload = _board()
    payload["columns"][0]["cardIds"].remove("card-1")
    payload["columns"][3]["cardIds"].append("card-1")
    del payload["cards"]["card-2"]
    payload["columns"][0]["cardIds"].remove("card-2")

    assert client.put("/api/users/user/board", json=payload).status_code == 200
    stored = _board()
    assert stored["columns"][3]["cardIds"] == ["card-6", "card-1"]
    assert "card-2" not in stored["cards"]


def test_unknown_user_is_not_found():
    assert client.get("/api/users/nobody/board").status_code == 404
    assert client.put("/api/users/nobody/board", json=_board()).status_code == 404
