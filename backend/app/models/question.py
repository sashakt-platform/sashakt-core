import json
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
    from app.models.test import Test


class QuestionType(str, Enum):
    single_choice = "single-choice"
    multi_choice = "multi-choice"
    subjective = "subjective"
    numerical_integer = "numerical-integer"


class JSONSerializable:
    """Mixin to make SQLModel classes JSON serializable"""

    def dict(self) -> dict[str, Any]:
        """Convert the model to a dictionary for JSON serialization"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                if hasattr(value, "dict") and callable(value.dict):
                    result[key] = value.dict()
                else:
                    result[key] = value
        return result

    def json(self) -> str:
        """Convert the model to a JSON string"""
        return json.dumps(self.dict())


class MarkingScheme(JSONSerializable, SQLModel):
    correct: float
    wrong: float
    skipped: float


class Image(JSONSerializable, SQLModel):
    url: str
    alt_text: str | None = None


class Option(JSONSerializable, SQLModel):
    text: str
    image: Image | None = None


class QuestionBase(SQLModel):
    question_text: str = Field(nullable=False)
    instructions: str | None = Field(default=None, nullable=True)
    question_type: QuestionType = Field(nullable=False)
    options: list[dict[str, Any]] | None = Field(
        sa_type=JSON, default=None
    )  # Store as dict, not Option objects
    correct_answer: list[int] | list[str] | float | int | None = Field(
        sa_type=JSON, default=None
    )
    subjective_answer_limit: int | None = Field(default=None, nullable=True)
    is_mandatory: bool = Field(default=True, nullable=False)
    marking_scheme: dict[str, Any] | None = Field(
        sa_type=JSON, default=None
    )  # Store as dict
    solution: str | None = Field(default=None, nullable=True)
    media: dict[str, Any] | None = Field(sa_type=JSON, default=None)  # Store as dict


class QuestionLocationBase(SQLModel):
    state_id: int | None = Field(default=None, nullable=True, foreign_key="state.id")
    district_id: int | None = Field(
        default=None, nullable=True, foreign_key="district.id"
    )
    block_id: int | None = Field(default=None, nullable=True, foreign_key="block.id")


# Table models
class Question(SQLModel, table=True):
    """Main question entity that tracks metadata and points to latest revision"""

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organization.id", nullable=False)
    last_revision_id: int | None = Field(nullable=True)

    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=True, nullable=True)
    is_deleted: bool | None = Field(default=False, nullable=True)

    # Relationships
    revisions: list["QuestionRevision"] = Relationship(back_populates="question")
    locations: list["QuestionLocation"] = Relationship(back_populates="question")
    organization: "Organization" = Relationship(back_populates="question")
    tests: list["Test"] = Relationship(
        back_populates="test_question_static", link_model=TestQuestion
    )
    candidate_test: list["CandidateTest"] = Relationship(
        back_populates="question_revision", link_model=CandidateTestAnswer
    )


class QuestionRevision(QuestionBase, table=True):
    """Versioned content of a question"""

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", nullable=False)

    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=True, nullable=True)
    is_deleted: bool | None = Field(default=False, nullable=True)

    # Relationships
    question: Question = Relationship(back_populates="revisions")


class QuestionLocation(QuestionLocationBase, table=True):
    """locations for questions"""

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", nullable=False)

    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=True, nullable=True)
    is_deleted: bool | None = Field(default=False, nullable=True)

    # Relationships
    question: Question = Relationship(back_populates="locations")
    state: Optional["State"] = Relationship()
    district: Optional["District"] = Relationship()
    block: Optional["Block"] = Relationship()


# Operation models
class QuestionCreate(SQLModel):
    """Data needed to create a new question with initial revision"""

    organization_id: int
    # Question content for initial revision
    question_text: str
    instructions: str | None = None
    question_type: QuestionType
    options: list[Option] | None = None
    correct_answer: list[int] | list[str] | float | int | None = None
    subjective_answer_limit: int | None = None
    is_mandatory: bool = True
    marking_scheme: MarkingScheme | None = None
    solution: str | None = None
    media: Image | None = None
    # Optional location information
    state_id: int | None = None
    district_id: int | None = None
    block_id: int | None = None


class QuestionRevisionCreate(QuestionBase):
    """Data needed to create a new revision for an existing question"""

    question_id: int
    # Override field types from QuestionBase to accept model objects in API
    options: list[Option] | None = None
    marking_scheme: MarkingScheme | None = None
    media: Image | None = None


class QuestionLocationCreate(QuestionLocationBase):
    """Data needed to add a location to a question"""

    question_id: int


class QuestionPublic(SQLModel):
    """Public representation of a question with its current revision"""

    id: int
    organization_id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool | None

    # Current revision data
    question_text: str
    instructions: str | None
    question_type: QuestionType
    options: list[dict[str, Any]] | None  # Use dict rather than Option objects
    correct_answer: list[int] | list[str] | float | int | None
    subjective_answer_limit: int | None
    is_mandatory: bool
    marking_scheme: dict[str, Any] | None  # Use dict rather than MarkingScheme objects
    solution: str | None
    media: dict[str, Any] | None  # Use dict rather than Image objects

    # Related location information
    locations: list["QuestionLocationPublic"] | None


class QuestionLocationPublic(QuestionLocationBase):
    """Public representation of question location"""

    id: int
    state_name: str | None = None
    district_name: str | None = None
    block_name: str | None = None


class QuestionUpdate(SQLModel):
    """Fields that can be updated on the question entity itself"""

    is_active: bool | None = None
    is_deleted: bool | None = None
