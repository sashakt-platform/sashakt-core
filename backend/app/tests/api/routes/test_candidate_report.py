import uuid

from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import TestQuestion
from app.models.candidate import CandidateTestAnswer
from app.tests.utils.candidate import (
    create_test_candidate,
    create_test_candidate_test,
    create_test_record,
)
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user, get_current_user_data


def test_candidate_report_submitted(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

    revision = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision.marking_scheme = {"correct": 10, "wrong": 0, "skipped": 0}
    db.add(revision)
    db.commit()
    db.refresh(revision)

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
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

    revision_one = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision_one.marking_scheme = {"correct": 5, "wrong": 0, "skipped": 0}
    db.add(revision_one)
    db.commit()

    revision_two = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision_two.marking_scheme = {"correct": 5, "wrong": 0, "skipped": 0}
    db.add(revision_two)
    db.commit()

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
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

    revision_one = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision_one.marking_scheme = {"correct": 10, "wrong": 0, "skipped": 0}
    db.add(revision_one)
    db.commit()

    revision_two = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision_two.marking_scheme = {"correct": 5, "wrong": 0, "skipped": 0}
    db.add(revision_two)
    db.commit()

    revision_three = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision_three.marking_scheme = {"correct": 2, "wrong": 0, "skipped": 0}
    db.add(revision_three)
    db.commit()

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
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

    revision = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision.marking_scheme = {"correct": 10, "wrong": 0, "skipped": 0}
    db.add(revision)
    db.commit()

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
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

    revision = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision.marking_scheme = {"correct": 10, "wrong": 0, "skipped": 0}
    db.add(revision)
    db.commit()

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
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

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


def test_candidate_report_skips_candidate_without_identity(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """A candidate without identity (registered user, not QR-code) should not appear."""
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

    revision = create_random_question_revision(
        db, user_id=user.id, org_id=user.organization_id
    )
    revision.marking_scheme = {"correct": 10, "wrong": 0, "skipped": 0}
    db.add(revision)
    db.commit()

    test = create_test_record(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        marks_level="question",
    )

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate_without_identity = create_test_candidate(
        db, organization_id=user.organization_id
    )

    create_test_candidate_test(
        db,
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate_without_identity.id,
        question_revision_ids=[revision.id],
        is_submitted=True,
        end_time="2026-06-10T10:20:00",
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
