import csv
import io
import uuid

from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import TestQuestion
from app.models.candidate import CandidateTestAnswer
from app.models.certificate import Certificate
from app.models.form import Form, FormField, FormFieldType, FormResponse
from app.tests.utils.candidate import (
    create_test_candidate,
    create_test_candidate_test,
    create_test_record,
)
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
