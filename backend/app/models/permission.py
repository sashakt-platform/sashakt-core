from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.role import RolePermission

if TYPE_CHECKING:
    from app.models import Role


# Shared properties
class PermissionBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)


# Properties to receive on name creation
class PermissionCreate(PermissionBase):
    pass


# Properties to receive on name update
class PermissionUpdate(PermissionBase):
    pass


# Database model, database table inferred from class name
class Permission(PermissionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    roles: list["Role"] | None = Relationship(
        back_populates="permissions", link_model=RolePermission
    )


# Properties to return via API, id is always required
class PermissionPublic(PermissionBase):
    id: int


class PermissionsPublic(SQLModel):
    data: list[PermissionPublic]
    count: int
