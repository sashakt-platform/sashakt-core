import enum

from sqlmodel import SQLModel
from typing_extensions import NotRequired, TypedDict


# Generic message
class Message(SQLModel):
    message: str


CorrectAnswerType = (
    list[int] | list[str] | float | int | str | dict[str, list[int]] | None
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


class LocaleEnum(str, enum.Enum):
    English = "en-US"
    Hindi = "hi-IN"


SUPPORTED_LOCALES = {loc.value: loc.name for loc in LocaleEnum}

DEFAULT_LOCALE = LocaleEnum.English
