from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models import RolePermsission

if TYPE_CHECKING:
    from app.models import Permission, User


# Shared properties
class RoleBase(SQLModel):
    name: str = Field(
        min_length=1,
        max_length=255,
        title="Name of Role",
        description="Name of  the Role",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="Description of Role",
        description="A brief Description of the Role",
    )


# Properties to receive on name creation
class RoleCreate(RoleBase):
    pass


# Properties to receive on name update
class RoleUpdate(RoleBase):
    pass


# Database model, database table inferred from class name
class Role(RoleBase, table=True):
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
    users: list["User"] = Relationship(back_populates="role")
    permissions: list["Permission"] = Relationship(
        back_populates="roles", link_model=RolePermsission
    )


# Properties to return via API, id is always required
class RolePublic(RoleBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int
