import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.core.timezone import get_timezone_aware_now
from app.models.utils import CorrectAnswerType

if TYPE_CHECKING:
    from app.models import QuestionRevision, Test, User
    from app.models.form import FormResponse
    from app.models.location import State
    from app.models.organization import Organization
    from app.models.question import QuestionCandidatePublic
    from app.models.tag import Tag


# Storing Answers for a question in a test by a candidate


class CandidateProfile(SQLModel):
    entity_id: int


class CandidateTestAnswerBase(SQLModel):
    __test__ = False
    candidate_test_id: int = Field(foreign_key="candidate_test.id", ondelete="CASCADE")
    question_revision_id: int = Field(
        foreign_key="question_revision.id", ondelete="CASCADE"
    )
    response: str | None = Field(nullable=True, default=None)
    visited: bool = Field(nullable=False, default=False)
    time_spent: int = Field(nullable=True, default=0)
    bookmarked: bool = Field(
        default=False,
        sa_column_kwargs={"server_default": "false"},
        description="Was this question bookmarked by test taker?",
    )


class CandidateTestAnswer(CandidateTestAnswerBase, table=True):
    __tablename__ = "candidate_test_answer"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    # Add relationship to QuestionRevision
    question_revision: "QuestionRevision" = Relationship(
        back_populates="candidate_test_answers"
    )


class CandidateTestAnswerCreate(CandidateTestAnswerBase):
    __test__ = False


class CandidateTestAnswerPublic(CandidateTestAnswerBase):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime
    correct_answer: CorrectAnswerType = None


class CandidateTestAnswerFeedback(SQLModel):
    __test__ = False
    question_revision_id: int
    response: str | None = None
    correct_answer: CorrectAnswerType = None


class CandidateTestAnswerUpdate(SQLModel):
    response: str | None
    visited: bool
    time_spent: int
    bookmarked: bool | None = None


# QR Code Candidate Request Models
class CandidateAnswerSubmitRequest(SQLModel):
    """Request model for QR code candidates to submit answers"""

    question_revision_id: int
    response: str | None = None
    visited: bool = False
    time_spent: int = 0
    bookmarked: bool = False


class BatchAnswerSubmitRequest(SQLModel):
    """Request model for submitting multiple answers at once"""

    answers: list[CandidateAnswerSubmitRequest]


class CandidateAnswerUpdateRequest(SQLModel):
    """Request model for QR code candidates to update answers"""

    response: str | None = None
    visited: bool | None = None
    time_spent: int | None = None
    bookmarked: bool = False


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
    certificate_data: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Certificate data snapshot (token, candidate_name, test_name, score, completion_date)",
    )


class CandidateTest(CandidateTestBase, table=True):
    __tablename__ = "candidate_test"
    __test__ = False
    __table_args__ = (UniqueConstraint("test_id", "candidate_id"),)
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    # Updated relationship to reference QuestionRevision instead of Question
    question_revisions: list["QuestionRevision"] = Relationship(
        back_populates="candidate_tests", link_model=CandidateTestAnswer
    )
    question_revision_ids: list[int] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    form_responses: list["FormResponse"] = Relationship(back_populates="candidate_test")


class CandidateTestProfile(SQLModel, table=True):
    __tablename__ = "candidate_test_profile"
    __test__ = False
    __table_args__ = (UniqueConstraint("candidate_test_id", "entity_id"),)

    id: int | None = Field(default=None, primary_key=True)
    candidate_test_id: int = Field(foreign_key="candidate_test.id", ondelete="CASCADE")
    entity_id: int = Field(foreign_key="entity.id", ondelete="CASCADE")
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)


class CandidateTestCreate(CandidateTestBase):
    __test__ = False


class CandidateTestPublic(CandidateTestBase):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime
    answers: list["CandidateTestAnswerFeedback"] | None = None


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
    is_active: bool = Field(default=True)


class CandidateCreate(CandidateBase):
    pass


class Candidate(CandidateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    identity: uuid.UUID | None = Field(
        default=None, unique=True, index=True, nullable=True
    )  # Only for anonymous QR code users
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    organization_id: int | None = Field(foreign_key="organization.id")
    is_deleted: bool = Field(default=False, nullable=False)
    user: "User" = Relationship(back_populates="candidates")
    tests: list["Test"] | None = Relationship(
        back_populates="candidates", link_model=CandidateTest
    )
    organization: Optional["Organization"] = Relationship(back_populates="candidates")


class CandidatePublic(CandidateBase):
    id: int
    candidate_uuid: uuid.UUID | None = None  # Include uuid in public response
    created_date: datetime
    modified_date: datetime
    organization_id: int | None
    is_deleted: bool


class CandidateUpdate(CandidateBase):
    pass


class TestCandidatePublic(SQLModel):
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
    total_questions: int
    marks_obtained: float | None
    marks_maximum: float | None
    certificate_download_url: str | None = None


class TestStatusSummary(SQLModel):
    total_test_submitted: int
    total_test_not_submitted: int
    not_submitted_active: int
    not_submitted_inactive: int


class StartTestRequest(SQLModel):
    test_id: int
    device_info: str | None = None
    candidate_profile: CandidateProfile | None = None  # Legacy support
    form_responses: dict[str, Any] | None = None  # New form responses


class StartTestResponse(SQLModel):
    candidate_uuid: uuid.UUID
    candidate_test_id: int


class OverallTestAnalyticsResponse(SQLModel):
    total_candidates: int
    overall_score_percent: float
    overall_avg_time_minutes: float
