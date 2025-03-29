from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models import User


# Shared properties
class RoleBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, nullable=False)
    description: str | None = Field(default=None, max_length=255, nullable=True)
    label: str = Field(nullable=False)


# Properties to receive on name creation
class RoleCreate(RoleBase):
    pass


# Properties to receive on name update
class RoleUpdate(RoleBase):
    pass


# Database model, database table inferred from class name
class Role(RoleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    is_active: bool = Field(default=True, nullable=False)
    users: list["User"] = Relationship(back_populates="role")


# Properties to return via API, id is always required
class RolePublic(RoleBase):
    id: int
    is_active: bool


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int
