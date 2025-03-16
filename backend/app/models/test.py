import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


class MarksLevelEnum(str, enum.Enum):
    QUESTION = "question"
    TEST = "test"


if TYPE_CHECKING:
    from app.models.location import State
    from app.models.question import Question
    from app.models.tag import Tag
    from app.models.user import User


class TestTag(SQLModel, table=True):
    __tablename__ = "test_tag"  # type: ignore
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "tag_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE")


class TestQuestion(SQLModel, table=True):
    __tablename__ = "test_question"  # type: ignore
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "question_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int | None = Field(default=None, foreign_key="test.id")
    question_id: int | None = Field(default=None, foreign_key="question.id")


class TestState(SQLModel, table=True):
    __tablename__ = "test_state"  # type: ignore
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "state_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int | None = Field(default=None, foreign_key="test.id")
    state_id: int | None = Field(default=None, foreign_key="state.id")


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
    tags: list["Tag"] | None = Relationship(back_populates="tests", link_model=TestTag)
    test_question_static: list["Question"] | None = Relationship(
        back_populates="tests", link_model=TestQuestion
    )
    states: list["State"] | None = Relationship(
        back_populates="tests", link_model=TestState
    )
    created_by: Optional["User"] = Relationship(back_populates="tests")


class TestCreate(TestBase):
    tags: list[int] = []
    test_question_static: list[int] = []
    states: list[int] = []


class TestPublic(TestBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool
    tags: list[int]
    test_question_static: list[int]
    states: list[int]


class TestUpdate(TestBase):
    tags: list[int] = []
    test_question_static: list[int] = []
    states: list[int] = []
