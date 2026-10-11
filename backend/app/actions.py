import copy
from uuid import uuid4

from app.models import (
    Action,
    Board,
    CreateCard,
    DeleteCard,
    MoveCard,
    RenameColumn,
    UpdateCard,
)


class ActionError(ValueError):
    """An AI action that cannot be applied to the board."""


def apply_actions(board: dict, actions: list[Action]) -> tuple[Board, list[str]]:
    """Apply actions in order to a copy of the board; any failure rejects all of them.

    Returns the new board and one plain-language line per change actually made.
    """
    work = copy.deepcopy(board)
    columns = {column["id"]: column for column in work["columns"]}
    cards = work["cards"]

    def column_for(column_id: str) -> dict:
        if column_id not in columns:
            raise ActionError(f"Unknown column '{column_id}'.")
        return columns[column_id]

    def find_card(card_id: str) -> tuple[dict, dict]:
        if card_id not in cards:
            raise ActionError(f"Unknown card '{card_id}'.")
        owner = next(column for column in work["columns"] if card_id in column["cardIds"])
        return cards[card_id], owner

    changes: list[str] = []

    for action in actions:
        if isinstance(action, CreateCard):
            column = column_for(action.columnId)
            card_id = f"card-{uuid4()}"
            cards[card_id] = {"id": card_id, "title": action.title.strip(), "details": (action.details or "").strip()}
            column["cardIds"].append(card_id)
            changes.append(f"Added '{cards[card_id]['title']}' to {column['title']}")
        elif isinstance(action, UpdateCard):
            card, _ = find_card(action.cardId)
            if action.title is not None:
                card["title"] = action.title.strip()
            if action.details is not None:
                card["details"] = action.details.strip()
            changes.append(f"Updated '{card['title']}'")
        elif isinstance(action, MoveCard):
            _, source = find_card(action.cardId)
            target = column_for(action.columnId)
            source["cardIds"].remove(action.cardId)
            position = len(target["cardIds"]) if action.position is None else max(0, action.position)
            target["cardIds"].insert(min(position, len(target["cardIds"])), action.cardId)
            changes.append(f"Moved '{cards[action.cardId]['title']}' to {target['title']}")
        elif isinstance(action, DeleteCard):
            card, owner = find_card(action.cardId)
            owner["cardIds"].remove(action.cardId)
            del cards[action.cardId]
            changes.append(f"Deleted '{card['title']}'")
        elif isinstance(action, RenameColumn):
            column = column_for(action.columnId)
            changes.append(f"Renamed column '{column['title']}' to '{action.title.strip()}'")
            column["title"] = action.title.strip()

    # Final structural and length checks use the same model as every other board write.
    return Board.model_validate(work), changes
