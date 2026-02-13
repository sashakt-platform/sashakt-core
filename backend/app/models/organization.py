from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.timezone import get_timezone_aware_now
from app.models.candidate import Candidate

if TYPE_CHECKING:
    from app.models import Certificate, EntityType, Question, Tag, TagType, Test, User
    from app.models.form import Form
    from app.models.provider import OrganizationProvider


class OrganizationBase(SQLModel):
    name: str = Field(
        index=True, title="Organization Name", description="Name of the organization"
    )
    description: str | None = Field(
        default=None, title="Description", description="Description of the organization"
    )
    is_active: bool = Field(default=True)
    shortcode: str | None = Field(
        default=None,
        index=True,
        unique=True,
        description="Unique short code used to identify the organization",
    )
    logo: str | None = Field(default=None)


class Organization(OrganizationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )

    is_deleted: bool = Field(default=False)

    # Relationships
    tag_types: list["TagType"] = Relationship(back_populates="organization")
    tags: list["Tag"] = Relationship(back_populates="organization")
    entity_types: list["EntityType"] = Relationship(back_populates="organization")
    certificates: list["Certificate"] = Relationship(back_populates="organization")
    users: list["User"] = Relationship(back_populates="organization")
    question: list["Question"] = Relationship(back_populates="organization")
    organization_providers: list["OrganizationProvider"] = Relationship(
        back_populates="organization"
    )
    tests: list["Test"] = Relationship(back_populates="organization")
    candidates: list["Candidate"] = Relationship(back_populates="organization")
    forms: list["Form"] = Relationship(back_populates="organization")


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationPublic(OrganizationBase):
    id: int | None
    created_date: datetime | None
    modified_date: datetime | None
    is_deleted: bool


class OrganizationUpdate(OrganizationBase):
    pass


class AggregatedData(SQLModel):
    total_questions: int
    total_users: int
    total_tests: int


class OrganizationPublicMinimal(SQLModel):
    name: str
    logo: str | None = None
    shortcode: str
