from datetime import datetime, timezone

from pydantic import field_serializer
from sqlmodel import SQLModel
from typing_extensions import TypedDict

from app.core.config import CURRENT_ZONE, UTC_ZONE


# Generic message
class Message(SQLModel):
    message: str


class TimeLeft(TypedDict):
    time_left: int | None


class DatePublic(SQLModel):
    @field_serializer("created_date", "modified_date", check_fields=False)
    def serialize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # Assume UTC if no timezone info
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(CURRENT_ZONE).replace(tzinfo=None)


class StoreStartDate(SQLModel):
    # start_time: datetime | None = None

    @field_serializer("start_time", check_fields=False)
    def serialize_datetime_insert_start(
        self, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=CURRENT_ZONE)
        return value.astimezone(UTC_ZONE).replace(tzinfo=None)


class StoreEndDate(SQLModel):
    # end_time: datetime | None = None

    @field_serializer("end_time", check_fields=False)
    def serialize_datetime_insert_end(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=CURRENT_ZONE)
        return value.astimezone(UTC_ZONE).replace(tzinfo=None)


class StoreStartEndDate(StoreStartDate, StoreEndDate):
    pass


class PublicStartEndDate(SQLModel):
    @field_serializer("start_time", "end_time", check_fields=False)
    def serialize_datetime_public(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(CURRENT_ZONE).replace(tzinfo=None)
