from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


class BaseModel(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(nullable=True)


class Country(BaseModel, table=True):
    name: str = Field(nullable=False)
    states: list["State"] | None = Relationship(back_populates="country")


class State(BaseModel, table=True):
    name: str = Field(nullable=False)
    country_id: int = Field(foreign_key="country.id")
    country: Country | None = Relationship(back_populates="states")
    districts: list["District"] | None = Relationship(back_populates="state")


class District(BaseModel, table=True):
    name: str = Field(nullable=False)
    state_id: int = Field(foreign_key="state.id")
    state: State | None = Relationship(back_populates="districts")
    blocks: list["Block"] | None = Relationship(back_populates="district")


class Block(BaseModel, table=True):
    name: str = Field(nullable=False)
    district_id: int = Field(foreign_key="district.id")
    district: District | None = Relationship(back_populates="blocks")
