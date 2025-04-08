from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlmodel import JSON, Field, Relationship, SQLModel

from app.models.candidate import CandidateTestAnswer
from app.models.test import TestQuestion

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

    text: str
    image: dict[str, Any] | None = None


# SQLModel implementations
class MarkingScheme(SQLModel):
    """Defines scoring rules for a question"""

    correct: float = Field(description="Points awarded for a correct answer")
    wrong: float = Field(description="Points deducted for a wrong answer")
    skipped: float = Field(
        description="Points awarded/deducted when question is skipped"
    )


class Image(SQLModel):
    """Represents an image used in questions or options"""

    url: str = Field(description="URL or path to the image")
    alt_text: str | None = Field(
        default=None, description="Alternative text for accessibility"
    )


class Option(SQLModel):
    """Represents a single option in a choice-based question"""

    text: str = Field(description="Text content of the option")
    image: dict[str, Any] | None = Field(
        default=None, description="Optional image associated with this option"
    )


# Type aliases for cleaner annotations
OptionDict = dict[str, Any]
MarkingSchemeDict = dict[str, Any]
ImageDict = dict[str, Any]
CorrectAnswerType = list[int] | list[str] | float | int | None


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
    options: list[dict[str, Any]] | None = Field(
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
    marking_scheme: dict[str, Any] | None = Field(
        sa_type=JSON, default=None, description="Scoring rules for this question"
    )
    solution: str | None = Field(
        default=None, nullable=True, description="Explanation of the correct answer"
    )
    media: dict[str, Any] | None = Field(
        sa_type=JSON, default=None, description="Associated media for this question"
    )


class QuestionLocationBase(SQLModel):
    """Base model for geographic location of a question"""

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


class QuestionTag(SQLModel, table=True):
    """Relationship table linking questions to tags"""

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Primary key for the question-tag relationship",
    )
    question_id: int = Field(
        foreign_key="question.id", nullable=False, description="ID of the question"
    )
    tag_id: int = Field(
        foreign_key="tag.id", nullable=False, description="ID of the tag"
    )

    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this relationship was created",
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
        description="When this relationship was last modified",
    )
    is_active: bool | None = Field(
        default=True, nullable=True, description="Whether this relationship is active"
    )
    is_deleted: bool | None = Field(
        default=False,
        nullable=True,
        description="Whether this relationship is marked as deleted",
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
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this question was created",
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
        description="When this question was last modified",
    )
    is_active: bool | None = Field(
        default=True, nullable=True, description="Whether this question is active"
    )
    is_deleted: bool | None = Field(
        default=False,
        nullable=True,
        description="Whether this question is marked as deleted",
    )

    # Relationships
    revisions: list["QuestionRevision"] = Relationship(
        back_populates="question", description="All revisions of this question"
    )
    locations: list["QuestionLocation"] = Relationship(
        back_populates="question",
        description="Geographic locations associated with this question",
    )
    tags: list["Tag"] = Relationship(
        back_populates="questions",
        link_model=QuestionTag,
        description="Tags associated with this question",
    )
    organization: "Organization" = Relationship(
        back_populates="question", description="Organization that owns this question"
    )
    tests: list["Test"] = Relationship(
        back_populates="test_question_static",
        link_model=TestQuestion,
        description="Tests that include this question",
    )
    candidate_test: list["CandidateTest"] = Relationship(
        back_populates="question_revision",
        link_model=CandidateTestAnswer,
        description="Candidate tests that include this question",
    )


class QuestionRevision(QuestionBase, table=True):
    """Versioned content of a question"""

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Primary key for the question revision",
    )
    question_id: int = Field(
        foreign_key="question.id",
        nullable=False,
        description="ID of the parent question",
    )
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="ID of the user who created this revision",
    )

    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this revision was created",
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
        description="When this revision was last modified",
    )
    is_active: bool | None = Field(
        default=True, nullable=True, description="Whether this revision is active"
    )
    is_deleted: bool | None = Field(
        default=False,
        nullable=True,
        description="Whether this revision is marked as deleted",
    )

    # Relationships
    question: Question = Relationship(
        back_populates="revisions", description="Parent question for this revision"
    )
    created_by: "User" = Relationship(
        back_populates="question_revisions",
        description="User who created this revision",
    )


class QuestionLocation(QuestionLocationBase, table=True):
    """Geographical locations for questions"""

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Primary key for the question location",
    )
    question_id: int = Field(
        foreign_key="question.id", nullable=False, description="ID of the question"
    )

    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this location was created",
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
        description="When this location was last modified",
    )
    is_active: bool | None = Field(
        default=True, nullable=True, description="Whether this location is active"
    )
    is_deleted: bool | None = Field(
        default=False,
        nullable=True,
        description="Whether this location is marked as deleted",
    )

    # Relationships
    question: Question = Relationship(
        back_populates="locations", description="Question associated with this location"
    )
    state: Optional["State"] = Relationship(
        description="State associated with this location"
    )
    district: Optional["District"] = Relationship(
        description="District associated with this location"
    )
    block: Optional["Block"] = Relationship(
        description="Block associated with this location"
    )


class QuestionCreate(SQLModel):
    """Data needed to create a new question with initial revision"""

    organization_id: int = Field(
        description="ID of the organization that will own this question"
    )
    created_by_id: int = Field(description="ID of the user creating this question")
    # Question content for initial revision
    question_text: str = Field(description="The question text")
    instructions: str | None = Field(
        default=None, description="Instructions for answering"
    )
    question_type: QuestionType = Field(description="Type of question")
    options: list[dict[str, Any]] | None = Field(
        default=None, description="Available options for choice questions"
    )
    correct_answer: CorrectAnswerType = Field(
        default=None, description="The correct answer(s)"
    )
    subjective_answer_limit: int | None = Field(
        default=None, description="Character limit for subjective answers"
    )
    is_mandatory: bool = Field(
        default=True, description="Whether the question must be answered"
    )
    marking_scheme: dict[str, Any] | None = Field(
        default=None, description="Scoring rules"
    )
    solution: str | None = Field(default=None, description="Explanation of the answer")
    media: dict[str, Any] | None = Field(default=None, description="Associated media")
    # Optional location information
    state_id: int | None = Field(default=None, description="ID of the state")
    district_id: int | None = Field(default=None, description="ID of the district")
    block_id: int | None = Field(default=None, description="ID of the block")
    tag_ids: list[int] | None = Field(
        default=None, description="IDs of tags to associate with the question"
    )


class QuestionRevisionCreate(SQLModel):
    """Data needed to create a new revision for an existing question"""

    question_id: int = Field(description="ID of the question to create a revision for")
    created_by_id: int = Field(description="ID of the user creating this revision")
    # Question content fields
    question_text: str = Field(description="The question text")
    instructions: str | None = Field(
        default=None, description="Instructions for answering"
    )
    question_type: QuestionType = Field(description="Type of question")
    options: list[dict[str, Any]] | None = Field(
        default=None, description="Available options for choice questions"
    )
    correct_answer: CorrectAnswerType = Field(
        default=None, description="The correct answer(s)"
    )
    subjective_answer_limit: int | None = Field(
        default=None, description="Character limit for subjective answers"
    )
    is_mandatory: bool = Field(
        default=True, description="Whether the question must be answered"
    )
    marking_scheme: dict[str, Any] | None = Field(
        default=None, description="Scoring rules"
    )
    solution: str | None = Field(default=None, description="Explanation of the answer")
    media: dict[str, Any] | None = Field(default=None, description="Associated media")


class QuestionLocationCreate(QuestionLocationBase):
    """Data needed to add a location to a question"""

    question_id: int = Field(
        description="ID of the question to associate with this location"
    )


class QuestionTagCreate(SQLModel):
    """Data needed to add a tag to a question"""

    question_id: int = Field(description="ID of the question to tag")
    tag_id: int = Field(description="ID of the tag to associate with the question")


class QuestionLocationPublic(QuestionLocationBase):
    """Public representation of question location"""

    id: int = Field(description="ID of the location")
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
    is_active: bool | None = Field(description="Whether this question is active")
    is_deleted: bool | None = Field(
        description="Whether this question is marked as deleted"
    )

    # Current revision data
    question_text: str = Field(description="The question text")
    instructions: str | None = Field(description="Instructions for answering")
    question_type: QuestionType = Field(description="Type of question")
    options: list[dict[str, Any]] | None = Field(
        description="Available options for choice questions"
    )
    correct_answer: CorrectAnswerType = Field(description="The correct answer(s)")
    subjective_answer_limit: int | None = Field(
        description="Character limit for subjective answers"
    )
    is_mandatory: bool = Field(description="Whether the question must be answered")
    marking_scheme: dict[str, Any] | None = Field(description="Scoring rules")
    solution: str | None = Field(description="Explanation of the answer")
    media: dict[str, Any] | None = Field(description="Associated media")
    created_by_id: int = Field(
        description="ID of the user who created the current revision"
    )

    # Related location and tag information
    locations: list["QuestionLocationPublic"] | None = Field(
        description="Geographic locations associated with this question"
    )
    tags: list[Any] | None = Field(description="Tags associated with this question")


class QuestionUpdate(SQLModel):
    """Fields that can be updated on the question entity itself"""

    is_active: bool | None = Field(
        default=None, description="Whether this question is active"
    )
    is_deleted: bool | None = Field(
        default=None, description="Whether this question is marked as deleted"
    )


# Force model rebuild to handle forward references
QuestionPublic.model_rebuild()
