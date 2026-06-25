import uuid

from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import Test, TestQuestion
from app.models.candidate import Candidate, CandidateTest, CandidateTestAnswer
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import random_lower_string


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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = Candidate(
        identity=uuid.uuid4(),
        organization_id=user.organization_id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:00:00",
        end_time="2026-06-10T10:32:00",
        is_submitted=True,
        question_revision_ids=[revision.id],
        question_set_ids=[None],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision.id,
        response="[1]",
        visited=True,
    )
    db.add(answer)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["candidates"]) == 1

    entry = data["candidates"][0]
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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level="test",
        marking_scheme={"correct": 10, "wrong": 0, "skipped": 0},
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_one.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_two.id))
    db.commit()

    candidate = Candidate(
        identity=uuid.uuid4(),
        organization_id=user.organization_id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:00:00",
        end_time="2026-06-10T10:30:00",
        is_submitted=True,
        question_revision_ids=[revision_one.id, revision_two.id],
        question_set_ids=[None, None],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

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
    assert len(data["candidates"]) == 1

    entry = data["candidates"][0]
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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_one.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_two.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=revision_three.id))
    db.commit()

    candidate = Candidate(
        identity=uuid.uuid4(),
        organization_id=user.organization_id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:00:00",
        end_time="2026-06-10T10:25:00",
        is_submitted=True,
        question_revision_ids=[revision_one.id, revision_two.id, revision_three.id],
        question_set_ids=[None, None, None],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

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
    assert len(data["candidates"]) == 1

    entry = data["candidates"][0]
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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    submitted_candidate = Candidate(
        identity=uuid.uuid4(),
        organization_id=user.organization_id,
    )
    db.add(submitted_candidate)
    db.commit()
    db.refresh(submitted_candidate)

    submitted_ct = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=submitted_candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:00:00",
        end_time="2026-06-10T10:20:00",
        is_submitted=True,
        question_revision_ids=[revision.id],
        question_set_ids=[None],
    )
    db.add(submitted_ct)
    db.commit()
    db.refresh(submitted_ct)

    db.add(
        CandidateTestAnswer(
            candidate_test_id=submitted_ct.id,
            question_revision_id=revision.id,
            response="[1]",
            visited=True,
        )
    )
    db.commit()

    in_progress_candidate = Candidate(
        identity=uuid.uuid4(),
        organization_id=user.organization_id,
    )
    db.add(in_progress_candidate)
    db.commit()
    db.refresh(in_progress_candidate)

    in_progress_ct = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=in_progress_candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:05:00",
        end_time=None,
        is_submitted=False,
        question_revision_ids=[revision.id],
        question_set_ids=[None],
    )
    db.add(in_progress_ct)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["candidates"]) == 2

    entries_by_uuid = {e["candidate_uuid"]: e for e in data["candidates"]}

    submitted_entry = entries_by_uuid[str(submitted_candidate.identity)]
    assert submitted_entry["status"] == "submitted"
    assert submitted_entry["result"]["marks_obtained"] == 10.0
    assert submitted_entry["start_time"] == "2026-06-10T10:00:00"
    assert submitted_entry["end_time"] == "2026-06-10T10:20:00"
    assert submitted_entry["time_taken_seconds"] == 1200

    in_progress_entry = entries_by_uuid[str(in_progress_candidate.identity)]
    assert in_progress_entry["status"] == "in_progress"
    assert in_progress_entry["result"] is None
    assert in_progress_entry["start_time"] == "2026-06-10T10:05:00"
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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate = Candidate(
        identity=uuid.uuid4(),
        organization_id=user.organization_id,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:00:00",
        end_time=None,
        is_submitted=False,
        question_revision_ids=[revision.id],
        question_set_ids=[None],
    )
    db.add(candidate_test)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["candidates"]) == 1

    entry = data["candidates"][0]
    assert entry["candidate_uuid"] == str(candidate.identity)
    assert entry["end_time"] is None
    assert entry["time_taken_seconds"] is None


def test_candidate_report_different_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    other_user = create_random_user(db)

    test = Test(
        name=random_lower_string(),
        created_by_id=other_user.id,
        organization_id=other_user.organization_id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["candidates"] == []


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

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
        is_active=True,
        link=random_lower_string(),
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=revision.id))
    db.commit()

    candidate_without_identity = Candidate(
        identity=None,
        organization_id=user.organization_id,
    )
    db.add(candidate_without_identity)
    db.commit()
    db.refresh(candidate_without_identity)

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate_without_identity.id,
        device=random_lower_string(),
        consent=True,
        start_time="2026-06-10T10:00:00",
        end_time="2026-06-10T10:20:00",
        is_submitted=True,
        question_revision_ids=[revision.id],
        question_set_ids=[None],
    )
    db.add(candidate_test)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/candidate-report",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["candidates"] == []
