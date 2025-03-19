from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models import CandidateTest, CandidateTestAnswer
from app.models.test import TestQuestion

if TYPE_CHECKING:
    from app.models import (
        Test,
    )


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question: str = Field(nullable=False, index=True)
    tests: list["Test"] = Relationship(
        back_populates="test_question_static", link_model=TestQuestion
    )
    candidate_test: list["CandidateTest"] = Relationship(
        back_populates="quesion_revision", link_model=CandidateTestAnswer
    )
