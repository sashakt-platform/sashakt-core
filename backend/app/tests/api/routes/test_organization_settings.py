from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.organization import Organization
from app.models.organization_settings import (
    DEFAULT_ORGANIZATION_SETTINGS,
    MAX_NOMENCLATURE_LABEL_LEN,
    NOMENCLATURE_DEFAULTS,
    ORGANIZATION_SETTINGS_SCHEMA_VERSION,
    AnswerReviewSetting,
    AnswerReviewValue,
    MarkForReviewSetting,
    MarkForReviewValue,
    MarkingSchemeSetting,
    OMRModeSetting,
    OMRModeValue,
    OrganizationSettings,
    OrganizationSettingsPayload,
    PlatformNomenclatureSetting,
    PlatformNomenclatureValue,
    QuestionPaletteSetting,
    QuestionPaletteValue,
    QuestionsPerPageSetting,
    QuestionsPerPageValue,
    TestTimingsSetting,
    TestTimingsValue,
    default_organization_settings,
)
from app.models.question import Question, QuestionRevision, QuestionType
from app.models.test import OMRMode, TestQuestion
from app.models.utils import MarkingScheme
from app.services.organization_nomenclature import resolve_all, resolve_label
from app.services.organization_settings_mapper import (
    ANSWER_REVIEW_TO_FEEDBACK_FLAGS,
    check_org_time_window,
    fixed_overrides_for_test,
)
from app.tests.utils.organization_settings import (
    flexible_settings_payload,
    make_current_user_org_flexible,
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
    assert payload.question_palette.value.default is True
    assert payload.mark_for_review.mode == "fixed"
    assert payload.mark_for_review.value.default is True
    assert payload.omr_mode.mode == "fixed"
    assert payload.omr_mode.value.default is False
    assert payload.platform_nomenclature.mode == "default"
    assert all(
        getattr(payload.platform_nomenclature.value, term) == ""
        for term in NOMENCLATURE_DEFAULTS
    )


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
    # state_admin / test_admin / candidate have neither update permission
    # (neither "any org" nor "own org"), so any target yields 403.
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
        assert response.status_code == status.HTTP_403_FORBIDDEN


def test_put_settings_super_admin_uses_any_org_permission(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    get_user_systemadmin_token: dict[str, str],
) -> None:
    """super_admin has update_organization_settings; system_admin does not.

    Confirms the permission split: super can edit another org via the
    'any-org' permission; system_admin is blocked (scope check) since they
    only hold 'update_my_organization_settings'.
    """
    target_org_id = _get_org_id(client, get_user_systemadmin_token)

    sa = client.put(
        f"{settings.API_V1_STR}/organization/{target_org_id}/settings",
        headers=get_user_superadmin_token,
        json=_valid_payload(),
    )
    assert sa.status_code == 200

    sys_other = client.put(
        f"{settings.API_V1_STR}/organization/{_get_org_id(client, get_user_superadmin_token)}/settings",
        headers=get_user_systemadmin_token,
        json=_valid_payload(),
    )
    assert sys_other.status_code == status.HTTP_403_FORBIDDEN


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


def test_put_settings_rejects_start_time_after_end_time(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    bad_payload = default_organization_settings().model_dump(mode="json")
    bad_payload["test_timings"]["value"]["start_time"] = "17:00:00"
    bad_payload["test_timings"]["value"]["end_time"] = "09:00:00"

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": bad_payload},
    )
    assert response.status_code == 422
    assert "start_time must be earlier than end_time" in response.text


def test_put_settings_rejects_equal_start_and_end_time(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    bad_payload = default_organization_settings().model_dump(mode="json")
    bad_payload["test_timings"]["value"]["start_time"] = "12:00:00"
    bad_payload["test_timings"]["value"]["end_time"] = "12:00:00"

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


# ---------- Mapper unit tests ----------


def test_mapper_fixed_features_produce_overrides() -> None:
    payload = OrganizationSettingsPayload(
        test_timings=TestTimingsSetting(
            mode="fixed", value=TestTimingsValue(time_limit=90)
        ),
        questions_per_page=QuestionsPerPageSetting(
            mode="fixed", value=QuestionsPerPageValue(question_pagination=3)
        ),
        marking_scheme=MarkingSchemeSetting(
            mode="fixed",
            value=MarkingScheme(correct=2, wrong=-1, skipped=0),
        ),
        answer_review=AnswerReviewSetting(
            mode="fixed", value=AnswerReviewValue(default="end_of_test")
        ),
        question_palette=QuestionPaletteSetting(
            mode="fixed",
            value=QuestionPaletteValue(default=True),
        ),
        mark_for_review=MarkForReviewSetting(
            mode="fixed", value=MarkForReviewValue(default=False)
        ),
        omr_mode=OMRModeSetting(mode="fixed", value=OMRModeValue(default=True)),
        platform_nomenclature=PlatformNomenclatureSetting(mode="default"),
    )

    overrides = fixed_overrides_for_test(payload)
    assert overrides["time_limit"] == 90
    assert overrides["question_pagination"] == 3
    assert overrides["marking_scheme"] == MarkingScheme(correct=2, wrong=-1, skipped=0)
    assert overrides["show_feedback_immediately"] is False
    assert overrides["show_feedback_on_completion"] is True
    assert overrides["show_question_palette"] is True
    assert overrides["bookmark"] is False
    assert overrides["omr"] == OMRMode.ALWAYS


def test_mapper_flexible_features_produce_no_overrides() -> None:
    overrides = fixed_overrides_for_test(flexible_settings_payload())
    assert overrides == {}


def test_mapper_answer_review_mapping() -> None:
    for option, (
        expected_immediately,
        expected_on_completion,
    ) in ANSWER_REVIEW_TO_FEEDBACK_FLAGS.items():
        payload = default_organization_settings()
        payload.answer_review = AnswerReviewSetting(
            mode="fixed", value=AnswerReviewValue(default=option)
        )
        overrides = fixed_overrides_for_test(payload)
        assert overrides["show_feedback_immediately"] == expected_immediately
        assert overrides["show_feedback_on_completion"] == expected_on_completion


def test_mapper_omr_fixed_false_maps_to_never() -> None:
    payload = default_organization_settings()
    payload.omr_mode = OMRModeSetting(mode="fixed", value=OMRModeValue(default=False))
    overrides = fixed_overrides_for_test(payload)
    assert overrides["omr"] == OMRMode.NEVER


def test_check_org_time_window() -> None:
    tz = ZoneInfo("Asia/Kolkata")
    payload = default_organization_settings()
    payload.test_timings.value.start_time = time(9, 0)
    payload.test_timings.value.end_time = time(17, 0)

    assert (
        check_org_time_window(payload, datetime(2026, 5, 1, 12, 0, tzinfo=tz)) is None
    )
    assert check_org_time_window(payload, datetime(2026, 5, 1, 9, 0, tzinfo=tz)) is None
    assert (
        check_org_time_window(payload, datetime(2026, 5, 1, 17, 0, tzinfo=tz)) is None
    )

    outside = check_org_time_window(payload, datetime(2026, 5, 1, 7, 30, tzinfo=tz))
    assert outside == (time(9, 0), time(17, 0))

    # Unconfigured window (either bound null) → no enforcement
    unconfigured = default_organization_settings()
    unconfigured.test_timings.value.start_time = None
    unconfigured.test_timings.value.end_time = time(17, 0)
    assert (
        check_org_time_window(unconfigured, datetime(2026, 5, 1, 7, 30, tzinfo=tz))
        is None
    )


# ---------- End-to-end: create/update test with org settings ----------


def _create_test_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 15,
        "marks": 5,
        "link": random_lower_string(),
        "is_active": True,
        "question_pagination": 2,
        "show_question_palette": False,
        "bookmark": False,
        "show_feedback_immediately": True,
        "show_feedback_on_completion": False,
        "omr": "OPTIONAL",
    }
    base.update(overrides)
    return base


def _put_settings(
    client: TestClient,
    headers: dict[str, str],
    org_id: int,
    payload: OrganizationSettingsPayload,
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/organization/{org_id}/settings",
        headers=headers,
        json={"settings": payload.model_dump(mode="json")},
    )
    assert response.status_code == 200, response.text


def test_create_test_applies_all_fixed_overrides(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Default org settings are all fixed; client-supplied test fields get overridden."""
    # Materialize a defaults-backed settings row for the superadmin's org
    # (test fixtures create orgs directly in DB, bypassing the auto-init on POST /organization).
    own_org_id = _get_org_id(client, get_user_superadmin_token)
    get_resp = client.get(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_superadmin_token,
    )
    assert get_resp.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=_create_test_payload(),
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["time_limit"] == 60
    assert data["question_pagination"] == 1
    assert data["show_question_palette"] is True
    assert data["bookmark"] is True
    assert data["show_feedback_immediately"] is False
    assert data["show_feedback_on_completion"] is False
    assert data["omr"] == "NEVER"


def test_create_test_flexible_passes_client_values_through(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=_create_test_payload(),
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["time_limit"] == 15
    assert data["question_pagination"] == 2
    assert data["show_question_palette"] is False
    assert data["bookmark"] is False
    assert data["show_feedback_immediately"] is True
    assert data["show_feedback_on_completion"] is False
    assert data["omr"] == "OPTIONAL"


def test_update_test_reapplies_fixed_overrides(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """On update, fixed features still win even if client submits different values."""
    # Start flexible so we can create the test with specific non-default values.
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)

    create_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json=_create_test_payload(),
        headers=get_user_superadmin_token,
    )
    assert create_resp.status_code == 200, create_resp.text
    test_id = create_resp.json()["id"]
    assert create_resp.json()["time_limit"] == 15

    # Lock time_limit via fixed org settings and update the test.
    locked = flexible_settings_payload()
    locked.test_timings.mode = "fixed"
    locked.test_timings.value.time_limit = 120
    _put_settings(client, get_user_superadmin_token, org_id, locked)

    update_payload = _create_test_payload(time_limit=45)
    update_payload["locale"] = "en-US"
    update_resp = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=get_user_superadmin_token,
        json=update_payload,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["time_limit"] == 120


def test_fixed_value_change_does_not_affect_existing_tests(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Changing a fixed org setting only affects *new* tests; existing rows keep their values."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)

    create_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json=_create_test_payload(time_limit=42),
        headers=get_user_superadmin_token,
    )
    test_id = create_resp.json()["id"]
    assert create_resp.json()["time_limit"] == 42

    # Lock test_timings as fixed with a different value; existing test must keep 42.
    new_default = flexible_settings_payload()
    new_default.test_timings.mode = "fixed"
    new_default.test_timings.value.time_limit = 999
    _put_settings(client, get_user_superadmin_token, org_id, new_default)

    get_resp = client.get(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=get_user_superadmin_token,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["time_limit"] == 42


# ---------- Runtime enforcement in candidate flow ----------


def _create_startable_test(
    client: TestClient,
    db: SessionDep,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a test via POST + attach one question so the candidate flow has work to do."""
    body = _create_test_payload() if payload is None else payload
    response = client.post(f"{settings.API_V1_STR}/test/", headers=headers, json=body)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    org_id = data["organization_id"]
    user_id = data["created_by_id"]

    question = Question(organization_id=org_id)
    db.add(question)
    db.flush()
    assert question.id is not None
    revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user_id,
        question_text="dummy",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "x"},
            {"id": 2, "key": "B", "value": "y"},
        ],
        correct_answer=[1],
        is_mandatory=False,
    )
    db.add(revision)
    db.flush()
    assert revision.id is not None
    question.last_revision_id = revision.id
    db.add(TestQuestion(test_id=data["id"], question_revision_id=revision.id))
    db.commit()
    return data


def test_start_test_rejected_outside_time_window(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
    monkeypatch: Any,
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(client, db, get_user_superadmin_token)

    # Configure org time-of-day window 09:00-17:00 (mode is irrelevant).
    window_payload = flexible_settings_payload()
    window_payload.test_timings.value.start_time = time(9, 0)
    window_payload.test_timings.value.end_time = time(17, 0)
    _put_settings(client, get_user_superadmin_token, org_id, window_payload)

    # Freeze current time at 07:30 (outside window).
    frozen = datetime(2026, 5, 1, 7, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    monkeypatch.setattr("app.api.routes.candidate.get_current_time", lambda: frozen)

    response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json={"test_id": test_data["id"], "device_info": "test"},
    )
    assert response.status_code == 400
    assert "09:00" in response.json()["detail"]
    assert "17:00" in response.json()["detail"]


def test_start_test_allowed_inside_time_window(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
    monkeypatch: Any,
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(client, db, get_user_superadmin_token)

    window_payload = flexible_settings_payload()
    window_payload.test_timings.value.start_time = time(9, 0)
    window_payload.test_timings.value.end_time = time(17, 0)
    _put_settings(client, get_user_superadmin_token, org_id, window_payload)

    frozen = datetime(2026, 5, 1, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    monkeypatch.setattr("app.api.routes.candidate.get_current_time", lambda: frozen)

    response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json={"test_id": test_data["id"], "device_info": "test"},
    )
    assert response.status_code == 200, response.text


def test_time_window_skipped_when_not_configured(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Flexible settings with null start/end time: no enforcement."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    test_data = _create_startable_test(client, db, get_user_superadmin_token)

    response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json={"test_id": test_data["id"], "device_info": "test"},
    )
    assert response.status_code == 200, response.text


def _start_and_fetch_candidate_test(client: TestClient, test_id: int) -> dict[str, Any]:
    start_resp = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json={"test_id": test_id, "device_info": "test"},
    )
    assert start_resp.status_code == 200, start_resp.text
    start = start_resp.json()
    response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{start['candidate_test_id']}",
        params={"candidate_uuid": start["candidate_uuid"]},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_runtime_omr_disabled_overrides_existing_test(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """An existing test with omr=ALWAYS must appear as omr=NEVER once org disables OMR."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(omr="ALWAYS"),
    )
    assert test_data["omr"] == "ALWAYS"

    # Now disable OMR at org level.
    disabled = flexible_settings_payload()
    disabled.omr_mode.mode = "fixed"
    disabled.omr_mode.value.default = False
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    body = _start_and_fetch_candidate_test(client, test_data["id"])
    assert body["omr"] == "NEVER"


def test_public_landing_reflects_disabled_feature(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """GET /test/public/{slug} must apply runtime disabled overrides so a
    landing page for an existing test reflects the admin's current config."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(omr="ALWAYS", bookmark=True),
    )
    assert test_data["omr"] == "ALWAYS"
    assert test_data["bookmark"] is True

    # Disable OMR and mark-for-review at org level.
    disabled = flexible_settings_payload()
    disabled.omr_mode.mode = "fixed"
    disabled.omr_mode.value.default = False
    disabled.mark_for_review.mode = "fixed"
    disabled.mark_for_review.value.default = False
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test_data['link']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["omr"] == "NEVER"
    assert body["bookmark"] is False


def test_runtime_question_palette_disabled(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(show_question_palette=True, bookmark=True),
    )
    assert test_data["show_question_palette"] is True
    assert test_data["bookmark"] is True

    # Disabling question_palette must NOT affect bookmark (independent features now).
    disabled = flexible_settings_payload()
    disabled.question_palette.mode = "fixed"
    disabled.question_palette.value.default = False
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    body = _start_and_fetch_candidate_test(client, test_data["id"])
    assert body["show_question_palette"] is False
    assert body["bookmark"] is True


def test_runtime_mark_for_review_disabled(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(show_question_palette=True, bookmark=True),
    )
    assert test_data["bookmark"] is True

    disabled = flexible_settings_payload()
    disabled.mark_for_review.mode = "fixed"
    disabled.mark_for_review.value.default = False
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    body = _start_and_fetch_candidate_test(client, test_data["id"])
    assert body["bookmark"] is False
    # Question palette stays untouched.
    assert body["show_question_palette"] is True


def test_runtime_answer_review_disabled(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(
            show_feedback_immediately=True, show_feedback_on_completion=True
        ),
    )
    assert test_data["show_feedback_immediately"] is True
    assert test_data["show_feedback_on_completion"] is True

    disabled = flexible_settings_payload()
    disabled.answer_review.mode = "fixed"
    disabled.answer_review.value.default = "off"
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    body = _start_and_fetch_candidate_test(client, test_data["id"])
    assert body["show_feedback_immediately"] is False
    assert body["show_feedback_on_completion"] is False


def test_submit_test_honors_disabled_answer_review(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Submitting a test whose test row says feedback-on-completion=True must NOT
    leak answers_with_feedback when the org has answer review fixed-off."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(
            show_feedback_immediately=True, show_feedback_on_completion=True
        ),
    )
    assert test_data["show_feedback_on_completion"] is True

    start_resp = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json={"test_id": test_data["id"], "device_info": "test"},
    )
    assert start_resp.status_code == 200
    start = start_resp.json()

    # Now disable answer review at org level.
    disabled = flexible_settings_payload()
    disabled.answer_review.mode = "fixed"
    disabled.answer_review.value.default = "off"
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    submit_resp = client.post(
        f"{settings.API_V1_STR}/candidate/submit_test/{start['candidate_test_id']}",
        params={"candidate_uuid": start["candidate_uuid"]},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json().get("answers") is None


def test_review_feedback_blocked_when_disabled_by_org(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """GET /review-feedback returns 403 when org has answer review fixed-off,
    even if the test row had the flags enabled."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(
            show_feedback_immediately=True, show_feedback_on_completion=True
        ),
    )

    start_resp = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json={"test_id": test_data["id"], "device_info": "test"},
    )
    start = start_resp.json()

    disabled = flexible_settings_payload()
    disabled.answer_review.mode = "fixed"
    disabled.answer_review.value.default = "off"
    _put_settings(client, get_user_superadmin_token, org_id, disabled)

    # During attempt (end_time=None) → rejected because instant feedback is forced off.
    review_resp = client.get(
        f"{settings.API_V1_STR}/candidate/{start['candidate_test_id']}/review-feedback",
        params={"candidate_uuid": start["candidate_uuid"]},
    )
    assert review_resp.status_code == 403


def test_runtime_fixed_on_does_not_override_existing_test(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Fixed-on (enabling) should NOT force existing tests to the new value — only new tests."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    org_id = _get_org_id(client, get_user_superadmin_token)
    test_data = _create_startable_test(
        client,
        db,
        get_user_superadmin_token,
        payload=_create_test_payload(omr="NEVER"),
    )
    assert test_data["omr"] == "NEVER"

    # Lock OMR on via fixed + default=True — existing test should keep NEVER.
    locked_on = flexible_settings_payload()
    locked_on.omr_mode.mode = "fixed"
    locked_on.omr_mode.value.default = True
    _put_settings(client, get_user_superadmin_token, org_id, locked_on)

    body = _start_and_fetch_candidate_test(client, test_data["id"])
    assert body["omr"] == "NEVER"


# ---------- Platform nomenclature: API round-trip and validation ----------


def test_put_settings_custom_nomenclature_round_trip(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    new_payload = default_organization_settings()
    new_payload.platform_nomenclature = PlatformNomenclatureSetting(
        mode="custom",
        value=PlatformNomenclatureValue(tests="Exams", certificates="Awards"),
    )

    put_resp = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": new_payload.model_dump(mode="json")},
    )
    assert put_resp.status_code == 200, put_resp.text

    get_resp = client.get(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
    )
    assert get_resp.status_code == 200
    nom = get_resp.json()["settings"]["platform_nomenclature"]
    assert nom["mode"] == "custom"
    assert nom["value"]["tests"] == "Exams"
    assert nom["value"]["certificates"] == "Awards"
    # Untouched terms stay empty
    assert nom["value"]["forms"] == ""


def test_put_settings_nomenclature_strips_whitespace(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    payload = default_organization_settings().model_dump(mode="json")
    payload["platform_nomenclature"] = {
        "mode": "custom",
        "value": {"tests": "  Exams  "},
    }

    put_resp = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": payload},
    )
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["settings"]["platform_nomenclature"]["value"]["tests"] == (
        "Exams"
    )


def test_put_settings_nomenclature_label_too_long_returns_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    payload = default_organization_settings().model_dump(mode="json")
    payload["platform_nomenclature"] = {
        "mode": "custom",
        "value": {"tests": "x" * (MAX_NOMENCLATURE_LABEL_LEN + 1)},
    }

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": payload},
    )
    assert response.status_code == 422


def test_put_settings_nomenclature_unknown_key_returns_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    payload = default_organization_settings().model_dump(mode="json")
    payload["platform_nomenclature"] = {
        "mode": "custom",
        "value": {"bogus": "x"},
    }

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": payload},
    )
    assert response.status_code == 422


def test_put_settings_nomenclature_invalid_mode_returns_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    payload = default_organization_settings().model_dump(mode="json")
    payload["platform_nomenclature"] = {"mode": "flexible", "value": {}}

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": payload},
    )
    assert response.status_code == 422


def test_put_settings_version_mismatch_returns_422(
    client: TestClient,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    own_org_id = _get_org_id(client, get_user_systemadmin_token)
    payload = default_organization_settings().model_dump(mode="json")
    payload["version"] = 1

    response = client.put(
        f"{settings.API_V1_STR}/organization/{own_org_id}/settings",
        headers=get_user_systemadmin_token,
        json={"settings": payload},
    )
    assert response.status_code == 422


# ---------- Platform nomenclature: resolver unit tests ----------


def test_resolve_label_default_mode_returns_builtins() -> None:
    payload = default_organization_settings()
    payload.platform_nomenclature = PlatformNomenclatureSetting(
        mode="default",
        value=PlatformNomenclatureValue(tests="Ignored"),
    )
    for term, builtin in NOMENCLATURE_DEFAULTS.items():
        assert resolve_label(payload, term) == builtin


def test_resolve_label_custom_mode_uses_value_when_set() -> None:
    payload = default_organization_settings()
    payload.platform_nomenclature = PlatformNomenclatureSetting(
        mode="custom",
        value=PlatformNomenclatureValue(tests="Exams", forms="Surveys"),
    )
    assert resolve_label(payload, "tests") == "Exams"
    assert resolve_label(payload, "forms") == "Surveys"


def test_resolve_label_custom_mode_empty_falls_back_to_default() -> None:
    payload = default_organization_settings()
    payload.platform_nomenclature = PlatformNomenclatureSetting(
        mode="custom",
        value=PlatformNomenclatureValue(tests="Exams"),
    )
    assert (
        resolve_label(payload, "certificates") == NOMENCLATURE_DEFAULTS["certificates"]
    )


def test_resolve_all_returns_every_tracked_term() -> None:
    payload = default_organization_settings()
    payload.platform_nomenclature = PlatformNomenclatureSetting(
        mode="custom",
        value=PlatformNomenclatureValue(tests="Exams"),
    )
    resolved = resolve_all(payload)
    assert set(resolved.keys()) == set(NOMENCLATURE_DEFAULTS.keys())
    assert resolved["tests"] == "Exams"
    assert resolved["users"] == NOMENCLATURE_DEFAULTS["users"]
