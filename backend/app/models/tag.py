from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.test import TestTag

if TYPE_CHECKING:
    from app.models.test import Test


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    tests: list["Test"] = Relationship(back_populates="tags", link_model=TestTag)
