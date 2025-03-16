import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


class MarksLevelEnum(str, enum.Enum):
    QUESTION = "question"
    TEST = "test"


if TYPE_CHECKING:
    from app.models.question import Question
    from app.models.tag import Tag
    from app.models.user import User


class TestTagLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    __test__ = False
    __table_args__ = (UniqueConstraint("test_id", "tag_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE")


class TestQuestionStaticLink(SQLModel, table=True):
    __test__ = False
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int | None = Field(default=None, foreign_key="test.id", primary_key=True)
    question_id: int | None = Field(
        default=None, foreign_key="question.id", primary_key=True
    )


class TestBase(SQLModel):
    name: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    start_time: datetime | None = Field(default=None, nullable=True)
    end_time: datetime | None = Field(default=None, nullable=True)
    time_limit: int | None = Field(default=None, nullable=True)
    marks_level: MarksLevelEnum | None = Field(default=None, nullable=True)
    marks: int | None = Field(default=None, nullable=True)
    completion_message: str | None = Field(default=None, nullable=True)
    start_instructions: str | None = Field(default=None, nullable=True)
    link: str | None = Field(nullable=False)
    no_of_attempts: int | None = Field(nullable=False, default=1)
    shuffle: bool | None = Field(nullable=False, default=False)
    random_questions: bool | None = Field(nullable=False, default=False)
    no_of_questions: int | None = Field(default=None, nullable=False)
    question_pagination: int = Field(default=1, nullable=False)
    is_template: bool | None = Field(default=False, nullable=False)
    template_id: int | None = Field(default=None, foreign_key="test.id", nullable=True)
    created_by_id: int = Field(foreign_key="user.id", nullable=False)


class Test(TestBase, table=True):
    __test__ = False
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
    template: Optional["Test"] = Relationship(
        back_populates="tests", sa_relationship_kwargs={"remote_side": "Test.id"}
    )
    tests: list["Test"] | None = Relationship(back_populates="template")
    tags: list["Tag"] | None = Relationship(
        back_populates="tests", link_model=TestTagLink
    )
    test_question_static: list["Question"] | None = Relationship(
        back_populates="tests", link_model=TestQuestionStaticLink
    )
    created_by: Optional["User"] = Relationship(back_populates="tests")


class TestCreate(TestBase):
    tags: list[int] = []
    test_question_static: list[int] = []


class TestPublic(TestBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool
    tags: list[int]
    test_question_static: list[int]


class TestUpdate(TestBase):
    name: str | None
    description: str | None
    start_time: datetime | None
    end_time: datetime | None
    time_limit: int | None
    marks_level: MarksLevelEnum | None
    marks: int | None
    completion_message: str | None
    start_instructions: str | None
    link: str | None
    no_of_attempts: int | None
    shuffle: bool | None
    random_questions: bool | None
    no_of_questions: int | None
    question_pagination: int | None
    is_template: bool | None
    template_id: int | None
    created_by_id: int | None
    tags: list[int] = []
    test_question_static: list[int] = []


# Sample payload for TestUpdate
sample_payload = {
    "name": "Sample Test",
    "description": "This is a sample test description.",
    "start_time": None,
    "end_time": None,
    "time_limit": 120,
    "marks_level": "test",
    "marks": 100,
    "completion_message": "Congratulations! You have completed the test.",
    "start_instructions": "Please read all questions carefully before answering.",
    "link": "http://example.com/test-link",
    "no_of_attempts": 3,
    "shuffle": True,
    "random_questions": True,
    "no_of_questions": 50,
    "question_pagination": 1,
    "is_template": False,
    "template_id": None,
    "created_by_id": 1,
    "tags": [1, 2, 3],
    "test_question_static": [101, 102, 103],
}
