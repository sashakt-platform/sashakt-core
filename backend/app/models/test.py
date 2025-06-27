import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from app.models import CandidateTest


class MarksLevelEnum(str, enum.Enum):
    QUESTION = "question"
    TEST = "test"


if TYPE_CHECKING:
    from app.models import Candidate, QuestionRevision, State, User
    from app.models.tag import Tag


class TestTag(SQLModel, table=True):
    __tablename__ = "test_tag"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "tag_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE")


class TestQuestion(SQLModel, table=True):
    __tablename__ = "test_question"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "question_revision_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    question_revision_id: int = Field(
        foreign_key="question_revision.id", ondelete="CASCADE"
    )
    question_revision: "QuestionRevision" = Relationship(
        back_populates="test_questions"
    )


class TestState(SQLModel, table=True):
    __tablename__ = "test_state"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "state_id"),)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    state_id: int = Field(foreign_key="state.id", ondelete="CASCADE")


class TestBase(SQLModel):
    name: str = Field(
        index=True,
        title="Test Name",
        description="Name of the test. The same will be shown to the candidate.",
    )
    description: str | None = Field(
        default=None,
        title="Test Description",
        description="Description of the test. The same will be shown to the candidate.",
    )
    start_time: datetime | None = Field(
        default=None,
        title="Start Time of the Test",
        description="The time when the test will be started and can be attempted by the candidate.",
    )
    end_time: datetime | None = Field(
        default=None,
        title="End Time of the Test",
        description="The time when the test will be ended and can not be any more attempted by the candidate.",
    )
    time_limit: int | None = Field(
        default=None,
        title="Time Limit in  Minutes",
        ge=1,
        description="The maximum time allowed for the test in minutes.",
    )
    marks_level: MarksLevelEnum | None = Field(
        default=None,
        title="Marks Level as Question or Test",
        description="Field to set the marks level as question or test. If set to question, then the marks will be calculated as per the question level. If set to test, then the marks will be calculated as per the test level.",
    )
    marks: int | None = Field(
        default=None,
        title="Total Marks of the Test",
        description="Total marks of the test when marks level is set to test.",
    )
    completion_message: str | None = Field(
        default=None,
        title="Completion Message",
        description="Message to be shown to the candidate after the test is completed.",
    )
    start_instructions: str | None = Field(
        default=None,
        title="Start Instructions",
        description="Instructions to be shown to the candidate before starting the test.",
    )
    link: str | None = Field(
        default=None,
        title="Test Link",
        description="Link to the test shared with the candidate. Auto-generated if not provided.",
    )
    no_of_attempts: int | None = Field(
        nullable=False,
        default=1,
        title="No of Attempts of a Test",
        description="No of attempts allowed for the test. If set to 'None', then unlimited attempts are allowed.",
    )
    shuffle: bool = Field(
        default=False,
        title="Shuffle Selected Questions",
        description="Field to set the shuffle of the selected questions. If set to true, then the set questions will be shuffled and displayed to the candidate.",
    )
    random_questions: bool = Field(
        default=False,
        title="Random Questions",
        description="Field to set the random questions. If set to true, then the random questions will be selected from the question bank and displayed to the candidate.",
    )
    no_of_random_questions: int | None = Field(
        default=None,
        title="No of Random Questions",
        description="No of random questions to be selected from the question bank. This field is only applicable when random_questions is set to true.",
    )
    question_pagination: int = Field(
        default=1,
        ge=0,
        title="Question Pagination",
        description="Field to set the question pagination. If set to 1 or more, then the questions will be paginated and displayed to the candidate. If set to 0, then all the questions will be displayed at once.",
    )
    is_template: bool = Field(
        default=False,
        title="Save Test as Template",
        description="Field to set the test as template. If set to true, then the test will be treated as a template and can be used to create other tests.",
    )
    template_id: int | None = Field(
        default=None,
        foreign_key="test.id",
        title="Template ID",
        description="ID of the template from which the test is created.",
    )
    is_active: bool = Field(default=True)


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

    is_deleted: bool = Field(default=False, nullable=False)
    template: Optional["Test"] = Relationship(
        back_populates="tests", sa_relationship_kwargs={"remote_side": "Test.id"}
    )
    tests: list["Test"] | None = Relationship(back_populates="template")
    tags: list["Tag"] | None = Relationship(back_populates="tests", link_model=TestTag)
    question_revisions: list["QuestionRevision"] | None = Relationship(
        back_populates="tests", link_model=TestQuestion
    )
    states: list["State"] | None = Relationship(
        back_populates="tests", link_model=TestState
    )
    created_by: Optional["User"] = Relationship(back_populates="tests")
    candidates: list["Candidate"] | None = Relationship(
        back_populates="tests", link_model=CandidateTest
    )
    created_by_id: int = Field(
        foreign_key="user.id",
        title="User ID",
        description="ID of the user who created the test.",
    )


class TestCreate(TestBase):
    tag_ids: list[int] = []
    question_revision_ids: list[int] = []
    state_ids: list[int] = []


class TestPublic(TestBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_deleted: bool
    tags: list["Tag"]
    question_revisions: list["QuestionRevision"]
    states: list["State"]
    total_questions: int | None = None
    created_by_id: int = Field(
        foreign_key="user.id",
        title="User ID",
        description="ID of the user who created the test.",
    )


class TestUpdate(TestBase):
    tag_ids: list[int] = []
    question_revision_ids: list[int] = []
    state_ids: list[int] = []


class TestPublicLimited(TestBase):
    """Limited public information for test landing page"""

    id: int
    total_questions: int
