from datetime import time
from typing import Any

from fastapi import status
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
from app.tests.utils.user import get_current_user_data
from app.tests.utils.utils import random_lower_string


def _get_org_id(client: TestClient, headers: dict[str, str]) -> int:
    data = get_current_user_data(client, headers)
    org_id = data.get("organization_id")
    assert isinstance(org_id, int)
    return org_id


def _valid_payload() -> dict[str, Any]:
    return {"settings": default_organization_settings().model_dump(mode="json")}


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
    assert payload.answer_review.value.default == "off"
    assert payload.question_palette.mode == "fixed"
    assert payload.question_palette.value.palette is True
    assert payload.question_palette.value.mark_for_review is True
    assert payload.omr_mode.mode == "fixed"
    assert payload.omr_mode.value.default is False


def test_default_settings_factory_is_idempotent() -> None:
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
    OrganizationSettingsPayload.model_validate(row.settings)


# ---------- GET /organization/{id}/settings ----------


def test_get_settings_super_admin_any_org(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    get_user_systemadmin_token: dict[str, str],
) -> None:
    target_org_id = _get_org_id(client, get_user_systemadmin_token)

    response = client.get(
        f"{settings.API_V1_STR}/organization/{target_org_id}/settings",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == target_org_id
    assert body["settings"]["version"] == ORGANIZATION_SETTINGS_SCHEMA_VERSION


def test_get_settings_returns_defaults_when_row_missing(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """get_or_create: settings row is lazily created with defaults if missing."""
    from app.models.organization import Organization

    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    response = client.get(
        f"{settings.API_V1_STR}/organization/{org.id}/settings",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    assert response.json()["settings"] == DEFAULT_ORGANIZATION_SETTINGS


def test_get_settings_system_admin_own_org(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    response = client.get(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
    )
    assert response.status_code == 200


def test_get_settings_system_admin_other_org_forbidden(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
    get_user_superadmin_token: dict[str, str],
) -> None:
    other_org_id = _get_org_id(client, get_user_superadmin_token)
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    assert other_org_id != own_org_id

    response = client.get(
        f"{settings.API_V1_STR}/organization/{other_org_id}/settings",
        headers=get_user_systemadmin_token,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_settings_candidate_cannot_read_other_org(
    client: TestClient,
    get_user_candidate_token: dict[str, str],
    get_user_superadmin_token: dict[str, str],
) -> None:
    # Candidate has read_organization permission but scope check blocks other orgs.
    other_org_id = _get_org_id(client, get_user_superadmin_token)
    response = client.get(
        f"{settings.API_V1_STR}/organization/{other_org_id}/settings",
        headers=get_user_candidate_token,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_settings_nonexistent_org_404(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/organization/999999999/settings",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404


# ---------- PUT /organization/{id}/settings ----------


def test_put_settings_super_admin_any_org(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    get_user_systemadmin_token: dict[str, str],
) -> None:
    target_org_id = _get_org_id(client, get_user_systemadmin_token)

    new_payload = default_organization_settings()
    new_payload.test_timings.value.time_limit = 45
    body = {"settings": new_payload.model_dump(mode="json")}

    response = client.put(
        f"{settings.API_V1_STR}/organization/{target_org_id}/settings",
        headers=get_user_superadmin_token,
        json=body,
    )
    assert response.status_code == 200
    assert response.json()["settings"]["test_timings"]["value"]["time_limit"] == 45


def test_put_settings_persists_round_trip(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    new_payload = default_organization_settings()
    new_payload.questions_per_page.mode = "flexible"
    new_payload.questions_per_page.value.question_pagination = 5
    new_payload.answer_review.value.default = "end_of_test"

    put_resp = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": new_payload.model_dump(mode="json")},
    )
    assert put_resp.status_code == 200

    get_resp = client.get(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
    )
    assert get_resp.status_code == 200
    settings_body = get_resp.json()["settings"]
    assert settings_body["questions_per_page"]["mode"] == "flexible"
    assert settings_body["questions_per_page"]["value"]["question_pagination"] == 5
    assert settings_body["answer_review"]["value"]["default"] == "end_of_test"


def test_put_settings_system_admin_other_org_forbidden(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
    get_user_superadmin_token: dict[str, str],
) -> None:
    other_org_id = _get_org_id(client, get_user_superadmin_token)
    response = client.put(
        f"{settings.API_V1_STR}/organization/{other_org_id}/settings",
        headers=get_user_systemadmin_token,
        json=_valid_payload(),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_put_settings_forbidden_for_low_privilege_roles(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    get_user_stateadmin_token: dict[str, str],
    get_user_testadmin_token: dict[str, str],
    get_user_candidate_token: dict[str, str],
) -> None:
    # state_admin / test_admin / candidate all lack update_organization_settings.
    # Target any org; permission check fires before scope check.
    target_org_id = _get_org_id(client, get_user_superadmin_token)
    for headers in (
        get_user_stateadmin_token,
        get_user_testadmin_token,
        get_user_candidate_token,
    ):
        response = client.put(
            f"{settings.API_V1_STR}/organization/{target_org_id}/settings",
            headers=headers,
            json=_valid_payload(),
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_put_settings_invalid_mode_returns_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    bad_payload = default_organization_settings().model_dump(mode="json")
    bad_payload["test_timings"]["mode"] = "disabled"  # not a valid mode anymore

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": bad_payload},
    )
    assert response.status_code == 422


def test_put_settings_invalid_answer_review_value_returns_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    bad_payload = default_organization_settings().model_dump(mode="json")
    bad_payload["answer_review"]["value"]["default"] = "not_a_real_option"

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": bad_payload},
    )
    assert response.status_code == 422


def test_put_settings_extra_field_rejected_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    bad_payload = default_organization_settings().model_dump(mode="json")
    bad_payload["unknown_feature"] = {"mode": "fixed"}

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": bad_payload},
    )
    assert response.status_code == 422
