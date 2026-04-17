from fastapi.testclient import TestClient
from sqlmodel import Session

from app.crud import organization_settings as crud_settings
from app.models.organization_settings import (
    AnswerReviewSetting,
    AnswerReviewValue,
    MarkingSchemeSetting,
    OMRModeSetting,
    OMRModeValue,
    OrganizationSettingsPayload,
    QuestionPaletteSetting,
    QuestionPaletteValue,
    QuestionsPerPageSetting,
    QuestionsPerPageValue,
    TestTimingsSetting,
    TestTimingsValue,
)
from app.models.utils import MarkingScheme
from app.tests.utils.user import get_current_user_data


def flexible_settings_payload() -> OrganizationSettingsPayload:
    """Build an all-flexible settings payload so test-level values pass through."""
    return OrganizationSettingsPayload(
        test_timings=TestTimingsSetting(mode="flexible", value=TestTimingsValue()),
        questions_per_page=QuestionsPerPageSetting(
            mode="flexible", value=QuestionsPerPageValue()
        ),
        marking_scheme=MarkingSchemeSetting(
            mode="flexible",
            value=MarkingScheme(correct=1, wrong=0, skipped=0),
        ),
        answer_review=AnswerReviewSetting(
            mode="flexible", value=AnswerReviewValue(default="off")
        ),
        question_palette=QuestionPaletteSetting(
            mode="flexible",
            value=QuestionPaletteValue(palette=True, mark_for_review=True),
        ),
        omr_mode=OMRModeSetting(mode="flexible", value=OMRModeValue(default=False)),
    )


def make_org_settings_flexible(*, session: Session, organization_id: int) -> None:
    crud_settings.upsert(
        session=session,
        organization_id=organization_id,
        payload=flexible_settings_payload(),
    )


def make_current_user_org_flexible(
    *, client: TestClient, session: Session, auth_header: dict[str, str]
) -> None:
    """Flip the caller's org to all-flexible settings."""
    org_id = get_current_user_data(client, auth_header)["organization_id"]
    make_org_settings_flexible(session=session, organization_id=org_id)
