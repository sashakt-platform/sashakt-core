from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.test import TestQuestionStaticLink

if TYPE_CHECKING:
    from app.models.test import (
        Test,  # Import only at runtime
    )


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question: str
    tests: list["Test"] = Relationship(
        back_populates="test_question_static", link_model=TestQuestionStaticLink
    )
