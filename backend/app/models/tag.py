from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.location import State
from app.models.question import QuestionRevision, QuestionTag
from app.models.test import TestPublic, TestTag

if TYPE_CHECKING:
    from app.models import Organization, Question, QuestionRevision, Test, User


class TagTypeBase(SQLModel):
    name: str = Field(nullable=False, index=True, description="Name of the Tag Type")
    description: str | None = Field(
        default=None, nullable=True, description="Description of the Tag Type"
    )
    is_active: bool = Field(default=True)
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        description="Organization ID to which the Tag Type belongs",
    )


class TagType(TagTypeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_deleted: bool = Field(default=False, nullable=False)
    tags: list["Tag"] = Relationship(back_populates="tag_type")
    created_by: "User" = Relationship(back_populates="tag_types")
    organization: "Organization" = Relationship(back_populates="tag_types")
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the Tag Type",
    )


class TagTypeCreate(TagTypeBase):
    pass


class TagTypePublic(TagTypeBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_deleted: bool
    created_by_id: int = Field(
        description="ID of the user who created the current revision"
    )


class TagTypeUpdate(TagTypeBase):
    pass


class TagBase(SQLModel):
    name: str = Field(nullable=False, index=True, description="Name of the Tag")
    description: str | None = Field(
        default=None, nullable=True, description="Description of the Tag"
    )
    is_active: bool = Field(default=True)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    tag_type_id: int = Field(
        default=None,
        foreign_key="tagtype.id",
        nullable=True,
        description="ID of the Tag Type to which the Tag should belong to",
    )

    is_deleted: bool = Field(default=False, nullable=False)
    tag_type: "TagType" = Relationship(back_populates="tags")
    tests: list["Test"] = Relationship(back_populates="tags", link_model=TestTag)
    questions: list["Question"] = Relationship(
        back_populates="tags", link_model=QuestionTag
    )
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        description="Organization ID to which the Tag belongs",
    )
    organization: "Organization" = Relationship(back_populates="tags")
    created_by: "User" = Relationship(back_populates="tags")
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the Tag",
    )


class TagCreate(TagBase):
    tag_type_id: int | None = None


class TagPublic(TagBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_deleted: bool
    tag_type: TagType | None = None
    organization_id: int
    created_by_id: int


class TagUpdate(TagBase):
    tag_type_id: int | None = None


# Rebuild the models to ensure the database schema is up to date
State.model_rebuild()
QuestionRevision.model_rebuild()
TestPublic.model_rebuild()
