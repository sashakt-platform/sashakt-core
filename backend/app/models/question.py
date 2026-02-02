from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from pydantic import model_validator
from sqlalchemy.orm import Mapped
from sqlmodel import JSON, Field, Relationship, SQLModel, UniqueConstraint
from typing_extensions import TypedDict

from app.core.timezone import get_timezone_aware_now
from app.models.candidate import CandidateTestAnswer
from app.models.test import TestQuestion
from app.models.user import UserPublic
from app.models.utils import CorrectAnswerType, MarkingScheme

if TYPE_CHECKING:
    from app.models.candidate import CandidateTest
    from app.models.location import Block, District, State
    from app.models.organization import Organization
    from app.models.tag import Tag
    from app.models.test import Test
    from app.models.user import User


class QuestionType(str, Enum):
    """Types of questions available in the system"""

    single_choice = "single-choice"
    multi_choice = "multi-choice"
    subjective = "subjective"
    numerical_integer = "numerical-integer"


# Simple structure classes - no SQLModel inheritance
class MarkingSchemeBase:
    """Defines scoring rules for a question"""

    correct: float
    wrong: float
    skipped: float


class ImageBase:
    """Represents an image used in questions or options"""

    url: str
    alt_text: str | None = None


class OptionBase:
    """Represents a single option in a choice-based question"""

    value: str
    image: dict[str, Any] | None = None


class Image(SQLModel):
    """Represents an image used in questions or options"""

    url: str = Field(description="URL or path to the image")
    alt_text: str | None = Field(
        default=None, description="Alternative text for accessibility"
    )


class Option(TypedDict):
    """Represents a single option in a choice-based question"""

    id: int
    key: str
    value: str


class FailedQuestion(TypedDict):
    row_number: int
    question_text: str
    error: str


# Type aliases for cleaner annotations
OptionDict = dict[str, Any]  # Consider using dict[str, Union[str, ImageDict]] later
MarkingSchemeDict = dict[str, float]  # More specific than dict[str, Any]
ImageDict = dict[str, Any]  # Consider using dict[str, Union[str, None]] later


class QuestionRevisionInfo(SQLModel):
    id: int
    created_date: datetime
    text: str
    type: str
    is_current: bool
    created_by_id: UserPublic


class QuestionBase(SQLModel):
    """Base model with common fields for questions"""

    question_text: str = Field(nullable=False, description="The actual question text")
    instructions: str | None = Field(
        default=None,
        nullable=True,
        description="Instructions for answering the question",
    )
    question_type: QuestionType = Field(
        nullable=False,
        description="Type of question (single-choice, multi-choice, etc.)",
    )

    options: list[Option] | None = Field(
        sa_type=JSON,
        default=None,
        description="Available options for choice-based questions",
    )

    correct_answer: CorrectAnswerType = Field(
        sa_type=JSON,
        default=None,
        description="The correct answer(s) for this question",
    )
    subjective_answer_limit: int | None = Field(
        default=None,
        nullable=True,
        description="Character limit for subjective answers",
    )
    is_mandatory: bool = Field(
        default=True,
        nullable=False,
        description="Whether the question must be answered",
    )
    is_active: bool = Field(default=True, description="Whether this question is active")
    marking_scheme: MarkingScheme | None = Field(
        default={"correct": 1, "wrong": 0, "skipped": 0},
        sa_type=JSON,
        description="Scoring rules for this question",
    )
    solution: str | None = Field(
        default=None, nullable=True, description="Explanation of the correct answer"
    )
    media: dict[str, Any] | None = Field(
        sa_type=JSON, default=None, description="Associated media for this question"
    )

    @model_validator(mode="after")
    def validate_question(self) -> "QuestionBase":
        question_type = self.question_type
        options = self.options
        correct_answer = self.correct_answer
        if question_type in ["single-choice", "multi-choice"]:
            if options and correct_answer is not None:
                option_ids = [
                    opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", None)
                    for opt in options
                ]
                if len(option_ids) != len(set(option_ids)):
                    raise ValueError("Option IDs must be unique.")
                answer_ids = (
                    correct_answer
                    if isinstance(correct_answer, list)
                    else [correct_answer]
                )
                for ans_id in answer_ids:
                    if ans_id not in option_ids:
                        raise ValueError(
                            f"Correct answer ID {ans_id} does not match any option ID."
                        )
            if question_type == QuestionType.single_choice:
                if not isinstance(correct_answer, list) or len(correct_answer) != 1:
                    raise ValueError(
                        "Single-choice questions must have exactly one correct answer."
                    )
            elif question_type == QuestionType.multi_choice:
                if not isinstance(correct_answer, list) or len(correct_answer) < 1:
                    raise ValueError(
                        "Multi-choice questions must have at least one correct answer."
                    )

        return self


class QuestionTag(SQLModel, table=True):
    """Relationship table linking questions to tags"""

    __tablename__ = "question_tag"
    __table_args__ = (UniqueConstraint("question_id", "tag_id"),)

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Primary key for the question-tag relationship",
    )
    question_id: int = Field(
        foreign_key="question.id",
        nullable=False,
        description="ID of the question",
        ondelete="CASCADE",
    )
    tag_id: int = Field(
        foreign_key="tag.id",
        nullable=False,
        description="ID of the tag",
        ondelete="CASCADE",
    )

    created_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        description="When this relationship was created",
    )


class Question(SQLModel, table=True):
    """Main question entity that tracks metadata and points to latest revision"""

    id: int | None = Field(
        default=None, primary_key=True, description="Primary key for the question"
    )
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        description="ID of the organization that owns this question",
    )
    last_revision_id: int | None = Field(
        nullable=True, description="ID of the current revision of this question"
    )

    created_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        description="When this question was created",
    )
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
        description="When this question was last modified",
    )
    is_active: bool = Field(default=True, description="Whether this question is active")

    # Relationships
    # All revisions of this question
    revisions: Mapped[list["QuestionRevision"]] = Relationship(
        back_populates="question", cascade_delete=True
    )
    # Geographic locations associated with this question
    locations: Mapped[list["QuestionLocation"]] = Relationship(
        back_populates="question", cascade_delete=True
    )
    # Tags associated with this question
    tags: Mapped[list["Tag"]] = Relationship(
        back_populates="questions",
        link_model=QuestionTag,
    )
    # Organization that owns this question
    organization: "Organization" = Relationship(back_populates="question")


class QuestionRevision(QuestionBase, table=True):
    """Versioned content of a question"""

    __tablename__ = "question_revision"
    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Primary key for the question revision",
    )
    question_id: int = Field(
        foreign_key="question.id",
        nullable=False,
        description="ID of the parent question",
        ondelete="CASCADE",
    )
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="ID of the user who created this revision",
    )
    created_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        description="When this revision was created",
    )
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
        description="When this revision was last modified",
    )

    # Relationships
    # Parent question for this revision
    question: Question = Relationship(back_populates="revisions")
    # User who created this revision
    created_by: "User" = Relationship(back_populates="question_revisions")
    # Tests that include this question revision
    tests: list["Test"] = Relationship(
        back_populates="question_revisions",
        link_model=TestQuestion,
    )
    # Candidate tests that include this question revision
    candidate_tests: list["CandidateTest"] = Relationship(
        back_populates="question_revisions",
        link_model=CandidateTestAnswer,
    )
    # Direct relationship to candidate test answers
    candidate_test_answers: list["CandidateTestAnswer"] = Relationship(
        back_populates="question_revision"
    )
    # Direct relationship to test questions
    test_questions: list["TestQuestion"] = Relationship(
        back_populates="question_revision"
    )


class QuestionLocation(SQLModel, table=True):
    """Geographical locations for questions"""

    __tablename__ = "question_location"
    __table_args__ = (
        # Each row has only one of state_id, district_id, or block_id
        UniqueConstraint("question_id", "state_id"),
        UniqueConstraint("question_id", "district_id"),
        UniqueConstraint("question_id", "block_id"),
    )
    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Primary key for the question location",
    )
    question_id: int = Field(
        foreign_key="question.id",
        nullable=False,
        description="ID of the question",
        ondelete="CASCADE",
    )
    state_id: int | None = Field(
        default=None,
        nullable=True,
        foreign_key="state.id",
        description="ID of the state this question is associated with",
    )
    district_id: int | None = Field(
        default=None,
        nullable=True,
        foreign_key="district.id",
        description="ID of the district this question is associated with",
    )
    block_id: int | None = Field(
        default=None,
        nullable=True,
        foreign_key="block.id",
        description="ID of the block this question is associated with",
    )
    created_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        description="When this location was created",
    )

    # Relationships
    # Question associated with this location
    question: Mapped[Question] = Relationship(back_populates="locations")
    # State associated with this location
    state: Mapped[Optional["State"]] = Relationship(back_populates="question_locations")
    # District associated with this location
    district: Mapped[Optional["District"]] = Relationship(
        back_populates="question_locations"
    )
    # Block associated with this location
    block: Mapped[Optional["Block"]] = Relationship(back_populates="question_locations")


# Use inheritance to avoid field duplication
class QuestionCreate(QuestionBase):
    """Data needed to create a new question with initial revision"""

    organization_id: int = Field(
        description="ID of the organization that will own this question"
    )
    state_ids: list[int] | None = Field(
        default=None, description="IDs of states to associate"
    )
    district_ids: list[int] | None = Field(
        default=None, description="IDs of districts to associate"
    )
    block_ids: list[int] | None = Field(
        default=None, description="IDs of blocks to associate"
    )
    # Tag relationships
    tag_ids: list[int] | None = Field(
        default=None, description="IDs of tags to associate with the question"
    )


class QuestionRevisionCreate(QuestionBase):
    """Data needed to create a new revision for an existing question"""

    pass


class QuestionTagsUpdate(SQLModel):
    """Data to update all tags for a question."""

    tag_ids: list[int] = Field(
        description="The complete list of tag IDs to associate with the question"
    )


class QuestionLocationUpdateItem(SQLModel):
    """Item for specifying a location to associate with a question."""

    # Only one of these should be provided
    state_id: int | None = Field(
        default=None, description="ID of the state to associate"
    )
    district_id: int | None = Field(
        default=None, description="ID of the district to associate"
    )
    block_id: int | None = Field(
        default=None, description="ID of the block to associate"
    )


class QuestionLocationsUpdate(SQLModel):
    """Data to update all locations for a question."""

    locations: list[QuestionLocationUpdateItem] = Field(
        description="The complete list of locations to associate with the question"
    )


class QuestionLocationPublic(SQLModel):
    """Public representation of question location"""

    id: int = Field(description="ID of the location")
    state_id: int | None = Field(default=None, description="ID of the state")
    district_id: int | None = Field(default=None, description="ID of the district")
    block_id: int | None = Field(default=None, description="ID of the block")
    state_name: str | None = Field(default=None, description="Name of the state")
    district_name: str | None = Field(default=None, description="Name of the district")
    block_name: str | None = Field(default=None, description="Name of the block")


class QuestionPublic(SQLModel):
    """Public representation of a question with its current revision"""

    id: int = Field(description="ID of the question")
    organization_id: int = Field(
        description="ID of the organization that owns this question"
    )
    created_date: datetime = Field(description="When this question was created")
    modified_date: datetime = Field(description="When this question was last modified")
    is_active: bool = Field(default=True, description="Whether this question is active")

    # Current revision data
    question_text: str = Field(description="The question text")
    instructions: str | None = Field(description="Instructions for answering")
    question_type: QuestionType = Field(description="Type of question")
    options: list[Option] | None = Field(
        description="Available options for choice questions"
    )
    correct_answer: CorrectAnswerType = Field(description="The correct answer(s)")
    subjective_answer_limit: int | None = Field(
        description="Character limit for subjective answers"
    )
    is_mandatory: bool = Field(description="Whether the question must be answered")
    marking_scheme: MarkingScheme | None = Field(description="Scoring rules")
    solution: str | None = Field(description="Explanation of the answer")
    media: dict[str, Any] | None = Field(description="Associated media")
    latest_question_revision_id: int = Field(
        description="ID of the latest revision of this question"
    )
    created_by_id: int = Field(
        description="ID of the user who created the current revision"
    )
    # Related location and tag information
    locations: list["QuestionLocationPublic"] | None = Field(
        description="Geographic locations associated with this question"
    )
    tags: list[Any] | None = Field(description="Tags associated with this question")


class QuestionCandidatePublic(SQLModel):
    """Candidate-safe representation of a question (no answers or solutions)"""

    id: int = Field(description="ID of the question")
    question_text: str = Field(description="The question text")
    instructions: str | None = Field(description="Instructions for answering")
    question_type: QuestionType = Field(description="Type of question")
    options: list[Option] | None = Field(
        description="Available options for choice questions"
    )
    subjective_answer_limit: int | None = Field(
        description="Character limit for subjective answers"
    )
    is_mandatory: bool = Field(description="Whether the question must be answered")
    media: dict[str, Any] | None = Field(description="Associated media")
    marking_scheme: MarkingScheme | None = Field(description="Scoring rules")


class QuestionUpdate(SQLModel):
    """Fields that can be updated on the question entity itself"""

    is_active: bool = Field(default=True, description="Whether this question is active")


class BulkUploadQuestionsResponse(SQLModel):
    message: str
    uploaded_questions: int
    success_questions: int
    failed_questions: int
    error_log: str | None


class DeleteQuestion(SQLModel):
    delete_success_count: int
    delete_failure_list: list[QuestionPublic] | None = None


# Force model rebuild to handle forward references
QuestionPublic.model_rebuild()
QuestionRevision.model_rebuild()
