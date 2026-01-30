from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.timezone import get_timezone_aware_now
from app.models.test import Test, TestDistrict, TestState
from app.models.user import User, UserState

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.question import QuestionLocation


# -----Models for Country-----
class CountryBase(SQLModel):
    name: str = Field(nullable=False, index=True)
    is_active: bool = Field(default=True)


class Country(CountryBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    states: list["State"] | None = Relationship(back_populates="country")


class CountryPublic(CountryBase):
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
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    country: Country | None = Relationship(back_populates="states")
    districts: list["District"] | None = Relationship(back_populates="state")
    tests: list["Test"] | None = Relationship(
        back_populates="states", link_model=TestState
    )
    question_locations: list["QuestionLocation"] = Relationship(back_populates="state")
    users: list["User"] | None = Relationship(
        back_populates="states", link_model=UserState
    )
    entities: list["Entity"] | None = Relationship(back_populates="state")


class StatePublic(StateBase):
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
    is_active: bool = Field(default=True)


class District(DistrictBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    state_id: int = Field(foreign_key="state.id", nullable=False, ondelete="CASCADE")
    state: State | None = Relationship(back_populates="districts")
    blocks: list["Block"] | None = Relationship(back_populates="district")
    question_locations: list["QuestionLocation"] = Relationship(
        back_populates="district"
    )

    tests: list["Test"] | None = Relationship(
        back_populates="districts", link_model=TestDistrict
    )
    entities: list["Entity"] | None = Relationship(back_populates="district")


class DistrictPublic(DistrictBase):
    id: int
    created_date: datetime
    modified_date: datetime
    state: StatePublic


class DistrictCreate(DistrictBase):
    state_id: int


class DistrictUpdate(DistrictBase):
    state_id: int


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
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    district: District | None = Relationship(back_populates="blocks")
    question_locations: list["QuestionLocation"] = Relationship(back_populates="block")
    entities: list["Entity"] | None = Relationship(back_populates="block")


class BlockPublic(BlockBase):
    id: int
    created_date: datetime
    modified_date: datetime


class BlockCreate(BlockBase):
    pass


class BlockUpdate(BlockBase):
    pass


class BlockBulkUploadResponse(SQLModel):
    message: str
    uploaded_blocks: int
    success_blocks: int
    failed_blocks: int
    error_log: str | None


# -----Models for Block-----

# TODO: added below comment and we can potentially remove it
# Note: TestPublicLimited.model_rebuild() is called in __init__.py after all imports
