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
    ENGLISH = "en-US"
    HINDI = "hi-IN"


LOCALE_NAMES = {
    LocaleEnum.ENGLISH.value: "English",
    LocaleEnum.HINDI.value: "Hindi",
}

DEFAULTLOCALE = LOCALE_NAMES[LocaleEnum.ENGLISH.value]
