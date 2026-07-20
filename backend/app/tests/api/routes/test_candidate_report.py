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
from app.tests.utils.form import create_form, create_form_response
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user, get_org_user


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
