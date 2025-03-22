from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.test import TestTag

if TYPE_CHECKING:
    from app.models import Organization, Test, User


class TagTypeBase(SQLModel):
    name: str = Field(nullable=False, index=True, description="Name of the Tag Type")
    description: str | None = Field(
        nullable=True, description="Description of the Tag Type"
    )
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the Tag Type",
    )
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
    is_active: bool | None = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)
    tags: list["Tag"] = Relationship(back_populates="tag_type")
    created_by: "User" = Relationship(back_populates="tag_types")
    organization: "Organization" = Relationship(back_populates="tag_types")


class TagTypeCreate(TagTypeBase):
    pass


class TagTypePublic(TagTypeBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool


class TagTypeUpdate(TagTypeBase):
    pass


class TagBase(SQLModel):
    tag_type_id: int = Field(
        foreign_key="tagtype.id",
        nullable=False,
        description="ID of the Tag Type to which the Tag should belong to",
    )
    name: str = Field(nullable=False, index=True, description="Name of the Tag")
    description: str | None = Field(nullable=True, description="Description of the Tag")
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the Tag",
    )


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)
    tag_type: "TagType" = Relationship(back_populates="tags")
    tests: list["Test"] = Relationship(back_populates="tags", link_model=TestTag)
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        description="Organization ID to which the Tag belongs",
    )
    organization: "Organization" = Relationship(back_populates="tags")
    created_by: "User" = Relationship(back_populates="tags")


class TagCreate(TagBase):
    pass


class TagPublic(TagBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool
    tag_type_id: int
    organization_id: int
    created_by_id: int


class TagUpdate(TagBase):
    pass
