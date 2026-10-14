import pytest
from pydantic import ValidationError

from app import db
from app.actions import ActionError, apply_actions
from app.models import AIResponse


def _parse(*actions):
    return AIResponse.model_validate({"reply": "", "actions": list(actions)}).actions


def _apply(*actions):
    board = db.get_default_board()
    result, _ = apply_actions(board, _parse(*actions))
    return board, result.model_dump()


def _ids(board, column_id):
    return next(column["cardIds"] for column in board["columns"] if column["id"] == column_id)


def test_create_card_appends_to_the_column_with_a_generated_id():
    _, result = _apply({"type": "create_card", "columnId": "col-review", "title": " New ", "details": " d "})

    new_id = _ids(result, "col-review")[-1]
    assert new_id.startswith("card-") and new_id not in db.get_default_board()["cards"]
    assert result["cards"][new_id] == {"id": new_id, "title": "New", "details": "d"}


def test_update_card_changes_only_the_given_fields():
    _, result = _apply({"type": "update_card", "cardId": "card-1", "details": "New details"})

    assert result["cards"]["card-1"]["title"] == "Align roadmap themes"
    assert result["cards"]["card-1"]["details"] == "New details"


@pytest.mark.parametrize(
    "position, expected",
    [(None, ["card-3", "card-1"]), (0, ["card-1", "card-3"]), (1, ["card-3", "card-1"]), (99, ["card-3", "card-1"]), (-5, ["card-1", "card-3"])],
)
def test_move_card_to_another_column_respects_position(position, expected):
    action = {"type": "move_card", "cardId": "card-1", "columnId": "col-discovery"}
    if position is not None:
        action["position"] = position

    _, result = _apply(action)

    assert _ids(result, "col-discovery") == expected
    assert "card-1" not in _ids(result, "col-backlog")


def test_move_card_within_the_same_column_reorders_it():
    _, result = _apply({"type": "move_card", "cardId": "card-1", "columnId": "col-backlog", "position": 1})

    assert _ids(result, "col-backlog") == ["card-2", "card-1"]


def test_delete_card_removes_it_everywhere():
    _, result = _apply({"type": "delete_card", "cardId": "card-3"})

    assert "card-3" not in result["cards"]
    assert _ids(result, "col-discovery") == []


def test_rename_column_changes_only_the_title():
    _, result = _apply({"type": "rename_column", "columnId": "col-done", "title": "Shipped"})

    assert result["columns"][4]["title"] == "Shipped"
    assert [column["id"] for column in result["columns"]] == [c["id"] for c in db.get_default_board()["columns"]]


def test_actions_apply_in_order_and_do_not_modify_the_input_board():
    board, result = _apply(
        {"type": "create_card", "columnId": "col-backlog", "title": "Temp"},
        {"type": "move_card", "cardId": "card-1", "columnId": "col-done"},
        {"type": "delete_card", "cardId": "card-2"},
    )

    assert board == db.get_default_board()
    assert "card-2" not in result["cards"] and "card-1" in _ids(result, "col-done")


@pytest.mark.parametrize(
    "action",
    [
        {"type": "update_card", "cardId": "nope", "title": "x"},
        {"type": "move_card", "cardId": "card-1", "columnId": "nope"},
        {"type": "create_card", "columnId": "nope", "title": "x"},
        {"type": "delete_card", "cardId": "nope"},
        {"type": "rename_column", "columnId": "nope", "title": "x"},
    ],
)
def test_unknown_ids_raise_action_error(action):
    with pytest.raises(ActionError):
        _apply(action)


def test_a_deleted_card_cannot_be_used_by_a_later_action():
    with pytest.raises(ActionError):
        _apply({"type": "delete_card", "cardId": "card-1"}, {"type": "update_card", "cardId": "card-1", "title": "x"})


def test_results_that_break_board_rules_raise_validation_error():
    with pytest.raises(ValidationError):
        _apply({"type": "rename_column", "columnId": "col-done", "title": "  "})


def test_apply_actions_describes_each_change_actually_made():
    actions = _parse(
        {"type": "create_card", "columnId": "col-review", "title": "Docs"},
        {"type": "update_card", "cardId": "card-1", "title": "Roadmap v2"},
        {"type": "move_card", "cardId": "card-2", "columnId": "col-done"},
        {"type": "delete_card", "cardId": "card-3"},
        {"type": "rename_column", "columnId": "col-progress", "title": "Doing"},
    )

    _, changes = apply_actions(db.get_default_board(), actions)

    assert changes == [
        "Added 'Docs' to Review",
        "Updated 'Roadmap v2'",
        "Moved 'Gather customer signals' to Done",
        "Deleted 'Prototype analytics view'",
        "Renamed column 'In Progress' to 'Doing'",
    ]
