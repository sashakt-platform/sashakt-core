from datetime import datetime, timezone
from enum import Enum

from models.location import Block, District, State
from models.organization import Organization
from sqlmodel import JSON, Field, Relationship, SQLModel


class QuestionType(str, Enum):
    single_choice = "single-choice"
    multi_choice = "multi-choice"
    subjective = "subjective"
    numerical_integer = "numerical-integer"


class MarkingScheme(SQLModel):
    correct: float
    wrong: float
    skipped: float


class Image(SQLModel):
    url: str
    alt_text: str | None = None


class Option(SQLModel):
    text: str
    image: Image | None = None


class QuestionBase(SQLModel):
    question_text: str = Field(nullable=False)
    instructions: str | None = Field(default=None, nullable=True)
    question_type: QuestionType = Field(nullable=False)
    options: list[Option] | None = Field(sa_type=JSON, default=None)
    correct_answer: list[int] | list[str] | float | int | None = Field(
        sa_type=JSON, default=None
    )
    subjective_answer_limit: int | None = Field(default=None, nullable=True)
    is_mandatory: bool = Field(default=True, nullable=False)
    marking_scheme: MarkingScheme | None = Field(sa_type=JSON, default=None)
    solution: str | None = Field(default=None, nullable=True)
    media: Image | None = Field(sa_type=JSON, default=None)


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
    organization: Organization = Relationship(back_populates="question")


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
    state: State | None = Relationship()
    district: District | None = Relationship()
    block: Block | None = Relationship()


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
    options: list[Option] | None
    correct_answer: list[int] | list[str] | float | int | None
    subjective_answer_limit: int | None
    is_mandatory: bool
    marking_scheme: MarkingScheme | None
    solution: str | None
    media: Image | None

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
