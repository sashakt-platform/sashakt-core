from sqlmodel import Field, Relationship, SQLModel, Session, create_engine
from typing import List, Optional
from datetime import datetime, timezone


class BaseModel(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_date: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: Optional[bool] = Field(nullable=True)


class Organization(BaseModel, table=True):
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)


class Country(BaseModel, table=True):
    name: str = Field(nullable=False)
    states: Optional[List["State"]] = Relationship(back_populates="country")


class State(BaseModel, table=True):
    name: str = Field(nullable=False)
    country_id: int = Field(foreign_key="country.id")
    country: Optional[Country] = Relationship(back_populates="states")
    districts: Optional[List["District"]] = Relationship(back_populates="state")


class District(BaseModel, table=True):
    name: str = Field(nullable=False)
    state_id: int = Field(foreign_key="state.id")
    state: Optional[State] = Relationship(back_populates="districts")
    blocks: Optional[List["Block"]] = Relationship(back_populates="district")


class Block(BaseModel, table=True):
    name: str = Field(nullable=False)
    district_id: int = Field(foreign_key="district.id")
    district: Optional[District] = Relationship(back_populates="blocks")

