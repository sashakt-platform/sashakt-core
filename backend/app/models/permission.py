from sqlmodel import Field, SQLModel


# Shared properties
class PermissionBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = Field(default=True, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)


# Properties to receive on name creation
class PermissionCreate(PermissionBase):
    pass


# Properties to receive on name update
class PermissionUpdate(PermissionBase):
    pass


# Database model, database table inferred from class name
class Permission(PermissionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)


# Properties to return via API, id is always required
class PermissionPublic(PermissionBase):
    id: int | None = Field(default=None, primary_key=True)


class PermissionsPublic(SQLModel):
    data: list[PermissionPublic]
    count: int
