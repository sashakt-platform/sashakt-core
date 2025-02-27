from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone


class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_date: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: Optional[bool] = Field(nullable=True)
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)
