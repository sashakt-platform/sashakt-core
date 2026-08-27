import csv
import io
import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.api.routes.test import (
    CANDIDATE_REPORT_CSV_HEADERS,
    candidate_report_to_csv_row,
)
from app.core.config import settings
from app.models import TestQuestion
from app.models.candidate import (
    CandidateReport,
    CandidateReportStatus,
    CandidateTestAnswer,
    Result,
)
from app.models.certificate import Certificate
from app.models.form import Form, FormField, FormFieldType, FormResponse
from app.tests.utils.candidate import (
    create_test_candidate,
    create_test_candidate_test,
    create_test_record,
)
from app.tests.utils.form import create_form, create_form_response
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user, get_org_user
from app.tests.utils.utils import random_lower_string


def test_candidate_report_submitted(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1

    entry = data["items"][0]
    assert entry["candidate_uuid"] == str(candidate.identity)
    assert entry["candidate_test_id"] == candidate_test.id
    assert entry["status"] == "submitted"
    assert entry["result"]["marks_obtained"] == 10.0
    assert entry["start_time"] == "2026-06-10T10:00:00"
    assert entry["end_time"] == "2026-06-10T10:32:00"
    assert entry["time_taken_seconds"] == 1920


def test_candidate_report_total_marks_test_level(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    revision_one = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 5, "wrong": 0, "skipped": 0},
    )
    revision_two = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 5, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="test",
    )
    test.marking_scheme = {"correct": 10, "wrong": 0, "skipped": 0}
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_one.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_two.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision_one.id, revision_two.id],
        is_submitted=True,
        end_time="2026-06-10T10:30:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision_one.id,
            response="[1]",
            visited=True,
        )
    )
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision_two.id,
            response="[2]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1

    entry = data["items"][0]
    assert entry["candidate_uuid"] == str(candidate.identity)
    assert entry["result"]["marks_obtained"] == 10.0
    assert entry["start_time"] == "2026-06-10T10:00:00"
    assert entry["end_time"] == "2026-06-10T10:30:00"
    assert entry["time_taken_seconds"] == 1800


def test_candidate_report_total_marks_question_level(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    revision_one = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )
    revision_two = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 5, "wrong": 0, "skipped": 0},
    )
    revision_three = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 2, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_one.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_two.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_three.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision_one.id, revision_two.id, revision_three.id],
        is_submitted=True,
        end_time="2026-06-10T10:25:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision_one.id,
            response="[1]",
            visited=True,
        )
    )
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision_two.id,
            response="[1]",
            visited=True,
        )
    )
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision_three.id,
            response="[2]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1

    entry = data["items"][0]
    assert entry["candidate_uuid"] == str(candidate.identity)
    assert entry["result"]["marks_obtained"] == 15.0
    assert entry["start_time"] == "2026-06-10T10:00:00"
    assert entry["end_time"] == "2026-06-10T10:25:00"
    assert entry["time_taken_seconds"] == 1500


def test_candidate_report_submitted_and_in_progress(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    submitted_candidate = create_test_candidate(
        db, organization_id=user.organization_id
    )
    submitted_candidate.identity = uuid.uuid4()
    db.add(submitted_candidate)
    db.commit()
    db.refresh(submitted_candidate)

    submitted_ct = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=submitted_candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:20:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=submitted_ct.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    in_progress_candidate = create_test_candidate(
        db, organization_id=user.organization_id
    )
    in_progress_candidate.identity = uuid.uuid4()
    db.add(in_progress_candidate)
    db.commit()
    db.refresh(in_progress_candidate)

    create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=in_progress_candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=False,
        end_time=None,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2

    entries_by_uuid = {e["candidate_uuid"]: e for e in data["items"]}

    submitted_entry = entries_by_uuid[str(submitted_candidate.identity)]
    assert submitted_entry["status"] == "submitted"
    assert submitted_entry["result"]["marks_obtained"] == 10.0
    assert submitted_entry["start_time"] == "2026-06-10T10:00:00"
    assert submitted_entry["end_time"] == "2026-06-10T10:20:00"
    assert submitted_entry["time_taken_seconds"] == 1200

    in_progress_entry = entries_by_uuid[str(in_progress_candidate.identity)]
    assert in_progress_entry["status"] == "not_submitted"
    assert in_progress_entry["result"] is None
    assert in_progress_entry["start_time"] == "2026-06-10T10:00:00"
    assert in_progress_entry["end_time"] is None
    assert in_progress_entry["time_taken_seconds"] is None


def test_candidate_report_null_end_time(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=False,
        end_time=None,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1

    entry = data["items"][0]
    assert entry["candidate_uuid"] == str(candidate.identity)
    assert entry["end_time"] is None
    assert entry["time_taken_seconds"] is None


def test_candidate_report_different_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    other_user = create_random_user(db)

    test = create_test_record(
        db,
        user_id=other_user.id,
        organization_id=other_user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access this test"


def test_candidate_report_not_found(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    _ = db
    response = client.get(
        f"{settings.API_V1_STR}/test/-999999/candidate-report",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404


def test_candidate_report_empty(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


def test_candidate_report_accessible_by_test_admin(
    client: TestClient,
    db: SessionDep,
    get_user_testadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_testadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_testadmin_token,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_candidate_report_accessible_by_state_admin(
    client: TestClient,
    db: SessionDep,
    get_user_stateadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_stateadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_stateadmin_token,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_candidate_report_sort_by_start_time(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    for start_time in (
        "2026-06-10T11:00:00",
        "2026-06-10T09:00:00",
        "2026-06-10T10:00:00",
    ):
        candidate = create_test_candidate(db, organization_id=user.organization_id)
        candidate.identity = uuid.uuid4()
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        create_test_candidate_test(
            db,
            admin_id=user.id,
            test_id=test.id,
            candidate_id=candidate.id,
            start_time=start_time,
        )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"sort_by": "start_time", "sort_order": "asc"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["start_time"] for item in items] == [
        "2026-06-10T09:00:00",
        "2026-06-10T10:00:00",
        "2026-06-10T11:00:00",
    ]

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"sort_by": "start_time", "sort_order": "desc"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["start_time"] for item in items] == [
        "2026-06-10T11:00:00",
        "2026-06-10T10:00:00",
        "2026-06-10T09:00:00",
    ]


def test_candidate_report_sort_by_status(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    submitted_candidate = create_test_candidate(
        db, organization_id=user.organization_id
    )
    submitted_candidate.identity = uuid.uuid4()
    db.add(submitted_candidate)
    db.commit()
    db.refresh(submitted_candidate)
    create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=submitted_candidate.id,
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )

    not_submitted_candidate = create_test_candidate(
        db, organization_id=user.organization_id
    )
    not_submitted_candidate.identity = uuid.uuid4()
    db.add(not_submitted_candidate)
    db.commit()
    db.refresh(not_submitted_candidate)
    create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=not_submitted_candidate.id,
        is_submitted=False,
        end_time=None,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"sort_by": "status", "sort_order": "asc"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["status"] for item in items] == ["not_submitted", "submitted"]

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"sort_by": "status", "sort_order": "desc"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["status"] for item in items] == ["submitted", "not_submitted"]


def test_candidate_report_search_matches_form_response(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    alice = create_test_candidate(db, organization_id=user.organization_id)
    alice.identity = uuid.uuid4()
    db.add(alice)
    db.commit()
    db.refresh(alice)
    alice_ct = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=alice.id
    )
    create_form_response(
        db,
        candidate_test=alice_ct,
        form=form,
        responses={"full_name": "Alice Johnson"},
    )

    bob = create_test_candidate(db, organization_id=user.organization_id)
    bob.identity = uuid.uuid4()
    db.add(bob)
    db.commit()
    db.refresh(bob)
    bob_ct = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=bob.id
    )
    create_form_response(
        db, candidate_test=bob_ct, form=form, responses={"full_name": "Bob Smith"}
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "johnson"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_uuid"] == str(alice.identity)


def test_candidate_report_search_is_case_insensitive_and_trims_whitespace(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    candidate_test = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=candidate.id
    )
    create_form_response(
        db,
        candidate_test=candidate_test,
        form=form,
        responses={"full_name": "Alice Johnson"},
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "  ALICE  "},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_uuid"] == str(candidate.identity)


def test_candidate_report_search_matches_any_field_value(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """The search should scan every key in the form response, not just one field."""
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    candidate_test = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=candidate.id
    )
    create_form_response(
        db,
        candidate_test=candidate_test,
        form=form,
        responses={"full_name": "Alice Johnson", "email": "alice@example.com"},
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "example.com"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_uuid"] == str(candidate.identity)


def test_candidate_report_search_no_match_returns_empty(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    candidate_test = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=candidate.id
    )
    create_form_response(
        db,
        candidate_test=candidate_test,
        form=form,
        responses={"full_name": "Alice Johnson"},
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "nonexistent-name"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_candidate_report_blank_search_returns_all_candidates(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """An empty search string is falsy and must behave like no search at all,
    including candidates that never submitted any form response."""
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=candidate.id
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": ""},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_uuid"] == str(candidate.identity)


def test_candidate_report_whitespace_only_search_requires_form_response(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """A whitespace-only search is truthy (unlike ""), so it takes the search
    branch; the stripped term is "" which matches any response value, but the
    EXISTS join still requires a form_response row to be present. Candidates
    with no form response at all must therefore be excluded."""
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    with_response = create_test_candidate(db, organization_id=user.organization_id)
    with_response.identity = uuid.uuid4()
    db.add(with_response)
    db.commit()
    db.refresh(with_response)
    with_response_ct = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=with_response.id
    )
    create_form_response(
        db,
        candidate_test=with_response_ct,
        form=form,
        responses={"full_name": "Alice Johnson"},
    )

    without_response = create_test_candidate(db, organization_id=user.organization_id)
    without_response.identity = uuid.uuid4()
    db.add(without_response)
    db.commit()
    db.refresh(without_response)
    create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=without_response.id
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "   "},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_uuid"] == str(with_response.identity)


def test_candidate_report_search_escapes_like_wildcards(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """`%` and `_` are SQL LIKE wildcards; the endpoint passes autoescape=True
    so they must be treated as literal characters in the search term."""
    user = get_org_user(client, db, get_user_superadmin_token)
    form = create_form(db, organization_id=user.organization_id, created_by_id=user.id)
    test = create_test_record(
        db, user_id=user.id, organization_id=user.organization_id, form_id=form.id
    )

    percent_candidate = create_test_candidate(db, organization_id=user.organization_id)
    percent_candidate.identity = uuid.uuid4()
    db.add(percent_candidate)
    db.commit()
    db.refresh(percent_candidate)
    percent_ct = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=percent_candidate.id
    )
    create_form_response(
        db,
        candidate_test=percent_ct,
        form=form,
        responses={"score": "100%"},
    )

    plain_candidate = create_test_candidate(db, organization_id=user.organization_id)
    plain_candidate.identity = uuid.uuid4()
    db.add(plain_candidate)
    db.commit()
    db.refresh(plain_candidate)
    plain_ct = create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=plain_candidate.id
    )
    create_form_response(
        db,
        candidate_test=plain_ct,
        form=form,
        responses={"score": "1000"},
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "100%"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["candidate_uuid"] == str(percent_candidate.identity)

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "100_"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_candidate_report_search_without_form_returns_empty(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """A test with no associated form (form_id is None) has no form responses
    to search; a search term should filter everything out rather than error."""
    user = get_org_user(client, db, get_user_superadmin_token)
    test = create_test_record(db, user_id=user.id, organization_id=user.organization_id)

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    create_test_candidate_test(
        db, admin_id=user.id, test_id=test.id, candidate_id=candidate.id
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"search": "alice"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_candidate_report_sort_by_invalid_field(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
        params={"sort_by": "not_a_field"},
    )

    assert response.status_code == 400


def test_candidate_report_certificate_download_url_present(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Report includes a certificate_download_url for a submitted candidate when the
    test has a certificate assigned, and persists the certificate data snapshot."""
    user = get_org_user(client, db, get_user_superadmin_token)

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )
    test.certificate_id = certificate.id
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1

    entry = data["items"][0]
    assert entry["result"]["certificate_download_url"] is not None
    assert entry["result"]["certificate_download_url"].startswith(
        "/api/v1/certificate/download/"
    )

    db.refresh(candidate_test)
    assert candidate_test.certificate_data is not None
    assert candidate_test.certificate_data.get("token") is not None


def test_candidate_report_certificate_download_url_none_without_certificate(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Report has certificate_download_url=None when the test has no certificate."""
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    entry = response.json()["items"][0]
    assert entry["result"]["certificate_download_url"] is None

    db.refresh(candidate_test)
    assert candidate_test.certificate_data is None


def test_candidate_report_certificate_token_reused_across_calls(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Calling the report endpoint twice returns the same certificate token/url
    instead of regenerating it each time."""
    user = get_org_user(client, db, get_user_superadmin_token)

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )
    test.certificate_id = certificate.id
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    first_response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )
    second_response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_url = first_response.json()["items"][0]["result"]["certificate_download_url"]
    second_url = second_response.json()["items"][0]["result"][
        "certificate_download_url"
    ]

    assert first_url is not None
    assert first_url == second_url


def test_candidate_report_certificate_generated_independently_per_candidate(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Each candidate in the same report page gets its own distinct certificate
    token, and both are persisted."""
    user = get_org_user(client, db, get_user_superadmin_token)

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )
    test.certificate_id = certificate.id
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate_tests = []
    for _ in range(2):
        candidate = create_test_candidate(db, organization_id=user.organization_id)
        candidate.identity = uuid.uuid4()
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        candidate_test = create_test_candidate_test(
            db,
            admin_id=user.id,
            test_id=test.id,
            candidate_id=candidate.id,
            question_revision_ids=[revision.id],
            is_submitted=True,
            end_time="2026-06-10T10:32:00",
        )
        db.add(
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revision.id,
                response="[1]",
                visited=True,
            )
        )
        db.commit()
        candidate_tests.append(candidate_test)

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2

    urls = {item["result"]["certificate_download_url"] for item in items}
    assert len(urls) == 2
    assert all(url is not None for url in urls)

    for candidate_test in candidate_tests:
        db.refresh(candidate_test)
        assert candidate_test.certificate_data is not None
        assert candidate_test.certificate_data.get("token") is not None


def test_candidate_report_certificate_token_matches_single_result_endpoint(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """A certificate token generated via the single-candidate result endpoint is
    reused (not regenerated) by the bulk candidate-report endpoint."""
    user = get_org_user(client, db, get_user_superadmin_token)

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )
    test.certificate_id = certificate.id
    test.show_result = True
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    result_response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        params={"candidate_uuid": str(candidate.identity)},
    )
    assert result_response.status_code == 200
    single_url = result_response.json()["certificate_download_url"]
    assert single_url is not None

    report_response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )
    assert report_response.status_code == 200
    report_url = report_response.json()["items"][0]["result"][
        "certificate_download_url"
    ]

    assert report_url == single_url


def test_candidate_report_includes_form_response(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Report includes resolved form_response values for a candidate that has
    submitted a form response, even when the candidate has not finished the test."""
    user = get_org_user(client, db, get_user_superadmin_token)

    form = Form(
        name=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    field = FormField(
        form_id=form.id,
        field_type=FormFieldType.TEXT,
        label="Full Name",
        name="full_name",
        order=0,
    )
    db.add(field)
    db.commit()
    db.refresh(field)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        form_id=form.id,
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        is_submitted=False,
        end_time=None,
    )

    db.add(
        FormResponse(
            candidate_test_id=candidate_test.id,
            form_id=form.id,
            responses={"full_name": "Jane Doe"},
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    entry = response.json()["items"][0]
    assert entry["status"] == "not_submitted"
    assert entry["result"] is None
    assert entry["form_response"] == {"full_name": "Jane Doe"}


def test_candidate_report_form_response_none_without_submission(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Report has form_response=None when the test has a form but the candidate
    has not submitted any form response."""
    user = get_org_user(client, db, get_user_superadmin_token)

    form = Form(
        name=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        form_id=form.id,
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        is_submitted=False,
        end_time=None,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    entry = response.json()["items"][0]
    assert entry["form_response"] is None


def test_candidate_report_form_response_none_when_test_has_no_form(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Report has form_response=None when the test has no form configured."""
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    entry = response.json()["items"][0]
    assert entry["form_response"] is None


def test_candidate_report_export_submitted(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert (
        f'filename="{test.name}-responses.csv"'
        in response.headers["content-disposition"]
    )

    reader = csv.DictReader(io.StringIO(response.text))
    assert reader.fieldnames == [
        "Candidate UUID",
        "Status",
        "Marks Obtained",
        "Marks Maximum",
        "Correct Answers",
        "Incorrect Answers",
        "Mandatory Not Attempted",
        "Optional Not Attempted",
        "Total Questions",
        "Start Time",
        "End Time",
        "Time Taken (seconds)",
        "Form Response",
    ]
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["Candidate UUID"] == str(candidate.identity)
    assert row["Status"] == "submitted"
    assert row["Marks Obtained"] == "10.0"
    assert row["Start Time"] == "2026-06-10T10:00:00"
    assert row["End Time"] == "2026-06-10T10:32:00"
    assert row["Time Taken (seconds)"] == "1920"
    assert row["Form Response"] == ""


def test_candidate_report_export_different_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    other_user = create_random_user(db)

    test = create_test_record(
        db,
        user_id=other_user.id,
        organization_id=other_user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access this test"


def test_candidate_report_export_not_found(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    _ = db
    response = client.get(
        f"{settings.API_V1_STR}/test/-999999/candidate-report/export",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404


def test_candidate_report_export_empty(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    reader = csv.DictReader(io.StringIO(response.text))
    assert reader.fieldnames == [
        "Candidate UUID",
        "Status",
        "Marks Obtained",
        "Marks Maximum",
        "Correct Answers",
        "Incorrect Answers",
        "Mandatory Not Attempted",
        "Optional Not Attempted",
        "Total Questions",
        "Start Time",
        "End Time",
        "Time Taken (seconds)",
        "Form Response",
    ]
    assert list(reader) == []


def test_candidate_report_export_sort_by_start_time(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    for start_time in (
        "2026-06-10T11:00:00",
        "2026-06-10T09:00:00",
        "2026-06-10T10:00:00",
    ):
        candidate = create_test_candidate(db, organization_id=user.organization_id)
        candidate.identity = uuid.uuid4()
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        create_test_candidate_test(
            db,
            admin_id=user.id,
            test_id=test.id,
            candidate_id=candidate.id,
            start_time=start_time,
        )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
        params={"sort_by": "start_time", "sort_order": "asc"},
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["Start Time"] for row in rows] == [
        "2026-06-10T09:00:00",
        "2026-06-10T10:00:00",
        "2026-06-10T11:00:00",
    ]

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
        params={"sort_by": "start_time", "sort_order": "desc"},
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["Start Time"] for row in rows] == [
        "2026-06-10T11:00:00",
        "2026-06-10T10:00:00",
        "2026-06-10T09:00:00",
    ]


def test_candidate_report_export_sort_by_invalid_field(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_superadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
        params={"sort_by": "not_a_field"},
    )

    assert response.status_code == 400


def test_candidate_report_export_filters_null_and_na_form_response(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """CSV form_response column excludes keys whose value is null or "N/A",
    matching the frontend's "Show Responses" popup filter."""
    user = get_org_user(client, db, get_user_superadmin_token)

    form = Form(
        name=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    for name, order in (("full_name", 0), ("nickname", 1), ("age", 2)):
        db.add(
            FormField(
                form_id=form.id,
                field_type=FormFieldType.TEXT,
                label=name,
                name=name,
                order=order,
            )
        )
    db.commit()

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        form_id=form.id,
    )

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        is_submitted=False,
        end_time=None,
    )

    db.add(
        FormResponse(
            candidate_test_id=candidate_test.id,
            form_id=form.id,
            responses={"full_name": "Jane Doe", "nickname": None},
        )
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["Form Response"] == '{"full_name": "Jane Doe"}'


def test_candidate_report_export_accessible_by_test_admin(
    client: TestClient,
    db: SessionDep,
    get_user_testadmin_token: dict[str, str],
) -> None:
    user = get_org_user(client, db, get_user_testadmin_token)

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report/export",
        headers=get_user_testadmin_token,
    )

    assert response.status_code == 200
    assert list(csv.DictReader(io.StringIO(response.text))) == []


def test_candidate_report_csv_row_matches_headers() -> None:
    entry = CandidateReport(
        candidate_id=1,
        candidate_test_id=1,
        candidate_uuid=uuid.uuid4(),
        status=CandidateReportStatus.submitted,
        start_time=datetime(2026, 1, 1, 9, 0, 0),
        end_time=datetime(2026, 1, 1, 9, 45, 0),
        time_taken_seconds=2700,
        result=Result(
            correct_answer=1,
            incorrect_answer=2,
            mandatory_not_attempted=3,
            optional_not_attempted=4,
            total_questions=5,
            marks_obtained=6.0,
            marks_maximum=7.0,
        ),
        form_response={"key": "value"},
    )

    row = candidate_report_to_csv_row(entry)

    assert len(row) == len(CANDIDATE_REPORT_CSV_HEADERS)
    values_by_header = dict(zip(CANDIDATE_REPORT_CSV_HEADERS, row, strict=True))
    assert values_by_header == {
        "Candidate UUID": str(entry.candidate_uuid),
        "Status": "submitted",
        "Marks Obtained": 6.0,
        "Marks Maximum": 7.0,
        "Correct Answers": 1,
        "Incorrect Answers": 2,
        "Mandatory Not Attempted": 3,
        "Optional Not Attempted": 4,
        "Total Questions": 5,
        "Start Time": "2026-01-01T09:00:00",
        "End Time": "2026-01-01T09:45:00",
        "Time Taken (seconds)": 2700,
        "Form Response": '{"key": "value"}',
    }


def test_candidate_report_id_resolves_the_attempt(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """The reported candidate_test_id works against the per-attempt endpoints."""
    user = get_org_user(client, db, get_user_superadmin_token)

    revision = create_random_question_revision(
        db,
        user_id=user.id,
        org_id=user.organization_id,
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )
    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = create_test_candidate(db, organization_id=user.organization_id)
    candidate.identity = uuid.uuid4()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:32:00",
    )
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    report = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )
    assert report.status_code == 200
    entry = report.json()["items"][0]

    result = client.get(
        f"{settings.API_V1_STR}/candidate/result/{entry['candidate_test_id']}",
        params={"candidate_uuid": entry["candidate_uuid"]},
    )
    assert result.status_code == 200
