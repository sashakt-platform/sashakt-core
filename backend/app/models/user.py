from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models import Candidate, Organization, Role, Tag, TagType, Test


# Shared properties
class UserBase(SQLModel):
    full_name: str = Field(
        max_length=255,
        nullable=False,
        title="Full Name of the User",
        description="Enter Full Name of the User",
    )
    email: EmailStr = Field(
        unique=True,
        index=True,
        max_length=255,
        nullable=False,
        title="Email of the User",
        description="Enter Email Address",
    )
    phone: str = Field(max_length=255, nullable=False)
    role_id: int = Field(foreign_key="role.id", nullable=False)
    organization_id: int | None = Field(
        default=None, foreign_key="organization.id", nullable=True
    )
    created_by_id: int | None = Field(default=None, foreign_key="user.id")


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(
        min_length=8,
        max_length=40,
        nullable=False,
        title="Enter Password",
        description="Create password of minumum 8 charaters and maximum 40 characters",
    )


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool = Field(default=True, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)
    hashed_password: str
    token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    tests: list["Test"] | None = Relationship(back_populates="created_by")
    candidates: list["Candidate"] = Relationship(back_populates="user")
    tag_types: list["TagType"] = Relationship(back_populates="created_by")
    tags: list["Tag"] = Relationship(back_populates="created_by")
    organization: "Organization" = Relationship(back_populates="users")
    role: "Role" = Relationship(back_populates="users")
    created_by: "User" = Relationship(
        back_populates="created_users",
        sa_relationship_kwargs={"remote_side": "User.id"},
    )
    created_users: list["User"] = Relationship(back_populates="created_by")

    # TODO : We need to save tokens post user creation
    # token: str
    # refresh_token: str


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
