from datetime import datetime, timezone
from enum import Enum
from typing import List, Union
from sqlmodel import Field, Relationship, SQLModel, JSON

from models.location import State, District, Block
from models.organization import Organization

class BaseModel(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=True, nullable=True)
    is_deleted: bool | None = Field(default=False, nullable=True)

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

class Question(BaseModel, table=True):
    """Main question entity that tracks metadata and points to latest revision"""
    organization_id: int = Field(foreign_key="organization.id", nullable=False)
    last_revision_id: int | None = Field(nullable=True)  # Updated after revision creation
    
    # Relationships
    revisions: List["QuestionRevision"] = Relationship(back_populates="question") # multiple revisions?
    locations: List["QuestionLocation"] = Relationship(back_populates="question")
    # tags: List["QuestionTag"] = Relationship(back_populates="question")
    organization: "Organization" = Relationship(back_populates="question")

class QuestionRevision(BaseModel, table=True):
    """Versioned content of a question"""
    question_id: int = Field(foreign_key="question.id", nullable=False)
    question_text: str = Field(nullable=False)
    media: Image | None = Field(sa_type=JSON, default=None)
    instructions: str | None = Field(nullable=True)
    question_type: QuestionType = Field(nullable=False)
    options: List[Option] | None = Field(sa_type=JSON, default=None)
    correct_answer: Union[List[int], List[str], float, int, None] = Field(sa_type=JSON, default=None)
    subjective_answer_limit: int | None = Field(nullable=True)
    is_mandatory: bool = Field(default=True)
    marking_scheme: MarkingScheme | None = Field(sa_type=JSON, default=None)
    solution: str | None = Field(nullable=True)
    # created_by_id: int = Field(foreign_key="user.id", nullable=False)

    # Relationships
    question: Question = Relationship(back_populates="revisions")
    # created_by: "User" = Relationship() : create user later

class QuestionLocation(BaseModel, table=True):
    """locations for questions"""
    question_id: int = Field(foreign_key="question.id", nullable=False)
    state_id: int | None = Field(foreign_key="state.id", nullable=True)
    district_id: int | None = Field(foreign_key="district.id", nullable=True)
    block_id: int | None = Field(foreign_key="block.id", nullable=True)
    
    # Relationships
    question: Question = Relationship(back_populates="locations")
    state: "State" | None = Relationship()
    district: "District" | None = Relationship()
    block: "Block" | None = Relationship()

# class QuestionTag(BaseModel, table=True):
#     """Many-to-many relationship between questions and tags"""
#     question_id: int = Field(foreign_key="question.id", primary_key=True)
#     tag_id: int = Field(foreign_key="tag.id", primary_key=True)
    
#     # Relationships
#     question: Question = Relationship(back_populates="tags")
#     tag: Tag = Relationship(back_populates="questions")