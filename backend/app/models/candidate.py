from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models import Question, Test, User


# Storing Answers for a question in a test by a candidate


class CandidateTestAnswerBase(SQLModel):
    __test__ = False
    candidate_test_id: int = Field(foreign_key="candidate_test.id", ondelete="CASCADE")
    question_revision_id: int = Field(
        foreign_key="question.id", ondelete="CASCADE"
    )  # Will Update to question_revision.id once the latter model is ready
    response: str | None = Field(nullable=False, default=None)
    visited: bool = Field(nullable=False, default=False)
    time_spent: int = Field(nullable=True, default=0)


class CandidateTestAnswer(CandidateTestAnswerBase, table=True):
    __tablename__ = "candidate_test_answer"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )


class CandidateTestAnswerCreate(CandidateTestAnswerBase):
    __test__ = False


class CandidateTestAnswerPublic(CandidateTestAnswerBase):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime


class CandidateTestAnswerUpdate(SQLModel):
    response: str | None
    visited: bool
    time_spent: int


# Linking Tables between Candidate and Test


class CandidateTestBase(SQLModel):
    __test__ = False
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    candidate_id: int = Field(foreign_key="candidate.id", ondelete="CASCADE")
    device: str = Field(nullable=False)
    consent: bool = Field(default=False, nullable=False)
    start_time: datetime = Field(nullable=False)
    end_time: datetime | None = Field(nullable=False, default=None)
    is_submitted: bool = Field(default=False, nullable=False)


class CandidateTest(CandidateTestBase, table=True):
    __tablename__ = "candidate_test"
    __test__ = False
    __table_args__ = (UniqueConstraint("test_id", "candidate_id"),)
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    quesion_revision: list["Question"] = Relationship(
        back_populates="candidate_test", link_model=CandidateTestAnswer
    )


class CandidateTestCreate(CandidateTestBase):
    __test__ = False


class CandidateTestPublic(CandidateTestBase):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime


class CandidateTestUpdate(SQLModel):
    __test__ = False
    device: str
    consent: bool
    end_time: datetime | None
    is_submitted: bool


# Models for Candidates


class CandidateBase(SQLModel):
    user_id: int | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="CASCADE"
    )


class CandidateCreate(CandidateBase):
    pass


class Candidate(CandidateBase, table=True):
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
    user: "User" = Relationship(back_populates="candidates")
    tests: list["Test"] | None = Relationship(
        back_populates="candidates", link_model=CandidateTest
    )


class CandidatePublic(CandidateBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool


class CandidateUpdate(CandidateBase):
    pass
