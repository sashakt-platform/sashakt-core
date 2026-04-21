from datetime import datetime, time
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic import Field as PydanticField
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel
from typing_extensions import Self

from app.core.timezone import get_timezone_aware_now
from app.models.utils import MarkingScheme

if TYPE_CHECKING:
    from app.models.organization import Organization


ORGANIZATION_SETTINGS_SCHEMA_VERSION = 2


NOMENCLATURE_DEFAULTS: dict[str, str] = {
    "dashboard": "Dashboard",
    "question_bank": "Question Bank",
    "test_templates": "Test Templates",
    "tests": "Tests",
    "tag_management": "Tag Management",
    "tags": "Tags",
    "tag_types": "Tag Types",
    "forms": "Forms",
    "certificates": "Certificates",
    "entities": "Entities",
    "users": "Users",
}

MAX_NOMENCLATURE_LABEL_LEN = 50


AnswerReviewOption = Literal[
    "off",
    "after_each_question",
    "end_of_test",
    "after_question_and_after_test",
]


class AnswerReviewValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: AnswerReviewOption = "off"


class TestTimingsValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_limit: int | None = PydanticField(default=None, ge=1)
    start_time: time | None = None
    end_time: time | None = None

    @model_validator(mode="after")
    def _check_window_order(self) -> Self:
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            raise ValueError("start_time must be earlier than end_time")
        return self


class TestTimingsSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: TestTimingsValue = PydanticField(default_factory=TestTimingsValue)


class QuestionsPerPageValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_pagination: int = PydanticField(default=1, ge=0)


class QuestionsPerPageSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: QuestionsPerPageValue = PydanticField(default_factory=QuestionsPerPageValue)


class MarkingSchemeSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: MarkingScheme = PydanticField(
        default_factory=lambda: MarkingScheme(correct=1, wrong=0, skipped=0)
    )


class AnswerReviewSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: AnswerReviewValue = PydanticField(default_factory=AnswerReviewValue)


class QuestionPaletteValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: bool = True


class QuestionPaletteSetting(BaseModel):
    """
    - fixed + value.default=True: palette always on, hidden from test config
    - fixed + value.default=False: palette disabled
    - flexible + value.default: shown in test config with this default
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: QuestionPaletteValue = PydanticField(default_factory=QuestionPaletteValue)


class MarkForReviewValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: bool = True


class MarkForReviewSetting(BaseModel):
    """
    - fixed + value.default=True: mark-for-review always on, hidden from test config
    - fixed + value.default=False: mark-for-review disabled
    - flexible + value.default: shown in test config with this default
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: MarkForReviewValue = PydanticField(default_factory=MarkForReviewValue)


class OMRModeValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: bool = False


class OMRModeSetting(BaseModel):
    """
    - fixed + value.default=True: omr=ALWAYS on every test
    - fixed + value.default=False: omr=NEVER (feature disabled)
    - flexible + value.default: omr=OPTIONAL, default toggle in test form matches `default`
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "flexible"]
    value: OMRModeValue = PydanticField(default_factory=OMRModeValue)


class PlatformNomenclatureValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboard: str = ""
    question_bank: str = ""
    test_templates: str = ""
    tests: str = ""
    tag_management: str = ""
    tags: str = ""
    tag_types: str = ""
    forms: str = ""
    certificates: str = ""
    entities: str = ""
    users: str = ""

    @field_validator("*")
    @classmethod
    def _strip_and_limit(cls, v: str) -> str:
        v = v.strip()
        if len(v) > MAX_NOMENCLATURE_LABEL_LEN:
            raise ValueError(
                f"Label must be {MAX_NOMENCLATURE_LABEL_LEN} characters or fewer"
            )
        return v


class PlatformNomenclatureSetting(BaseModel):
    """
    - mode="default": built-in labels are used everywhere; value is ignored for rendering.
    - mode="custom": per-term value is used; empty string falls back to the built-in default.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["default", "custom"]
    value: PlatformNomenclatureValue = PydanticField(
        default_factory=PlatformNomenclatureValue
    )


class OrganizationSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = ORGANIZATION_SETTINGS_SCHEMA_VERSION
    test_timings: TestTimingsSetting
    questions_per_page: QuestionsPerPageSetting
    marking_scheme: MarkingSchemeSetting
    answer_review: AnswerReviewSetting
    question_palette: QuestionPaletteSetting
    mark_for_review: MarkForReviewSetting
    omr_mode: OMRModeSetting
    platform_nomenclature: PlatformNomenclatureSetting

    @field_validator("version")
    @classmethod
    def _version_matches(cls, v: int) -> int:
        if v != ORGANIZATION_SETTINGS_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported settings version {v}; "
                f"expected {ORGANIZATION_SETTINGS_SCHEMA_VERSION}"
            )
        return v


def default_organization_settings() -> OrganizationSettingsPayload:
    return OrganizationSettingsPayload(
        test_timings=TestTimingsSetting(
            mode="fixed",
            value=TestTimingsValue(
                time_limit=60,
                start_time=time(9, 0),
                end_time=time(17, 0),
            ),
        ),
        questions_per_page=QuestionsPerPageSetting(mode="fixed"),
        marking_scheme=MarkingSchemeSetting(mode="fixed"),
        answer_review=AnswerReviewSetting(
            mode="fixed",
            value=AnswerReviewValue(default="off"),
        ),
        question_palette=QuestionPaletteSetting(
            mode="fixed",
            value=QuestionPaletteValue(default=True),
        ),
        mark_for_review=MarkForReviewSetting(
            mode="fixed",
            value=MarkForReviewValue(default=True),
        ),
        omr_mode=OMRModeSetting(
            mode="fixed",
            value=OMRModeValue(default=False),
        ),
        platform_nomenclature=PlatformNomenclatureSetting(mode="default"),
    )


DEFAULT_ORGANIZATION_SETTINGS: dict[str, Any] = (
    default_organization_settings().model_dump(mode="json")
)


class OrganizationSettingsBase(SQLModel):
    organization_id: int = Field(
        foreign_key="organization.id",
        unique=True,
        index=True,
        description="Organization this settings row belongs to",
    )
    settings: dict[str, Any] = Field(
        sa_type=JSONB,
        description="Validated organization settings payload (see OrganizationSettingsPayload)",
    )


class OrganizationSettings(OrganizationSettingsBase, table=True):
    __tablename__ = "organization_settings"

    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )

    organization: "Organization" = Relationship(back_populates="settings")


class OrganizationSettingsPublic(SQLModel):
    id: int | None
    organization_id: int
    settings: OrganizationSettingsPayload
    created_date: datetime | None
    modified_date: datetime | None


class OrganizationSettingsUpdate(SQLModel):
    settings: OrganizationSettingsPayload
