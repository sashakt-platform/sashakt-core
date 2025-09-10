import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import model_validator
from sqlmodel import JSON, Field, Relationship, SQLModel, UniqueConstraint
from typing_extensions import Self, TypedDict

from app.core.timezone import get_timezone_aware_now
from app.models import CandidateTest
from app.models.utils import MarkingScheme


class MarksLevelEnum(str, enum.Enum):
    QUESTION = "question"
    TEST = "test"


if TYPE_CHECKING:
    from app.models import (
        Candidate,
        District,
        QuestionRevision,
        State,
        Tag,
        TagPublic,
        User,
    )


class TagRandomCreate(TypedDict):
    tag_id: int
    count: int


class TagRandomPublic(SQLModel):
    tag: "TagPublic"
    count: int


class TestTag(SQLModel, table=True):
    __tablename__ = "test_tag"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "tag_id"),)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE")


class TestQuestion(SQLModel, table=True):
    __tablename__ = "test_question"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "question_revision_id"),)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
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
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    state_id: int = Field(foreign_key="state.id", ondelete="CASCADE")


class TestDistrict(SQLModel, table=True):
    __tablename__ = "test_district"
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    __table_args__ = (UniqueConstraint("test_id", "district_id"),)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    district_id: int = Field(foreign_key="district.id", ondelete="CASCADE")


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
        default=MarksLevelEnum.QUESTION,
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
    show_result: bool = Field(
        default=True,
        sa_column_kwargs={"server_default": "true"},
        description="Whether result should be visible after test submission",
    )
    is_active: bool = Field(default=True)
    marking_scheme: MarkingScheme | None = Field(
        default=None,
        sa_type=JSON,
        description="Scoring rules for this test",
    )
    candidate_profile: bool = Field(
        default=False,
        title="Candidate Profile",
        description="Field to set whether candidate profile is to be filled before the test or not.",
        sa_column_kwargs={"server_default": "false"},
    )


class Test(TestBase, table=True):
    __test__ = False
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
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
    districts: list["District"] | None = Relationship(
        back_populates="tests", link_model=TestDistrict
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
    random_tag_count: list[TagRandomCreate] | None = Field(
        sa_type=JSON,
        default=None,
        title="Tag-based Randomization Configuration",
        description="Specifies how many random questions to select for each tag. Each item includes a tag ID and the count of random questions to select from that tag.",
    )


class TestCreate(TestBase):
    tag_ids: list[int] = []
    question_revision_ids: list[int] = []
    state_ids: list[int] = []
    district_ids: list[int] = []
    random_tag_count: list[TagRandomCreate] | None = None

    @model_validator(mode="after")
    def check_link_for_template(self) -> Self:
        if self.is_template and self.link:
            raise ValueError("Templates should not have a link.")
        return self


class TestPublic(TestBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_deleted: bool
    tags: list["Tag"]
    question_revisions: list["QuestionRevision"]
    states: list["State"]
    districts: list["District"]
    total_questions: int | None = None
    random_tag_counts: list[TagRandomPublic] | None = None
    created_by_id: int = Field(
        foreign_key="user.id",
        title="User ID",
        description="ID of the user who created the test.",
    )


class TestUpdate(TestBase):
    tag_ids: list[int] = []
    question_revision_ids: list[int] = []
    state_ids: list[int] = []
    district_ids: list[int] = []
    random_tag_count: list[TagRandomCreate] | None = None


class EntityPublicLimited(SQLModel):
    id: int
    name: str


class TestPublicLimited(TestBase):
    """Limited public information for test landing page"""

    id: int
    total_questions: int
    profile_list: list["EntityPublicLimited"] | None = None
