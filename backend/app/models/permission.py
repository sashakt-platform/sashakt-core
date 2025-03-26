from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models import Role


class RolePermsission(SQLModel, table=True):
    __tablename__ = "role_permission"
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("permission_id", "role_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    permission_id: int = Field(foreign_key="permission.id", ondelete="CASCADE")
    role_id: int = Field(foreign_key="role.id", ondelete="CASCADE")


class PermissionBase(SQLModel):
    name: str = Field(
        nullable=False,
        index=True,
        title="Title of Permission",
        description="Name of the Permission",
    )
    description: str = Field(
        nullable=True,
        title="Description of Permission",
        description="A brief explanation of the Permission",
    )


class PermissionCreate(PermissionBase):
    pass


class Permission(PermissionBase, table=True):
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
    roles: list["Role"] | None = Relationship(
        back_populates="permissions", link_model=RolePermsission
    )


class PermissionUpdate(PermissionBase):
    pass
