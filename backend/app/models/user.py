from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .candidate import Candidate
    from .test import Test


# Shared properties
class UserBase(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    # phone: str | None = Field(default=None, max_length=255)
    #


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


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
    hashed_password: str
    tests: list["Test"] = Relationship(back_populates="created_by")
    candidates: list["Candidate"] = Relationship(back_populates="user")
    # token: str
    # refresh_token: str
    # created_date: datetime | None = Field(
    #     default_factory=lambda: datetime.now(timezone.utc)
    # )
    # modified_date: datetime | None = Field(
    #     default_factory=lambda: datetime.now(timezone.utc),
    #     sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    # )
    # is_active: bool | None = Field(nullable=True)
    # is_deleted: bool | None = Field(nullable=True)
    # role_id: int | None = Field(nullable=True)
    # organization_id: int | None = Field(nullable=True)
    # created_by_id: int | None = Field(nullable=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: int | None = Field(default=None, primary_key=True)


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
