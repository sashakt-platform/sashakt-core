from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models import Permission, User


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permission"
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("permission_id", "role_id"),)
    permission_id: int = Field(foreign_key="permission.id", ondelete="CASCADE")
    role_id: int = Field(foreign_key="role.id", ondelete="CASCADE")


# Shared properties
class RoleBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, nullable=False)
    description: str | None = Field(default=None, max_length=255, nullable=True)
    label: str = Field(nullable=False)


# Properties to receive on name creation
class RoleCreate(RoleBase):
    permissions: list[int] = []


# Properties to receive on name update
class RoleUpdate(RoleBase):
    permissions: list[int] = []


# Database model, database table inferred from class name
class Role(RoleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    is_active: bool = Field(default=True, nullable=False)
    users: list["User"] = Relationship(back_populates="role")
    permissions: list["Permission"] | None = Relationship(
        back_populates="roles", link_model=RolePermission
    )


# Properties to return via API, id is always required
class RolePublic(RoleBase):
    id: int
    is_active: bool
    permissions: list[int]


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int
