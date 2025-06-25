from datetime import datetime

from sqlmodel import SQLModel
from typing_extensions import TypedDict


# Generic message
class Message(SQLModel):
    message: str


class TimeLeft(TypedDict):
    time_left_seconds: int | None


def get_current_time() -> datetime:
    """Returns the current datetime."""
    return datetime.now()
