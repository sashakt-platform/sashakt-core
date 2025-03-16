from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class OrganizationBase(SQLModel):
    name: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)


class Organization(OrganizationBase, table=True):
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


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationPublic(OrganizationBase):
    id: int | None
    created_date: datetime | None
    modified_date: datetime | None
    is_deleted: bool | None


class OrganizationUpdate(OrganizationBase):
    pass
