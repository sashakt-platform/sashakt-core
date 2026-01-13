import enum

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


class LocaleEnum(str, enum.Enum):
    English = "en-US"
    Hindi = "hi-IN"


SUPPORTED_LOCALES = {loc.value: loc.name for loc in LocaleEnum}

DEFAULT_LOCALE = LocaleEnum.English
