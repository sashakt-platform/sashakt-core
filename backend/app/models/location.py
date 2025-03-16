from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from app.models.test import Test, TestStateLocationLink


# -----Models for Country-----
class CountryBase(SQLModel):
    name: str = Field(nullable=False)


class Country(CountryBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None, nullable=True)
    states: list["State"] | None = Relationship(back_populates="country")


class CountryPublic(CountryBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None


class CountryCreate(CountryBase):
    pass


class CountryUpdate(CountryBase):
    name: str | None


# -----Models for Country-----


# -----Models for State-----
class StateBase(SQLModel):
    name: str = Field(nullable=False)
    country_id: int = Field(
        foreign_key="country.id", nullable=False, ondelete="CASCADE"
    )


class State(StateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None, nullable=True)
    country: Country | None = Relationship(back_populates="states")
    districts: list["District"] | None = Relationship(back_populates="state")
    tests: list["Test"] | None = Relationship(
        back_populates="states", link_model=TestStateLocationLink
    )


class StatePublic(StateBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None


class StateCreate(StateBase):
    pass


class StateUpdate(StateBase):
    name: str | None
    country_id: int | None


# -----Models for State-----


# -----Models for District-----


class DistrictBase(SQLModel):
    name: str = Field(nullable=False)
    state_id: int = Field(foreign_key="state.id", nullable=False, ondelete="CASCADE")


class District(DistrictBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None, nullable=True)
    state: State | None = Relationship(back_populates="districts")
    blocks: list["Block"] | None = Relationship(back_populates="district")


class DistrictPublic(DistrictBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None


class DistrictCreate(DistrictBase):
    pass


class DistrictUpdate(DistrictBase):
    name: str | None
    state_id: int | None


# -----Models for District-----


# -----Models for Block-----


class BlockBase(SQLModel):
    name: str = Field(nullable=False)
    district_id: int = Field(
        foreign_key="district.id", nullable=False, ondelete="CASCADE"
    )


class Block(BlockBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None, nullable=True)
    district: District | None = Relationship(back_populates="blocks")


class BlockPublic(BlockBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None


class BlockCreate(BlockBase):
    pass


class BlockUpdate(BlockBase):
    name: str | None
    district_id: int | None


# -----Models for Block-----
