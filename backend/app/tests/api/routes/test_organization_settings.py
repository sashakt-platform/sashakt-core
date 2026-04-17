from datetime import time

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.organization_settings import (
    DEFAULT_ORGANIZATION_SETTINGS,
    ORGANIZATION_SETTINGS_SCHEMA_VERSION,
    OrganizationSettings,
    OrganizationSettingsPayload,
    default_organization_settings,
)
from app.tests.utils.utils import random_lower_string


def test_default_settings_match_schema() -> None:
    """DEFAULT_ORGANIZATION_SETTINGS must validate against the Pydantic schema."""
    payload = OrganizationSettingsPayload.model_validate(DEFAULT_ORGANIZATION_SETTINGS)
    assert payload.version == ORGANIZATION_SETTINGS_SCHEMA_VERSION
    assert payload.test_timings.mode == "fixed"
    assert payload.test_timings.value.start_time == time(9, 0)
    assert payload.test_timings.value.end_time == time(17, 0)
    assert payload.test_timings.value.time_limit == 60
    assert payload.questions_per_page.mode == "fixed"
    assert payload.marking_scheme.mode == "fixed"
    assert payload.answer_review.mode == "fixed"
    assert payload.answer_review.value == "off"
    assert payload.question_palette.mode == "fixed"
    assert payload.question_palette.value.palette is True
    assert payload.question_palette.value.mark_for_review is True
    assert payload.omr_mode.mode == "fixed"
    assert payload.omr_mode.value.default is False


def test_default_settings_factory_is_idempotent() -> None:
    """default_organization_settings() returns an equal payload each call."""
    a = default_organization_settings().model_dump(mode="json")
    b = default_organization_settings().model_dump(mode="json")
    assert a == b == DEFAULT_ORGANIZATION_SETTINGS


def test_create_organization_initializes_settings_row(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    name = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": name, "description": random_lower_string()},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    org_id = response.json()["id"]

    row = db.exec(
        select(OrganizationSettings).where(
            OrganizationSettings.organization_id == org_id
        )
    ).first()
    assert row is not None
    assert row.settings == DEFAULT_ORGANIZATION_SETTINGS
    # Round-trip validates the schema.
    OrganizationSettingsPayload.model_validate(row.settings)
