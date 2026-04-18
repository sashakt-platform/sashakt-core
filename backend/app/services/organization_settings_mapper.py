from datetime import datetime, time
from typing import Any

from sqlmodel import Session

from app.crud import organization_settings as crud_settings
from app.models.organization_settings import (
    AnswerReviewOption,
    OrganizationSettingsPayload,
)
from app.models.test import OMRMode, Test

ANSWER_REVIEW_TO_FEEDBACK_FLAGS: dict[AnswerReviewOption, tuple[bool, bool]] = {
    "off": (False, False),
    "after_each_question": (True, False),
    "end_of_test": (False, True),
    "after_question_and_after_test": (True, True),
}


def fixed_overrides_for_test(
    settings: OrganizationSettingsPayload,
) -> dict[str, Any]:
    """Return Test-row fields to overwrite based on the org's fixed features.

    Flexible features return nothing; the client's payload is used as-is.
    """
    overrides: dict[str, Any] = {}

    if settings.test_timings.mode == "fixed":
        overrides["time_limit"] = settings.test_timings.value.time_limit

    if settings.questions_per_page.mode == "fixed":
        overrides["question_pagination"] = (
            settings.questions_per_page.value.question_pagination
        )

    if settings.marking_scheme.mode == "fixed":
        overrides["marking_scheme"] = settings.marking_scheme.value

    if settings.answer_review.mode == "fixed":
        immediately, on_completion = ANSWER_REVIEW_TO_FEEDBACK_FLAGS[
            settings.answer_review.value.default
        ]
        overrides["show_feedback_immediately"] = immediately
        overrides["show_feedback_on_completion"] = on_completion

    if settings.question_palette.mode == "fixed":
        overrides["show_question_palette"] = settings.question_palette.value.palette
        overrides["bookmark"] = settings.question_palette.value.mark_for_review

    if settings.omr_mode.mode == "fixed":
        overrides["omr"] = (
            OMRMode.ALWAYS if settings.omr_mode.value.default else OMRMode.NEVER
        )

    return overrides


def check_org_time_window(
    settings: OrganizationSettingsPayload, current_time: datetime
) -> tuple[time, time] | None:
    """Return the (start, end) bounds when current_time falls outside the org's
    time-of-day window. Returns None if the window is unconfigured or current
    time is inside the window.
    """
    window_start = settings.test_timings.value.start_time
    window_end = settings.test_timings.value.end_time
    if window_start is None or window_end is None:
        return None
    now_time = current_time.time()
    if window_start <= now_time <= window_end:
        return None
    return (window_start, window_end)


def get_effective_test_flags(session: Session, test: Test) -> dict[str, Any]:
    """Return `test.model_dump()` merged with the org's runtime disabled-feature
    overrides.

    Use this anywhere a candidate-facing decision depends on feature flags
    (`show_feedback_*`, `omr`, `show_question_palette`, `bookmark`) so that an
    org's decision to turn a feature off is honoured regardless of the test row.
    """
    test_data: dict[str, Any] = test.model_dump()
    if test.organization_id is None:
        return test_data
    settings_payload = crud_settings.get_payload(
        session=session, organization_id=test.organization_id
    )
    if settings_payload is None:
        return test_data
    test_data.update(runtime_disabled_overrides(settings_payload))
    return test_data


def runtime_disabled_overrides(
    settings: OrganizationSettingsPayload,
) -> dict[str, Any]:
    """Return Test-row fields to force off when a feature is fixed-off at org level.

    Applied at candidate read time so that existing tests also honour a
    feature that the org admin has since turned off. Fixed-on or flexible
    features produce no overrides here (those apply only to new tests at
    creation).
    """
    overrides: dict[str, Any] = {}

    if settings.omr_mode.mode == "fixed" and settings.omr_mode.value.default is False:
        overrides["omr"] = OMRMode.NEVER

    if settings.question_palette.mode == "fixed":
        if settings.question_palette.value.palette is False:
            overrides["show_question_palette"] = False
        if settings.question_palette.value.mark_for_review is False:
            overrides["bookmark"] = False

    if (
        settings.answer_review.mode == "fixed"
        and settings.answer_review.value.default == "off"
    ):
        overrides["show_feedback_immediately"] = False
        overrides["show_feedback_on_completion"] = False

    return overrides
