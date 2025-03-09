from sqlmodel import Field, SQLModel


# Shared properties
class RoleBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on name creation
class RoleCreate(RoleBase):
    pass


# Properties to receive on name update
class RoleUpdate(RoleBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Role(RoleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)


# Properties to return via API, id is always required
class RolePublic(RoleBase):
    id: int | None = Field(default=None, primary_key=True)


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int
