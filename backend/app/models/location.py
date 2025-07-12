from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.test import Test, TestState
from app.models.utils import DatePublic

if TYPE_CHECKING:
    from app.models.question import QuestionLocation


# -----Models for Country-----
class CountryBase(SQLModel):
    name: str = Field(nullable=False, index=True)
    is_active: bool = Field(default=True)


class Country(CountryBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    states: list["State"] | None = Relationship(back_populates="country")


class CountryPublic(CountryBase, DatePublic):
    id: int
    created_date: datetime
    modified_date: datetime


class CountryCreate(CountryBase):
    pass


class CountryUpdate(CountryBase):
    pass


# -----Models for Country-----


# -----Models for State-----
class StateBase(SQLModel):
    name: str = Field(nullable=False, index=True)
    is_active: bool = Field(default=True)
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
    country: Country | None = Relationship(back_populates="states")
    districts: list["District"] | None = Relationship(back_populates="state")
    tests: list["Test"] | None = Relationship(
        back_populates="states", link_model=TestState
    )
    question_locations: list["QuestionLocation"] = Relationship(back_populates="state")


class StatePublic(StateBase, DatePublic):
    id: int
    created_date: datetime
    modified_date: datetime


class StateCreate(StateBase):
    pass


class StateUpdate(StateBase):
    pass


# -----Models for State-----


# -----Models for District-----


class DistrictBase(SQLModel):
    name: str = Field(nullable=False, index=True)
    state_id: int = Field(foreign_key="state.id", nullable=False, ondelete="CASCADE")
    is_active: bool = Field(default=True)


class District(DistrictBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    state: State | None = Relationship(back_populates="districts")
    blocks: list["Block"] | None = Relationship(back_populates="district")
    question_locations: list["QuestionLocation"] = Relationship(
        back_populates="district"
    )


class DistrictPublic(DistrictBase, DatePublic):
    id: int
    created_date: datetime
    modified_date: datetime


class DistrictCreate(DistrictBase):
    pass


class DistrictUpdate(DistrictBase):
    pass


# -----Models for District-----


# -----Models for Block-----


class BlockBase(SQLModel):
    name: str = Field(nullable=False, index=True)
    district_id: int = Field(
        foreign_key="district.id", nullable=False, ondelete="CASCADE"
    )
    is_active: bool = Field(default=True)


class Block(BlockBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    district: District | None = Relationship(back_populates="blocks")
    question_locations: list["QuestionLocation"] = Relationship(back_populates="block")


class BlockPublic(BlockBase, DatePublic):
    id: int
    created_date: datetime
    modified_date: datetime


class BlockCreate(BlockBase):
    pass


class BlockUpdate(BlockBase):
    pass


# -----Models for Block-----
