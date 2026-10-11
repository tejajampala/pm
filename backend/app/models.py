from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

FIXED_COLUMN_IDS = ["col-backlog", "col-discovery", "col-progress", "col-review", "col-done"]


class Card(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=5000)


class Column(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=100)
    cardIds: list[str]


class Board(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]

    @model_validator(mode="after")
    def check_structure(self) -> "Board":
        if [column.id for column in self.columns] != FIXED_COLUMN_IDS:
            raise ValueError("Board must include all five fixed columns in order.")

        placed = [card_id for column in self.columns for card_id in column.cardIds]
        if len(placed) != len(set(placed)) or set(placed) != set(self.cards):
            raise ValueError("Every card must be placed in exactly one column.")

        if any(key != card.id for key, card in self.cards.items()):
            raise ValueError("Card ids must match their keys in the cards map.")

        return self


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    username: str = "user"
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    board: Board | None = None
    history: list[ChatTurn] = Field(default_factory=list)


def format_errors(errors: Sequence[Any]) -> str:
    parts = []
    for error in errors:
        location = [str(part) for part in error["loc"] if part != "body"]
        message = error["msg"].removeprefix("Value error, ")
        parts.append(f"{'.'.join(location)}: {message}" if location else message)
    return "; ".join(parts)


class CreateCard(BaseModel):
    type: Literal["create_card"]
    columnId: str
    title: str
    details: str | None = None


class UpdateCard(BaseModel):
    type: Literal["update_card"]
    cardId: str
    title: str | None = None
    details: str | None = None


class MoveCard(BaseModel):
    type: Literal["move_card"]
    cardId: str
    columnId: str
    position: int | None = None


class DeleteCard(BaseModel):
    type: Literal["delete_card"]
    cardId: str


class RenameColumn(BaseModel):
    type: Literal["rename_column"]
    columnId: str
    title: str


Action = Annotated[
    CreateCard | UpdateCard | MoveCard | DeleteCard | RenameColumn,
    Field(discriminator="type"),
]


class AIResponse(BaseModel):
    """What the model must return: a reply for the user and the board changes to make."""

    reply: str
    actions: list[Action] = Field(default_factory=list)
