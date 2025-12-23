from sqlmodel import SQLModel
from typing_extensions import TypedDict


# Generic message
class Message(SQLModel):
    message: str


class TimeLeft(TypedDict):
    time_left: int | None


class MarkingScheme(TypedDict):
    """Defines scoring rules for a question"""

    correct: float
    wrong: float
    skipped: float


CorrectAnswerType = list[int] | list[str] | float | int | None
