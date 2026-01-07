from sqlmodel import SQLModel
from typing_extensions import NotRequired, TypedDict


# Generic message
class Message(SQLModel):
    message: str


class TimeLeft(TypedDict):
    time_left: int | None


class PartialMarkCondition(TypedDict):
    num_correct_selected: int
    marks: int


class PartialMarkRule(TypedDict):
    correct_answers: list[PartialMarkCondition]


class MarkingScheme(TypedDict):
    correct: float
    wrong: float
    skipped: float

    partial: NotRequired[PartialMarkRule]
