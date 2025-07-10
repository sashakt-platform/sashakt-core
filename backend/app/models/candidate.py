import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.models.utils import (
    DatePublic,
    PublicStartEndDate,
    StoreEndDate,
    StoreStartEndDate,
)

if TYPE_CHECKING:
    from app.models import QuestionRevision, Test, User
    from app.models.location import State
    from app.models.question import QuestionCandidatePublic
    from app.models.tag import Tag


# Storing Answers for a question in a test by a candidate


class CandidateTestAnswerBase(SQLModel):
    __test__ = False
    candidate_test_id: int = Field(foreign_key="candidate_test.id", ondelete="CASCADE")
    question_revision_id: int = Field(
        foreign_key="question_revision.id", ondelete="CASCADE"
    )
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
    # Add relationship to QuestionRevision
    question_revision: "QuestionRevision" = Relationship(
        back_populates="candidate_test_answers"
    )


class CandidateTestAnswerCreate(CandidateTestAnswerBase):
    __test__ = False


class CandidateTestAnswerPublic(CandidateTestAnswerBase, DatePublic):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime


class CandidateTestAnswerUpdate(SQLModel):
    response: str | None
    visited: bool
    time_spent: int


# QR Code Candidate Request Models
class CandidateAnswerSubmitRequest(SQLModel):
    """Request model for QR code candidates to submit answers"""

    question_revision_id: int
    response: str | None = None
    visited: bool = False
    time_spent: int = 0


class BatchAnswerSubmitRequest(SQLModel):
    """Request model for submitting multiple answers at once"""

    answers: list[CandidateAnswerSubmitRequest]


class CandidateAnswerUpdateRequest(SQLModel):
    """Request model for QR code candidates to update answers"""

    response: str | None = None
    visited: bool | None = None
    time_spent: int | None = None


# Linking Tables between Candidate and Test


class CandidateTestBase(SQLModel):
    __test__ = False
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    candidate_id: int = Field(foreign_key="candidate.id", ondelete="CASCADE")
    device: str = Field(nullable=False)
    consent: bool = Field(default=False, nullable=False)
    start_time: datetime = Field(nullable=False)
    end_time: datetime | None = Field(nullable=True, default=None)
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
    # Updated relationship to reference QuestionRevision instead of Question
    question_revisions: list["QuestionRevision"] = Relationship(
        back_populates="candidate_tests", link_model=CandidateTestAnswer
    )


class CandidateTestCreate(CandidateTestBase, StoreStartEndDate):
    __test__ = False


class CandidateTestPublic(CandidateTestBase, PublicStartEndDate, DatePublic):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime


class CandidateTestUpdate(StoreEndDate):
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
    is_active: bool = Field(default=True)


class CandidateCreate(CandidateBase):
    pass


class Candidate(CandidateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    identity: uuid.UUID | None = Field(
        default=None, unique=True, index=True, nullable=True
    )  # Only for anonymous QR code users
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_deleted: bool = Field(default=False, nullable=False)
    user: "User" = Relationship(back_populates="candidates")
    tests: list["Test"] | None = Relationship(
        back_populates="candidates", link_model=CandidateTest
    )


class CandidatePublic(CandidateBase, DatePublic):
    id: int
    candidate_uuid: uuid.UUID | None = None  # Include uuid in public response
    created_date: datetime
    modified_date: datetime
    is_deleted: bool


class CandidateUpdate(CandidateBase):
    pass


class TestCandidatePublic(DatePublic, PublicStartEndDate):
    """Test information for candidates with safe questions (no answers)"""

    # Test info (all fields from TestBase)
    id: int
    name: str
    description: str | None
    start_time: datetime | None
    end_time: datetime | None
    time_limit: int | None
    marks_level: str | None
    marks: int | None
    completion_message: str | None
    start_instructions: str | None
    link: str
    no_of_attempts: int | None
    shuffle: bool
    random_questions: bool
    no_of_random_questions: int | None
    question_pagination: int
    is_template: bool
    template_id: int | None
    created_by_id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool

    # Safe questions (no answers)
    question_revisions: list["QuestionCandidatePublic"]

    # Other test data
    tags: list["Tag"]
    states: list["State"]
    total_questions: int

    # Candidate test info
    candidate_test: "CandidateTestPublic"


class Result(SQLModel):
    correct_answer: int
    incorrect_answer: int
    mandatory_not_attempted: int
    optional_not_attempted: int
