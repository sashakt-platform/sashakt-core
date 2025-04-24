from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models import Question, Tag, TagType, User


class OrganizationBase(SQLModel):
    name: str = Field(
        index=True, title="Organization Name", description="Name of the organization"
    )
    description: str | None = Field(
        default=None, title="Description", description="Description of the organization"
    )


class Organization(OrganizationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None)
    is_deleted: bool = Field(default=False)

    # Relationships
    tag_types: list["TagType"] = Relationship(back_populates="organization")
    tags: list["Tag"] = Relationship(back_populates="organization")
    users: list["User"] = Relationship(back_populates="organization")
    question: list["Question"] = Relationship(back_populates="organization")


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationPublic(OrganizationBase):
    id: int | None
    created_date: datetime | None
    modified_date: datetime | None
    is_active: bool | None
    is_deleted: bool


class OrganizationUpdate(OrganizationBase):
    pass
