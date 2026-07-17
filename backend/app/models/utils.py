import enum
from typing import NotRequired

from sqlmodel import SQLModel
from typing_extensions import TypedDict


# Generic message
class Message(SQLModel):
    message: str


CorrectAnswerType = (
    list[int]
    | list[str]
    | float
    | int
    | str
    | dict[str, list[int]]
    | dict[str, int | float]
    | dict[str, str]
    | None
)


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


class LocaleEnum(enum.StrEnum):
    English = "en-US"
    Hindi = "hi-IN"


SUPPORTED_LOCALES = {loc.value: loc.name for loc in LocaleEnum}

DEFAULT_LOCALE = LocaleEnum.English
