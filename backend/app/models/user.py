from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.core.timezone import get_timezone_aware_now

if TYPE_CHECKING:
    from app.models import (
        Candidate,
        Entity,
        EntityType,
        Organization,
        QuestionRevision,
        Role,
        State,
        Tag,
        TagType,
        Test,
    )


class UserState(SQLModel, table=True):
    __tablename__ = "userstate"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    state_id: int = Field(foreign_key="state.id", ondelete="CASCADE")
    __table_args__ = (UniqueConstraint("user_id", "state_id"),)


# Shared properties
class UserBase(SQLModel):
    full_name: str = Field(
        max_length=255,
        title="Full Name of the User",
        description="Enter Full Name of the User",
    )
    email: EmailStr = Field(
        unique=True,
        index=True,
        max_length=255,
        title="Email of the User",
        description="Enter Email Address",
    )
    phone: str = Field(max_length=255)
    role_id: int = Field(foreign_key="role.id")
    organization_id: int = Field(foreign_key="organization.id")
    created_by_id: int | None = Field(default=None, foreign_key="user.id")
    is_active: bool = Field(default=True)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(
        min_length=8,
        max_length=40,
        nullable=False,
        title="Enter Password",
        description="Create password of minumum 8 charaters and maximum 40 characters",
    )
    state_ids: list[int] | None = Field(
        default=None, description="IDs of states to associate with the user"
    )


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)
    state_ids: list[int] | None = None


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    is_deleted: bool = Field(default=False, nullable=False)
    hashed_password: str
    question_revisions: list["QuestionRevision"] = Relationship(
        back_populates="created_by"
    )
    token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    created_by_id: int | None = Field(default=None, foreign_key="user.id")
    tests: list["Test"] | None = Relationship(back_populates="created_by")
    candidates: list["Candidate"] = Relationship(back_populates="user")
    tag_types: list["TagType"] = Relationship(back_populates="created_by")
    tags: list["Tag"] = Relationship(back_populates="created_by")
    entity_types: list["EntityType"] = Relationship(back_populates="created_by")
    entities: list["Entity"] = Relationship(back_populates="created_by")
    organization: "Organization" = Relationship(back_populates="users")
    role: "Role" = Relationship(back_populates="users")
    created_by: "User" = Relationship(
        back_populates="created_users",
        sa_relationship_kwargs={"remote_side": "User.id"},
    )
    created_users: list["User"] = Relationship(back_populates="created_by")
    states: list["State"] | None = Relationship(
        back_populates="users", link_model=UserState
    )

    # TODO : We need to save tokens post user creation
    # token: str
    # refresh_token: str


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_deleted: bool
    created_by_id: int | None
    states: list["State"] | None = Field(
        default=None, description="states associated with this user"
    )


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
