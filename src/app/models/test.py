import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class MarksLevelEnum(str, enum.Enum):
    QUESTION = "question"
    TEST = "test"


if TYPE_CHECKING:
    from app.models.question import Question
    from app.models.tag import Tag
    from app.models.user import User


class TestTagLink(SQLModel, table=True):
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int | None = Field(default=None, foreign_key="test.id", primary_key=True)
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


class TestQuestionStaticLink(SQLModel, table=True):
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int | None = Field(default=None, foreign_key="test.id", primary_key=True)
    question_id: int | None = Field(
        default=None, foreign_key="question.id", primary_key=True
    )


class Test(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(nullable=True)
    name: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    start_time: datetime | None = Field(nullable=True)
    end_time: datetime | None = Field(nullable=True)
    time_limit: int | None = Field(nullable=True)
    marks_level: MarksLevelEnum | None = Field(sa_column=Column(JSON), default=None)
    marks: int | None = Field(nullable=True)
    completion_message: str | None = Field(nullable=True)
    start_instructions: str | None = Field(nullable=True)
    link: str | None = Field(nullable=False)
    no_of_attempts: int | None = Field(nullable=False, default=1)
    shuffle: bool | None = Field(nullable=False, default=False)
    random_questions: bool | None = Field(nullable=False, default=False)
    no_of_questions: int | None = Field(nullable=False)
    question_pagination: int | None = Field(default=1, nullable=False)
    is_template: bool | None = Field(default=False, nullable=False)
    template_id: int | None = Field(foreign_key="test.id", nullable=True)
    template: Optional["Test"] = Relationship(
        back_populates="tests", sa_relationship_kwargs={"remote_side": "Test.id"}
    )
    tests: list["Test"] = Relationship(back_populates="template")
    tags: list["Tag"] = Relationship(back_populates="tests", link_model=TestTagLink)
    test_question_static: list["Question"] = Relationship(
        back_populates="tests", link_model=TestQuestionStaticLink
    )
    created_by_id: int = Field(foreign_key="user.id")
    created_by: Optional["User"] = Relationship(back_populates="tests")
    is_deleted: bool = Field(default=False, nullable=False)
