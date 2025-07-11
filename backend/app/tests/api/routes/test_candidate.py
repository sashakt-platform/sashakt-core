import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import (
    Candidate,
    CandidateTest,
    CandidateTestAnswer,
    Organization,
    Question,
    QuestionRevision,
    Test,
    TestCandidatePublic,
)
from app.models.question import QuestionType
from app.models.test import TestQuestion
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user

from ...utils.utils import random_lower_string


def test_create_candidate(
    client: TestClient,
    db: SessionDep,
    get_user_candidate_token: dict[str, str],
) -> None:
    user = create_random_user(db)

    response = client.post(
        f"{settings.API_V1_STR}/candidate/",
        json={"user_id": user.id},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data
    assert data["is_active"] is True
    assert data["user_id"] == user.id

    response = client.post(
        f"{settings.API_V1_STR}/candidate/",
        headers=get_user_candidate_token,
        json={},
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data


def test_read_candidate(
    client: TestClient,
    db: SessionDep,
    get_user_testadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    candidate = Candidate(user_id=user.id)
    db.add(candidate)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate",
        headers=get_user_testadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    current_index = len(data) - 1
    data[current_index]["user_id"] = user.id

    candidate = Candidate()
    db.add(candidate)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate",
        headers=get_user_testadmin_token,
    )
    data = response.json()
    current_index = len(data) - 1
    assert response.status_code == 200
    assert data[current_index]["user_id"] is None


def test_read_candidate_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_stateadmin_token: dict[str, str],
) -> None:
    user_a = create_random_user(db)
    user_b = create_random_user(db)

    candidate_a = Candidate(user_id=user_a.id)
    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_a, candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        headers=get_user_stateadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["user_id"] == user_a.id
    assert data["id"] == candidate_aa.id
    assert data["created_date"] == (
        candidate_aa.created_date.isoformat() if candidate_aa.created_date else None
    )
    assert data["modified_date"] == (
        candidate_aa.modified_date.isoformat() if candidate_aa.modified_date else None
    )
    assert data["is_active"] is True
    assert data["is_deleted"] is False

    response = client.get(
        f"{settings.API_V1_STR}/candidate/{candidate_b.id}",
        headers=get_user_stateadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["user_id"] == user_b.id
    assert data["id"] == candidate_b.id
    assert data["created_date"] == (
        candidate_b.created_date.isoformat() if candidate_b.created_date else None
    )
    assert data["modified_date"] == (
        candidate_b.modified_date.isoformat() if candidate_b.modified_date else None
    )
    assert data["is_active"] is True
    assert data["is_deleted"] is False

    response = client.get(
        f"{settings.API_V1_STR}/candidate/{candidate_c.id}",
        headers=get_user_stateadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["user_id"] is None
    assert data["id"] == candidate_c.id
    assert data["created_date"] == (
        candidate_c.created_date.isoformat() if candidate_c.created_date else None
    )
    assert data["modified_date"] == (
        candidate_c.modified_date.isoformat() if candidate_c.modified_date else None
    )
    assert data["is_active"] is True
    assert data["is_deleted"] is False


def test_update_candidate(
    client: TestClient, db: SessionDep, get_user_candidate_token: dict[str, str]
) -> None:
    user_a = create_random_user(db)
    user_b = create_random_user(db)

    candidate_a = Candidate(user_id=user_a.id)
    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_a, candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        json={"user_id": user_b.id},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["user_id"] == user_b.id

    response = client.put(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        json={"user_id": None},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["user_id"] is None

    response = client.put(
        f"{settings.API_V1_STR}/candidate/{candidate_c.id}",
        json={"user_id": user_a.id},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_c.id
    assert data["user_id"] == user_a.id


def test_visibility_candidate(
    client: TestClient, db: SessionDep, get_user_candidate_token: dict[str, str]
) -> None:
    user_a = create_random_user(db)
    user_b = create_random_user(db)

    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.patch(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        params={"is_active": True},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["is_active"] is True
    assert data["is_active"] is not False and not None

    response = client.patch(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        params={"is_active": False},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None

    response = client.patch(
        f"{settings.API_V1_STR}/candidate/{candidate_c.id}",
        params={"is_active": False},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_c.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None


def test_delete_candidate(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_a = create_random_user(db)
    user_b = create_random_user(db)

    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.delete(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert "delete" in data["message"]

    response = client.get(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 404
    assert "id" not in data


# Test cases for Candidate and Tests


def test_create_candidate_test(
    client: TestClient, db: SessionDep, get_user_candidate_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate = Candidate(user_id=user.id)

    db.add(candidate)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device = random_lower_string()
    start_time = "2025-03-19T10:00:00Z"
    end_time = "2025-03-19T12:00:00Z"

    response = client.post(
        f"{settings.API_V1_STR}/candidate_test/",
        json={
            "test_id": test.id,
            "candidate_id": candidate.id,
            "device": device,
            "consent": True,
            "start_time": start_time,
            "end_time": end_time,
            "is_submitted": False,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data
    assert data["test_id"] == test.id
    assert data["candidate_id"] == candidate.id
    assert data["device"] == device
    assert data["is_submitted"] is False
    assert data["start_time"] == start_time.rstrip("Z")
    assert data["end_time"] == end_time.rstrip("Z")
    assert data["is_submitted"] is False


def test_read_candidate_test(
    client: TestClient, db: SessionDep, get_user_stateadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate = Candidate(user_id=user.id)

    db.add(candidate)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device = random_lower_string()
    start_time = "2025-03-19T10:00:00Z"
    end_time = "2025-03-19T12:00:00Z"

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=device,
        consent=True,
        start_time=start_time,
        end_time=end_time,
        is_submitted=False,
    )

    db.add(candidate_test)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/candidate_test/",
        headers=get_user_stateadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data[0]
    assert any(item["test_id"] == test.id for item in data)
    assert any(item["candidate_id"] == candidate.id for item in data)
    assert any(item["device"] == device for item in data)
    assert any(item["is_submitted"] is False for item in data)
    assert any(item["start_time"] == start_time.rstrip("Z") for item in data)
    assert any(item["end_time"] == end_time.rstrip("Z") for item in data)


def test_read_candidate_test_by_id(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate_a = Candidate(user_id=user.id)
    candidate_b = Candidate()

    db.add_all([candidate_a, candidate_b])
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device_a = random_lower_string()
    start_time_a = "2025-02-19T10:00:00Z"
    end_time_a = "2025-03-16T12:00:00Z"

    candidate_a_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate_a.id,
        device=device_a,
        consent=True,
        start_time=start_time_a,
        end_time=end_time_a,
        is_submitted=False,
    )

    db.add(candidate_a_test)
    db.commit()

    device_b = random_lower_string()
    start_time_b = "2025-02-10T10:00:00Z"
    end_time_b = "2025-03-14T12:00:00Z"

    candidate_b_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate_b.id,
        device=device_b,
        consent=True,
        start_time=start_time_b,
        end_time=end_time_b,
        is_submitted=False,
    )

    db.add(candidate_b_test)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate_test/{candidate_a_test.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data
    assert data["test_id"] == test.id
    assert data["candidate_id"] == candidate_a.id
    assert data["device"] == device_a
    assert data["is_submitted"] is False
    assert data["start_time"] == start_time_a.rstrip("Z")
    assert data["end_time"] == end_time_a.rstrip("Z")
    assert data["is_submitted"] is False


def test_update_candidate_test_by_id(
    client: TestClient, db: SessionDep, get_user_candidate_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate_a = Candidate(user_id=user.id)
    candidate_b = Candidate()

    db.add_all([candidate_a, candidate_b])
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device_a = random_lower_string()
    start_time_a = "2025-02-19T10:00:00Z"
    end_time_a = "2025-03-16T12:00:00Z"
    consent = False
    is_submitted = False

    candidate_a_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate_a.id,
        device=device_a,
        consent=consent,
        start_time=start_time_a,
        end_time=end_time_a,
        is_submitted=is_submitted,
    )

    db.add(candidate_a_test)
    db.commit()

    device_b = random_lower_string()
    start_time_b = "2025-02-10T10:00:00Z"
    end_time_b = "2025-03-14T12:00:00Z"

    candidate_b_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate_b.id,
        device=device_b,
        consent=True,
        start_time=start_time_b,
        end_time=end_time_b,
        is_submitted=False,
    )

    db.add(candidate_b_test)
    db.commit()

    # Changing Device
    response = client.put(
        f"{settings.API_V1_STR}/candidate_test/{candidate_a_test.id}",
        json={
            "device": device_b,
            "consent": consent,
            "end_time": end_time_a,
            "is_submitted": is_submitted,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["device"] == device_b
    assert data["device"] != device_a
    assert data["consent"] == consent
    assert data["end_time"] == end_time_a.rstrip("Z")
    assert data["is_submitted"] == is_submitted

    # Changing Consent
    response = client.put(
        f"{settings.API_V1_STR}/candidate_test/{candidate_a_test.id}",
        json={
            "device": device_b,
            "consent": True,
            "end_time": end_time_a,
            "is_submitted": is_submitted,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["device"] == device_b
    assert data["device"] != device_a
    assert data["consent"] is True
    assert data["consent"] != consent
    assert data["end_time"] == end_time_a.rstrip("Z")
    assert data["is_submitted"] == is_submitted

    # Changing End Time
    response = client.put(
        f"{settings.API_V1_STR}/candidate_test/{candidate_a_test.id}",
        json={
            "device": device_b,
            "consent": True,
            "end_time": end_time_b,
            "is_submitted": is_submitted,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["device"] == device_b
    assert data["device"] != device_a
    assert data["consent"] is True
    assert data["consent"] != consent
    assert data["end_time"] == end_time_b.rstrip("Z")
    assert data["end_time"] != end_time_a.rstrip("Z")
    assert data["is_submitted"] == is_submitted

    # Changing is_submitted
    response = client.put(
        f"{settings.API_V1_STR}/candidate_test/{candidate_a_test.id}",
        json={
            "device": device_b,
            "consent": True,
            "end_time": end_time_b,
            "is_submitted": True,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["device"] == device_b
    assert data["device"] != device_a
    assert data["consent"] is True
    assert data["consent"] != consent
    assert data["end_time"] == end_time_b.rstrip("Z")
    assert data["end_time"] != end_time_a.rstrip("Z")
    assert data["is_submitted"] is True
    assert data["is_submitted"] != is_submitted


# Test cases for Candidate-Tests & Answers


def test_create_candidate_test_answers(
    client: TestClient, db: SessionDep, get_user_candidate_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate = Candidate(user_id=user.id)

    db.add(candidate)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device = random_lower_string()
    start_time = "2025-02-10T10:00:00Z"
    end_time = "2025-03-14T12:00:00Z"
    consent = True
    is_submitted = False

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=device,
        consent=consent,
        start_time=start_time,
        end_time=end_time,
        is_submitted=is_submitted,
    )

    db.add(candidate_test)
    db.commit()

    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question first
    question_a = Question(organization_id=org.id)
    db.add(question_a)
    db.flush()

    # Create question revision linked to the question
    question_revision_a = QuestionRevision(
        question_id=question_a.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )
    db.add(question_revision_a)
    db.flush()

    # Set the last_revision_id on the question
    question_a.last_revision_id = question_revision_a.id
    db.commit()
    db.refresh(question_a)
    db.refresh(question_revision_a)

    response = client.post(
        f"{settings.API_V1_STR}/candidate_test_answer/",
        json={
            "candidate_test_id": candidate_test.id,
            "question_revision_id": question_revision_a.id,  # Use the revision ID
            "response": random_lower_string(),
            "visited": False,
            "time_spent": 4,
        },
        headers=get_user_candidate_token,
    )

    data = response.json()
    assert response.status_code == 200
    assert data["candidate_test_id"] == candidate_test.id
    assert data["question_revision_id"] == question_revision_a.id
    assert data["response"] is not None
    assert data["visited"] is False
    assert data["time_spent"] == 4


def test_read_candidate_test_answer(
    client: TestClient, db: SessionDep, get_user_systemadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate = Candidate(user_id=user.id)

    db.add(candidate)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device = random_lower_string()
    start_time = "2025-02-10T10:00:00Z"
    end_time = "2025-03-14T12:00:00Z"
    consent = True
    is_submitted = False

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=device,
        consent=consent,
        start_time=start_time,
        end_time=end_time,
        is_submitted=is_submitted,
    )

    db.add(candidate_test)
    db.commit()

    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create questions first
    question_a = Question(organization_id=org.id)
    question_b = Question(organization_id=org.id)
    db.add_all([question_a, question_b])
    db.flush()

    # Create question revisions
    question_revision_a = QuestionRevision(
        question_id=question_a.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )

    question_revision_b = QuestionRevision(
        question_id=question_b.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        correct_answer=[1, 2],
    )

    db.add_all([question_revision_a, question_revision_b])
    db.flush()

    # Set the last_revision_id on the questions
    question_a.last_revision_id = question_revision_a.id
    question_b.last_revision_id = question_revision_b.id
    db.commit()
    db.refresh(question_a)
    db.refresh(question_b)
    db.refresh(question_revision_a)
    db.refresh(question_revision_b)

    response_a = random_lower_string()
    response_b = random_lower_string()

    candidate_test_answer_a = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=question_revision_a.id,
        response=response_a,
        visited=False,
        time_spent=4,
    )

    candidate_test_answer_b = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=question_revision_b.id,
        response=response_b,
        visited=True,
        time_spent=56,
    )

    db.add_all([candidate_test_answer_a, candidate_test_answer_b])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate_test_answer/",
        headers=get_user_systemadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert any(
        item["candidate_test_id"] == candidate_test_answer_a.candidate_test_id
        for item in data
    )
    assert any(item["question_revision_id"] == question_revision_a.id for item in data)
    assert any(item["response"] == candidate_test_answer_a.response for item in data)
    assert any(item["visited"] is False for item in data)
    assert any(item["time_spent"] == 4 for item in data)
    assert any(
        item["candidate_test_id"] == candidate_test_answer_b.candidate_test_id
        for item in data
    )
    assert any(item["question_revision_id"] == question_revision_b.id for item in data)
    assert any(item["response"] == response_b for item in data)
    assert any(item["visited"] is True for item in data)
    assert any(item["time_spent"] == 56 for item in data)


def test_read_candidate_test_answer_by_id(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate = Candidate(user_id=user.id)

    db.add(candidate)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device = random_lower_string()
    start_time = "2025-02-10T10:00:00Z"
    end_time = "2025-03-14T12:00:00Z"
    consent = True
    is_submitted = False

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=device,
        consent=consent,
        start_time=start_time,
        end_time=end_time,
        is_submitted=is_submitted,
    )

    db.add(candidate_test)
    db.commit()

    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create questions first
    question_a = Question(organization_id=org.id)
    question_b = Question(organization_id=org.id)
    db.add_all([question_a, question_b])
    db.flush()

    # Create question revisions
    question_revision_a = QuestionRevision(
        question_id=question_a.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )

    question_revision_b = QuestionRevision(
        question_id=question_b.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
            {"id": 3, "key": "C", "value": "Option C"},
        ],
        correct_answer=[2, 3],
    )

    db.add_all([question_revision_a, question_revision_b])
    db.flush()

    # Set the last_revision_id on the questions
    question_a.last_revision_id = question_revision_a.id
    question_b.last_revision_id = question_revision_b.id
    db.commit()
    db.refresh(question_a)
    db.refresh(question_b)
    db.refresh(question_revision_a)
    db.refresh(question_revision_b)

    response_a = random_lower_string()
    response_b = random_lower_string()

    candidate_test_answer_a = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=question_revision_a.id,
        response=response_a,
        visited=False,
        time_spent=4,
    )

    candidate_test_answer_b = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=question_revision_b.id,
        response=response_b,
        visited=True,
        time_spent=56,
    )

    db.add_all([candidate_test_answer_a, candidate_test_answer_b])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate_test_answer/{candidate_test_answer_a.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_test_answer_a.id
    assert data["candidate_test_id"] == candidate_test.id
    assert data["question_revision_id"] == question_revision_a.id
    assert data["response"] == response_a
    assert data["visited"] is False
    assert data["time_spent"] == 4


def test_update_candidate_test_answer(
    client: TestClient, db: SessionDep, get_user_candidate_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    candidate = Candidate()

    db.add(candidate)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=5,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    device = random_lower_string()
    start_time = "2025-02-10T10:00:00Z"
    end_time = "2025-03-14T12:00:00Z"
    consent = True
    is_submitted = False

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=device,
        consent=consent,
        start_time=start_time,
        end_time=end_time,
        is_submitted=is_submitted,
    )

    db.add(candidate_test)
    db.commit()

    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create questions first
    question_a = Question(organization_id=org.id)
    question_b = Question(organization_id=org.id)
    db.add_all([question_a, question_b])
    db.flush()

    # Create question revisions
    question_revision_a = QuestionRevision(
        question_id=question_a.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )

    question_revision_b = QuestionRevision(
        question_id=question_b.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
            {"id": 3, "key": "C", "value": "Option C"},
        ],
        correct_answer=[1, 2],
    )

    db.add_all([question_revision_a, question_revision_b])
    db.flush()

    # Set the last_revision_id on the questions
    question_a.last_revision_id = question_revision_a.id
    question_b.last_revision_id = question_revision_b.id
    db.commit()
    db.refresh(question_a)
    db.refresh(question_b)
    db.refresh(question_revision_a)
    db.refresh(question_revision_b)

    response_a = random_lower_string()
    response_b = random_lower_string()

    candidate_test_answer_a = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=question_revision_a.id,
        response=response_a,
        visited=False,
        time_spent=4,
    )

    candidate_test_answer_b = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=question_revision_b.id,
        response=response_b,
        visited=True,
        time_spent=56,
    )

    db.add_all([candidate_test_answer_a, candidate_test_answer_b])
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/candidate_test_answer/{candidate_test_answer_a.id}",
        json={
            "response": response_b,
            "visited": True,
            "time_spent": 56,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["response"] == response_b
    assert data["visited"] is True
    assert data["time_spent"] == 56


def test_start_test_for_candidate(client: TestClient, db: SessionDep) -> None:
    """Test the start_test endpoint that creates anonymous candidates."""
    user = create_random_user(db)

    # Create a test
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Test start_test endpoint - no authentication required
    payload = {"test_id": test.id, "device_info": "Chrome Browser on MacOS"}

    response = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert "candidate_uuid" in data
    assert "candidate_test_id" in data

    # Verify candidate was created in database
    candidate_test_id = data["candidate_test_id"]
    candidate_test = db.get(CandidateTest, candidate_test_id)
    assert candidate_test is not None
    assert candidate_test.test_id == test.id
    assert candidate_test.device == "Chrome Browser on MacOS"
    assert candidate_test.consent is True

    # Verify candidate has UUID
    candidate = db.get(Candidate, candidate_test.candidate_id)
    assert candidate is not None
    assert candidate.identity is not None
    assert candidate.user_id is None  # Anonymous candidate

    # Verify end_time is None initially (will be set when test is submitted)
    assert candidate_test.end_time is None
    assert candidate_test.is_submitted is False


def test_start_test_inactive_test(client: TestClient, db: SessionDep) -> None:
    """Test that start_test fails for inactive tests."""
    user = create_random_user(db)

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=False,  # Inactive test
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    payload = {"test_id": test.id, "device_info": "Chrome"}
    response = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)

    assert response.status_code == 404
    assert "Test not found or not active" in response.json()["detail"]


def test_get_test_questions(client: TestClient, db: SessionDep) -> None:
    """Test the test_questions endpoint with candidate UUID verification."""
    user = create_random_user(db)

    # Create organization and question setup
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()

    # Create question with revision
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="What is 2+2?",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "3"},
            {"id": 2, "key": "B", "value": "4"},
            {"id": 3, "key": "C", "value": "5"},
        ],
        correct_answer=[1],
    )
    db.add(question_revision)
    db.flush()

    question.last_revision_id = question_revision.id
    db.commit()
    db.refresh(question_revision)

    # Create test
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    # Link question to test
    from app.models.test import TestQuestion

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision.id
    )
    db.add(test_question)
    db.commit()

    # Create candidate and candidate_test using start_test endpoint
    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()

    identity = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # Test get_test_questions endpoint
    response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_id}",
        params={"candidate_uuid": identity},
    )
    data = response.json()

    assert response.status_code == 200
    assert "id" in data  # Test ID
    assert "name" in data  # Test name
    assert "question_revisions" in data  # Questions (safe, no answers)
    assert "candidate_test" in data
    assert data["id"] == test.id
    assert isinstance(data["question_revisions"], list)
    assert data["candidate_test"]["id"] == candidate_test_id

    # Verify questions don't contain answers (security check)
    if data["question_revisions"]:
        question_data = data["question_revisions"][0]
        assert "question_text" in question_data
        assert "options" in question_data
        assert "correct_answer" not in question_data  # Should not expose answers
        assert "solution" not in question_data  # Should not expose solutions

    # Verify the response can be validated against TestCandidatePublic model
    test_candidate_response = TestCandidatePublic.model_validate(data)
    assert test_candidate_response.id == test.id
    assert test_candidate_response.candidate_test.id == candidate_test_id


def test_get_test_questions_invalid_uuid(client: TestClient, db: SessionDep) -> None:
    """Test that test_questions endpoint fails with invalid candidate UUID."""
    user = create_random_user(db)

    # Create test and candidate_test normally
    test = Test(
        name=random_lower_string(), created_by_id=user.id, link=random_lower_string()
    )
    db.add(test)
    db.commit()

    # Start test to create candidate_test
    payload = {"test_id": test.id}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    candidate_test_id = start_response.json()["candidate_test_id"]

    # Try with fake UUID
    import uuid

    fake_uuid = str(uuid.uuid4())

    response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_id}",
        params={"candidate_uuid": fake_uuid},
    )

    assert response.status_code == 404
    assert "Candidate test not found or invalid UUID" in response.json()["detail"]


def test_submit_answer_for_qr_candidate(client: TestClient, db: SessionDep) -> None:
    """Test QR code candidate can submit answers using UUID authentication."""
    user = create_random_user(db)

    # Create organization and question setup
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()

    # Create question with revision
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="What is 3+3?",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "5"},
            {"id": 2, "key": "B", "value": "6"},
            {"id": 3, "key": "C", "value": "7"},
        ],
        correct_answer=[1],
    )
    db.add(question_revision)
    db.flush()

    question.last_revision_id = question_revision.id
    db.commit()
    db.refresh(question_revision)

    # Create test
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    # Link question to test
    from app.models.test import TestQuestion

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision.id
    )
    db.add(test_question)
    db.commit()

    # Start test (creates candidate with UUID)
    payload = {"test_id": test.id, "device_info": "QR Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # Submit answer using new endpoint (no authentication required, just UUID)
    answer_payload = {
        "question_revision_id": question_revision.id,
        "response": "6",  # Answer choice
        "visited": True,
        "time_spent": 30,
    }

    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answer/{candidate_test_id}",
        json=answer_payload,
        params={"candidate_uuid": candidate_uuid},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["candidate_test_id"] == candidate_test_id
    assert data["question_revision_id"] == question_revision.id
    assert data["response"] == "6"
    assert data["visited"] is True
    assert data["time_spent"] == 30

    # Verify answer was saved in database
    answer = db.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        .where(CandidateTestAnswer.question_revision_id == question_revision.id)
    ).first()
    assert answer is not None
    assert answer.response == "6"


def test_submit_answer_invalid_uuid(client: TestClient, db: SessionDep) -> None:
    """Test that answer submission fails with invalid candidate UUID."""
    user = create_random_user(db)

    # Create basic test setup
    test = Test(
        name=random_lower_string(), created_by_id=user.id, link=random_lower_string()
    )
    db.add(test)
    db.commit()

    # Start test to get candidate_test_id
    payload = {"test_id": test.id}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    candidate_test_id = start_response.json()["candidate_test_id"]

    # Try to submit answer with fake UUID
    import uuid

    fake_uuid = str(uuid.uuid4())
    answer_payload = {
        "question_revision_id": 1,
        "response": "test answer",
        "visited": True,
        "time_spent": 10,
    }

    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answer/{candidate_test_id}",
        json=answer_payload,
        params={"candidate_uuid": fake_uuid},
    )

    assert response.status_code == 404
    assert "Candidate test not found or invalid UUID" in response.json()["detail"]


def test_update_answer_for_qr_candidate(client: TestClient, db: SessionDep) -> None:
    """Test QR code candidate can update existing answers using submit_answer endpoint."""
    user = create_random_user(db)

    # Setup similar to submit_answer test
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()

    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="What is 4+4?",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "7"},
            {"id": 2, "key": "B", "value": "8"},
            {"id": 3, "key": "C", "value": "9"},
        ],
        correct_answer=[1],
    )
    db.add(question_revision)
    db.flush()

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    from app.models.test import TestQuestion

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision.id
    )
    db.add(test_question)
    db.commit()

    # Start test
    payload = {"test_id": test.id, "device_info": "Update Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # First, submit an initial answer
    initial_answer = {
        "question_revision_id": question_revision.id,
        "response": "7",  # Initial wrong answer
        "visited": True,
        "time_spent": 15,
    }

    client.post(
        f"{settings.API_V1_STR}/candidate/submit_answer/{candidate_test_id}",
        json=initial_answer,
        params={"candidate_uuid": candidate_uuid},
    )

    # Now update the answer using the same submit_answer endpoint (it will update existing)
    update_payload = {
        "question_revision_id": question_revision.id,
        "response": "8",  # Correct answer
        "visited": True,
        "time_spent": 45,  # More time spent
    }

    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answer/{candidate_test_id}",
        json=update_payload,
        params={"candidate_uuid": candidate_uuid},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "8"
    assert data["time_spent"] == 45
    assert data["visited"] is True

    # Verify update in database
    answer = db.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        .where(CandidateTestAnswer.question_revision_id == question_revision.id)
    ).first()
    assert answer is not None
    assert answer.response == "8"
    assert answer.time_spent == 45


def test_submit_test_for_qr_candidate(client: TestClient, db: SessionDep) -> None:
    """Test QR code candidate can submit/finish the test."""
    user = create_random_user(db)

    # Create test
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    # Start test
    payload = {"test_id": test.id, "device_info": "Submit Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # Verify test is not submitted initially
    candidate_test = db.get(CandidateTest, candidate_test_id)
    assert candidate_test is not None
    assert candidate_test.is_submitted is False
    assert candidate_test.end_time is None

    # Submit the test
    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_test/{candidate_test_id}",
        params={"candidate_uuid": candidate_uuid},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_submitted"] is True
    assert data["end_time"] is not None

    # Verify in database
    db.refresh(candidate_test)
    assert candidate_test is not None
    assert candidate_test.is_submitted is True
    assert candidate_test.end_time is not None

    # Try to submit again (should fail)
    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_test/{candidate_test_id}",
        params={"candidate_uuid": candidate_uuid},
    )

    assert response.status_code == 400
    assert "Test already submitted" in response.json()["detail"]


def test_submit_answer_updates_existing(client: TestClient, db: SessionDep) -> None:
    """Test that submitting answer to same question updates existing answer."""
    user = create_random_user(db)

    # Setup test and question
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()

    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="What is 5+5?",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        correct_answer=[1],
    )
    db.add(question_revision)
    db.flush()

    question.last_revision_id = question_revision.id
    db.commit()
    db.refresh(question_revision)

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    from app.models.test import TestQuestion

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision.id
    )
    db.add(test_question)
    db.commit()

    # Start test
    payload = {"test_id": test.id}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # Submit first answer
    first_answer = {
        "question_revision_id": question_revision.id,
        "response": "9",
        "visited": True,
        "time_spent": 20,
    }

    response1 = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answer/{candidate_test_id}",
        json=first_answer,
        params={"candidate_uuid": candidate_uuid},
    )

    assert response1.status_code == 200
    first_answer_id = response1.json()["id"]

    # Submit second answer for same question (should update, not create new)
    second_answer = {
        "question_revision_id": question_revision.id,
        "response": "10",
        "visited": True,
        "time_spent": 40,
    }

    response2 = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answer/{candidate_test_id}",
        json=second_answer,
        params={"candidate_uuid": candidate_uuid},
    )

    assert response2.status_code == 200
    assert response2.json()["id"] == first_answer_id  # Same answer ID
    assert response2.json()["response"] == "10"  # Updated response
    assert response2.json()["time_spent"] == 40  # Updated time

    # Verify only one answer exists in database
    answers = db.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        .where(CandidateTestAnswer.question_revision_id == question_revision.id)
    ).all()
    assert len(answers) == 1
    assert answers[0].response == "10"


def test_get_test_result(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,  # Assuming user ID 1 exists
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    # Create a candidate
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    # Create a candidate test
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Test Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    questions = [
        create_random_question_revision(db),
        create_random_question_revision(db),
        create_random_question_revision(db),
        create_random_question_revision(db),
    ]

    db.add_all(questions)
    db.commit()

    # Create a Question first
    question = Question(organization_id=org.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    new_revision_data = {
        "created_by_id": user.id,
        "question_id": question.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [2],
        "is_mandatory": True,
        "is_active": True,
        "is_deleted": False,
    }
    revision = QuestionRevision(**new_revision_data)
    db.add(revision)
    db.commit()
    db.refresh(revision)
    new_revision_data = {
        "created_by_id": user.id,
        "question_id": question.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "apppe"},
            {"id": 2, "key": "B", "value": "banana"},
            {"id": 3, "key": "C", "value": "mango"},
        ],
        "correct_answer": [3],
        "is_mandatory": False,
        "is_active": True,
        "is_deleted": False,
    }
    revision2 = QuestionRevision(**new_revision_data)
    db.add(revision2)
    db.commit()
    db.refresh(revision2)
    for q in questions:
        test_question = TestQuestion(test_id=test.id, question_revision_id=q.id)
        db.add(test_question)
    test_question1 = TestQuestion(test_id=test.id, question_revision_id=revision.id)
    test_question2 = TestQuestion(test_id=test.id, question_revision_id=revision2.id)
    db.add(test_question1)
    db.add(test_question2)
    db.commit()

    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=questions[0].id,
        response=1,
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=questions[1].id,  # Assuming question revision ID 1 exists
        response=2,
        visited=True,
        time_spent=30,
    )

    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision.id,
        response="2",
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision2.id,
        response=3,
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    # Call the endpoint
    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        headers=get_user_superadmin_token,
        params={"candidate_uuid": str(candidate.identity)},
    )

    assert response.status_code == 200
    data = response.json()

    # assert data["test_id"] == test.id
    assert data["correct_answer"] == 2
    assert data["incorrect_answer"] == 2
    assert data["mandatory_not_attempted"] == 0
    assert data["optional_not_attempted"] == 0


def test_result_with_no_answers(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,  # Assuming user ID 1 exists
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    # Create a candidate
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    # Create a candidate test
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Test Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)
    question = Question(organization_id=org.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    new_revision_data = {
        "created_by_id": user.id,
        "question_id": question.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        "correct_answer": [3],
        "is_mandatory": True,
        "is_active": True,
        "is_deleted": False,
    }
    revision = QuestionRevision(**new_revision_data)
    db.add(revision)
    db.commit()
    db.refresh(revision)

    question2 = Question(organization_id=org.id)
    db.add(question2)
    db.commit()
    db.refresh(question2)

    new_revision_data = {
        "created_by_id": user.id,
        "question_id": question2.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "values 1"},
            {"id": 2, "key": "B", "value": "values 2"},
            {"id": 3, "key": "C", "value": " values 3"},
        ],
        "correct_answer": [2, 3],
        "is_mandatory": True,
        "is_active": True,
        "is_deleted": False,
    }
    revision2 = QuestionRevision(**new_revision_data)
    db.add(revision2)
    db.commit()
    db.refresh(revision2)

    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision.id,  # Assuming question revision ID 1 exists
        response="",
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)

    candidate_test_answer2 = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision2.id,
        response=[3, 2],
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer2)
    db.commit()
    db.refresh(candidate_test_answer2)

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        params={"candidate_uuid": str(candidate.identity)},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["correct_answer"] == 1
    assert data["incorrect_answer"] == 0
    assert data["mandatory_not_attempted"] == 1
    assert data["optional_not_attempted"] == 0


def test_get_test_result_not_found(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    candidate_test_id = 100
    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
        params={"candidate_uuid": str(candidate.identity)},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate test not found"


def test_convert_to_list_with_int_reponse(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions="Test is of mcq",
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Test Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)
    question = Question(organization_id=org.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    revision = QuestionRevision(
        created_by_id=user.id,
        question_id=question.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        correct_answer=[1, 2],
        is_mandatory=True,
        is_active=True,
        is_deleted=False,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    revision2 = QuestionRevision(
        created_by_id=user.id,
        question_id=question.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[2],
        is_mandatory=False,
        is_active=True,
        is_deleted=False,
    )
    db.add(revision2)
    db.commit()
    db.refresh(revision2)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision.id,
        response=[2, 3],  # Integer response
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision2.id,
        response="",  # Integer response
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        params={"candidate_uuid": str(candidate.identity)},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["correct_answer"] == 0  # Assuming correct answer is option B (2)
    assert data["incorrect_answer"] == 1
    assert data["mandatory_not_attempted"] == 0
    assert data["optional_not_attempted"] == 1


def test_submit_batch_answers_for_qr_candidate(
    client: TestClient, db: SessionDep
) -> None:
    """Test submitting multiple answers at once"""
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()

    # Create question with revision
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="What is 2+2?",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "3"},
            {"id": 2, "key": "B", "value": "4"},
        ],
        correct_answer=[2],
    )
    db.add(question_revision)
    db.flush()
    question.last_revision_id = question_revision.id
    db.commit()
    db.refresh(question_revision)

    # Create a second question revision for testing
    second_question = Question(organization_id=org.id)
    db.add(second_question)
    db.flush()
    second_question_revision = QuestionRevision(
        question_id=second_question.id,
        created_by_id=user.id,
        question_text="Second test question",
        question_type=QuestionType.single_choice,
        options=[{"id": 1, "key": "A", "value": "1"}],
        correct_answer=[1],
    )
    db.add(second_question_revision)
    db.flush()
    second_question.last_revision_id = second_question_revision.id
    db.commit()
    db.refresh(second_question_revision)

    # Create test
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    # Link questions to test
    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision.id))
    db.add(
        TestQuestion(test_id=test.id, question_revision_id=second_question_revision.id)
    )
    db.commit()

    # Start test to create candidate and candidate_test
    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # Prepare batch request
    batch_request = {
        "answers": [
            {
                "question_revision_id": question_revision.id,
                "response": "4",
                "visited": True,
                "time_spent": 30,
            },
            {
                "question_revision_id": second_question_revision.id,
                "response": "1",
                "visited": True,
                "time_spent": 45,
            },
        ]
    }

    # Submit batch answers
    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answers/{candidate_test_id}",
        json=batch_request,
        params={"candidate_uuid": candidate_uuid},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Sort by question revision ID to have a deterministic order for verification
    data.sort(key=lambda x: x["question_revision_id"])

    # Verify first answer
    assert data[0]["question_revision_id"] == question_revision.id
    assert data[0]["response"] == "4"
    assert data[0]["visited"] is True
    assert data[0]["time_spent"] == 30

    # Verify second answer
    assert data[1]["question_revision_id"] == second_question_revision.id
    assert data[1]["response"] == "1"
    assert data[1]["visited"] is True
    assert data[1]["time_spent"] == 45

    # Verify answers in database
    answers = db.exec(
        select(CandidateTestAnswer)
        .where(CandidateTestAnswer.candidate_test_id == candidate_test_id)
        .order_by("question_revision_id")
    ).all()
    assert len(answers) == 2
    assert answers[0].response == "4"
    assert answers[1].response == "1"


def test_submit_batch_answers_invalid_uuid(client: TestClient, db: SessionDep) -> None:
    """Test submitting batch answers with invalid UUID"""
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(), created_by_id=user.id, link=random_lower_string()
    )
    db.add(test)
    db.commit()

    # Start test to create candidate_test
    payload = {"test_id": test.id}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    candidate_test_id = start_response.json()["candidate_test_id"]

    batch_request: dict[str, list[dict[str, Any]]] = {
        "answers": [
            {
                "question_revision_id": 1,
                "response": "1",
                "visited": True,
                "time_spent": 30,
            }
        ]
    }

    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answers/{candidate_test_id}",
        json=batch_request,
        params={"candidate_uuid": str(uuid.uuid4())},  # Random UUID
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate test not found or invalid UUID"


def test_submit_batch_answers_empty_list(client: TestClient, db: SessionDep) -> None:
    """Test submitting empty batch answers list"""
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(), created_by_id=user.id, link=random_lower_string()
    )
    db.add(test)
    db.commit()

    # Start test to create candidate_test
    payload = {"test_id": test.id}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    batch_request: dict[str, list[Any]] = {"answers": []}

    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answers/{candidate_test_id}",
        json=batch_request,
        params={"candidate_uuid": candidate_uuid},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_submit_batch_answers_update_existing(
    client: TestClient, db: SessionDep
) -> None:
    """Test updating existing answers in batch"""
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()

    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="What is 2+2?",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "3"},
            {"id": 2, "key": "B", "value": "4"},
        ],
        correct_answer=[2],
    )
    db.add(question_revision)
    db.flush()
    question.last_revision_id = question_revision.id
    db.commit()
    db.refresh(question_revision)

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision.id))
    db.commit()

    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    # Create initial answer
    initial_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test_id,
        question_revision_id=question_revision.id,
        response="3",
        visited=True,
        time_spent=20,
    )
    db.add(initial_answer)
    db.commit()
    db.refresh(initial_answer)

    # Prepare batch request to update the answer
    batch_request: dict[str, list[dict[str, Any]]] = {
        "answers": [
            {
                "question_revision_id": question_revision.id,
                "response": "4",
                "visited": True,
                "time_spent": 30,
            }
        ]
    }

    # Submit batch answers
    response = client.post(
        f"{settings.API_V1_STR}/candidate/submit_answers/{candidate_test_id}",
        json=batch_request,
        params={"candidate_uuid": candidate_uuid},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["response"] == "4"
    assert data[0]["time_spent"] == 30

    # Verify answer was updated in database
    db.refresh(initial_answer)
    assert initial_answer.response == "4"
    assert initial_answer.time_spent == 30


def test_candidate_timer_with_specific_dates(
    client: TestClient, db: SessionDep
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        user = create_random_user(db)
        org = Organization(name=random_lower_string())

        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(org)
        db.commit()
        db.refresh(org)

        test = Test(
            name="Date Based Test",
            start_time=fake_current_time - timedelta(minutes=30),
            end_time=fake_current_time + timedelta(minutes=40),
            time_limit=60,  # 60 minutes time limit
            is_active=True,
            created_by_id=user.id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)

        candidate_test = CandidateTest(
            test_id=test.id,
            candidate_id=candidate.id,
            device="Laptop",
            consent=True,
            start_time=fake_current_time - timedelta(minutes=30),
            is_submitted=False,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)

        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
        )

        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data
        time_left = data["time_left"]
        assert isinstance(time_left, int)
        assert time_left == 1800


def test_candidate_timer_candidate_test_not_found(
    client: TestClient, db: SessionDep
) -> None:
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    # Try accessing a non-existing candidate test ID (e.g., 99999)
    response = client.get(
        f"{settings.API_V1_STR}/candidate/time_left/99999",
        params={"candidate_uuid": str(candidate.identity)},
    )

    # Assert 404 response
    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate test not found or invalid UUID"


def test_candidate_timer_end_time_takes_priority(
    client: TestClient, db: SessionDep
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        user = create_random_user(db)
        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        now = fake_current_time
        test = Test(
            name="End Time Priority Test",
            start_time=now - timedelta(minutes=2),
            end_time=now + timedelta(minutes=5),
            time_limit=60,
            is_active=True,
            created_by_id=user.id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        candidate_test = CandidateTest(
            test_id=test.id,
            candidate_id=candidate.id,
            created_by_id=user.id,
            start_time=now - timedelta(minutes=2),
            is_submitted=False,
            device="Laptop",
            consent=True,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)
        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data

        time_left = int(data["time_left"])
        assert time_left == 300


def test_candidate_timer_timelimit_and_end_time_not_set(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        user = create_random_user(db)

        test = Test(
            name="Time Limit Test",
            description="Test without time limit",
            start_instructions="Instructions",
            link=random_lower_string(),
            created_by_id=user.id,
            is_active=True,
            is_deleted=False,
            time_limit=None,
        )
        db.add(test)
        db.commit()
        db.refresh(test)

        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        candidate_test = CandidateTest(
            test_id=test.id,
            candidate_id=candidate.id,
            device="Laptop",
            consent=True,
            start_time=fake_current_time,
            end_time=None,
            is_submitted=False,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)

        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
            headers=get_user_superadmin_token,
        )

        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data

        assert data["time_left"] is None


def test_candidate_timer_with_only_time_limit(
    client: TestClient, db: SessionDep
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        # Create a candidate with random UUID
        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        # Create a user
        user = create_random_user(db)
        test = Test(
            name="Only Time Limit Test",
            time_limit=30,  # 30 minutes
            end_time=None,
            start_time=fake_current_time
            - timedelta(minutes=5),  # test started 5 minutes ago
            is_active=True,
            created_by_id=user.id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        candidate_test = CandidateTest(
            test_id=test.id,
            created_by_id=user.id,
            candidate_id=candidate.id,
            device="Laptop",
            consent=True,
            start_time=fake_current_time - timedelta(minutes=5),
            is_submitted=False,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)
        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data
        assert isinstance(data["time_left"], int)
        assert data["time_left"] == 1500  # 30 minutes in seconds


def test_candidate_timer_only_end_time(client: TestClient, db: SessionDep) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        user = create_random_user(db)
        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        now = fake_current_time
        test = Test(
            name="End Time Priority Test",
            start_time=now - timedelta(minutes=2),
            end_time=now + timedelta(minutes=5),
            is_active=True,
            created_by_id=user.id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        candidate_test = CandidateTest(
            test_id=test.id,
            candidate_id=candidate.id,
            created_by_id=user.id,
            start_time=now - timedelta(minutes=2),
            is_submitted=False,
            device="Laptop",
            consent=True,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)
        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data

        time_left = int(data["time_left"])
        assert time_left == 300


def test_candidate_timer_no_start_time(client: TestClient, db: SessionDep) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        user = create_random_user(db)
        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        now = fake_current_time
        test = Test(
            name="End Time Priority Test",
            end_time=now + timedelta(minutes=5),
            time_limit=3,
            is_active=True,
            created_by_id=user.id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        candidate_test = CandidateTest(
            test_id=test.id,
            candidate_id=candidate.id,
            created_by_id=user.id,
            start_time=now - timedelta(minutes=2),
            is_submitted=False,
            device="Laptop",
            consent=True,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)
        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data

        time_left = int(data["time_left"])
        assert time_left == 60


def test_candidate_timer_no_start_time_only_end_time(
    client: TestClient, db: SessionDep
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch(
        "app.api.routes.candidate.get_current_time", return_value=fake_current_time
    ):
        user = create_random_user(db)
        candidate = Candidate(identity=uuid.uuid4())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        now = fake_current_time
        test = Test(
            name="End Time Priority Test",
            end_time=now + timedelta(minutes=5),
            is_active=True,
            created_by_id=user.id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        candidate_test = CandidateTest(
            test_id=test.id,
            candidate_id=candidate.id,
            created_by_id=user.id,
            start_time=now - timedelta(minutes=2),
            is_submitted=False,
            device="Laptop",
            consent=True,
        )
        db.add(candidate_test)
        db.commit()
        db.refresh(candidate_test)
        response = client.get(
            f"{settings.API_V1_STR}/candidate/time_left/{candidate_test.id}",
            params={"candidate_uuid": str(candidate.identity)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data

        time_left = int(data["time_left"])
        assert time_left == 300


def test_result_not_visible(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)
    test = Test(
        name="Hidden Result Test",
        description=random_lower_string(),
        time_limit=50,
        marks=90,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,  # Assuming user ID 1 exists
        is_active=True,
        is_deleted=False,
        show_result=False,  # Result not visible
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    # Create a candidate
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    # Create a candidate test
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Test phone",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    # Create a Question first
    question = Question(organization_id=org.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    new_revision_data = {
        "created_by_id": user.id,
        "question_id": question.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [2],
        "is_mandatory": True,
        "is_active": True,
        "is_deleted": False,
    }
    revision = QuestionRevision(**new_revision_data)
    db.add(revision)
    db.commit()
    db.refresh(revision)
    new_revision_data = {
        "created_by_id": user.id,
        "question_id": question.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "apppe"},
            {"id": 2, "key": "B", "value": "banana"},
            {"id": 3, "key": "C", "value": "mango"},
        ],
        "correct_answer": [3],
        "is_mandatory": False,
        "is_active": True,
        "is_deleted": False,
    }
    revision2 = QuestionRevision(**new_revision_data)
    db.add(revision2)
    db.commit()
    db.refresh(revision2)

    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision.id,
        response="2",
        visited=True,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=revision2.id,
        response=3,
        visited=True,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    # Call the endpoint
    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        headers=get_user_superadmin_token,
        params={"candidate_uuid": str(candidate.identity)},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["detail"] == "Results are not visible for this test"


def test_candidate_inactive_not_listed(
    client: TestClient,
    db: SessionDep,
    get_user_candidate_token: dict[str, str],
) -> None:
    user = create_random_user(db)

    response = client.post(
        f"{settings.API_V1_STR}/candidate/",
        json={"user_id": user.id, "is_active": False},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["is_active"] is False
    assert data["user_id"] == user.id


def test_start_test_before_start_time(client: TestClient, db: SessionDep) -> None:
    user = create_random_user(db)

    # Create a test
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        start_time="2025-07-06T12:30:00Z",
        time_limit=60,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    payload = {"test_id": test.id, "device_info": "Browser on MacOS Chrome"}
    fake_now = datetime(2025, 7, 5, 12, 0, 0)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        response = client.post(
            f"{settings.API_V1_STR}/candidate/start_test", json=payload
        )
        assert response.status_code == 400
        assert "Test has not started yet" in response.json()["detail"]


def test_candidate_test_question_ids_are_shuffled(
    client: TestClient, db: SessionDep
) -> None:
    """Test the start_test endpoint that creates anonymous candidates."""
    user = create_random_user(db)

    # Create a test
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=70,
        marks=200,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,
        shuffle=True,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    question_ids = []
    for i in range(10):
        question = Question(
            created_by_id=user.id,
            organization_id=user.organization_id,
            is_active=True,
            is_deleted=False,
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        q = QuestionRevision(
            question_text=f"Q{i}",
            created_by_id=user.id,
            question_id=question.id,
            question_type="single_choice",
            options=[{"id": 1, "key": "A", "value": "Option"}],
            correct_answer=[1],
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        question_ids.append(q.id)
        tq = TestQuestion(test_id=test.id, question_revision_id=q.id)
        db.add(tq)
        db.commit()

    payload = {"test_id": test.id, "device_info": "Chrome Browser on ubuntu"}

    response = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert "candidate_uuid" in data
    assert "candidate_test_id" in data
    candidate_test = db.exec(
        select(CandidateTest).where(CandidateTest.id == data["candidate_test_id"])
    ).first()
    assert candidate_test is not None
    stored_ids = [int(qid) for qid in candidate_test.question_revision_ids if qid]

    assert len(stored_ids) == len(question_ids)
    assert set(stored_ids) == set(question_ids)
    assert stored_ids != question_ids
    get_response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test.id}",
        params={"candidate_uuid": data["candidate_uuid"]},
    )
    assert get_response.status_code == 200
    test_data = get_response.json()
    returned_questions = test_data["question_revisions"]
    returned_ids = [q["id"] for q in returned_questions]

    assert returned_ids == stored_ids
    response2 = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    data2 = response2.json()
    assert response2.status_code == 200
    candidate_test_2 = db.exec(
        select(CandidateTest).where(CandidateTest.id == data2["candidate_test_id"])
    ).first()
    assert candidate_test_2 is not None
    stored_ids_2 = [int(qid) for qid in candidate_test_2.question_revision_ids if qid]
    assert len(stored_ids_2) == len(question_ids)
    assert set(stored_ids_2) == set(question_ids)
    assert stored_ids_2 != question_ids
    get_response2 = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_2.id}",
        params={"candidate_uuid": data2["candidate_uuid"]},
    )
    assert get_response2.status_code == 200
    test_data2 = get_response2.json()
    returned_questions2 = test_data2["question_revisions"]
    returned_ids2 = [q["id"] for q in returned_questions2]
    assert returned_ids2 == stored_ids_2
    assert stored_ids != stored_ids_2
    assert len(stored_ids) == len(stored_ids_2)
    assert sorted(stored_ids) == sorted(stored_ids_2)


def test_candidate_test_question_ids_are_random(
    client: TestClient, db: SessionDep
) -> None:
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=70,
        marks=150,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,
        shuffle=True,
        random_questions=True,
        no_of_random_questions=3,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    all_question_ids = []
    for i in range(10):
        question = Question(
            created_by_id=user.id,
            organization_id=user.organization_id,
            is_active=True,
            is_deleted=False,
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        q = QuestionRevision(
            question_text=f"Q{i}",
            created_by_id=user.id,
            question_id=question.id,
            question_type="single_choice",
            options=[{"id": 1, "key": "A", "value": "Option"}],
            correct_answer=[1],
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        all_question_ids.append(q.id)
        tq = TestQuestion(test_id=test.id, question_revision_id=q.id)
        db.add(tq)
        db.commit()

    payload = {"test_id": test.id, "device_info": "Chrome Browser on Ubuntu"}
    response = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "candidate_uuid" in data
    assert "candidate_test_id" in data
    candidate_test = db.exec(
        select(CandidateTest).where(CandidateTest.id == data["candidate_test_id"])
    ).first()
    assert candidate_test is not None
    stored_ids = candidate_test.question_revision_ids

    assert len(stored_ids) == 3
    assert set(stored_ids).issubset(set(all_question_ids))
    get_response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test.id}",
        params={"candidate_uuid": data["candidate_uuid"]},
    )
    assert get_response.status_code == 200
    test_data = get_response.json()
    returned_questions = test_data["question_revisions"]
    returned_ids = [q["id"] for q in returned_questions]

    assert returned_ids == stored_ids
    response2 = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    assert response2.status_code == 200
    data2 = response2.json()
    assert "candidate_uuid" in data2
    assert "candidate_test_id" in data2
    candidate_test_2 = db.exec(
        select(CandidateTest).where(CandidateTest.id == data2["candidate_test_id"])
    ).first()
    assert candidate_test_2 is not None
    stored_ids_2 = candidate_test_2.question_revision_ids
    assert len(stored_ids_2) == 3
    assert set(stored_ids_2).issubset(set(all_question_ids))
    get_response2 = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_2.id}",
        params={"candidate_uuid": data2["candidate_uuid"]},
    )
    assert get_response2.status_code == 200
    returned_ids_2 = [q["id"] for q in get_response2.json()["question_revisions"]]
    assert returned_ids_2 == stored_ids_2
    assert stored_ids != stored_ids_2
    assert len(stored_ids) == len(stored_ids_2)


def test_candidate_test_question_ids_in_order(
    client: TestClient, db: SessionDep
) -> None:
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(),
        description="Should return questions in the same order",
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        shuffle=False,
        random_questions=False,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    inserted_question_ids = []
    for i in range(5):
        question = Question(
            created_by_id=user.id,
            organization_id=user.organization_id,
            is_active=True,
            is_deleted=False,
        )
        db.add(question)
        db.commit()
        db.refresh(question)

        revision = QuestionRevision(
            question_text=f"Q{i}",
            created_by_id=user.id,
            question_id=question.id,
            question_type="single_choice",
            options=[{"id": 1, "key": "A", "value": "Option A"}],
            correct_answer=[1],
        )
        db.add(revision)
        db.commit()
        db.refresh(revision)

        inserted_question_ids.append(revision.id)

        test_question = TestQuestion(test_id=test.id, question_revision_id=revision.id)
        db.add(test_question)
        db.commit()

    payload = {"test_id": test.id, "device_info": "Test Device"}
    response = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    assert response.status_code == 200
    data = response.json()

    candidate_test_id = data["candidate_test_id"]
    candidate_uuid = data["candidate_uuid"]

    candidate_test = db.exec(
        select(CandidateTest).where(CandidateTest.id == candidate_test_id)
    ).first()
    assert candidate_test is not None
    stored_ids = candidate_test.question_revision_ids
    get_response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_id}",
        params={"candidate_uuid": candidate_uuid},
    )
    assert get_response.status_code == 200
    returned_data = get_response.json()
    returned_questions = returned_data["question_revisions"]
    returned_ids = [q["id"] for q in returned_questions]
    assert stored_ids == inserted_question_ids
    assert returned_ids == inserted_question_ids
    response2 = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    assert response2.status_code == 200
    data2 = response2.json()
    candidate_test_id_2 = data2["candidate_test_id"]
    candidate_uuid_2 = data2["candidate_uuid"]

    candidate_test_2 = db.exec(
        select(CandidateTest).where(CandidateTest.id == candidate_test_id_2)
    ).first()
    assert candidate_test_2 is not None
    stored_ids_2 = candidate_test_2.question_revision_ids

    get_response_2 = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_id_2}",
        params={"candidate_uuid": candidate_uuid_2},
    )
    assert get_response_2.status_code == 200
    returned_ids_2 = [q["id"] for q in get_response_2.json()["question_revisions"]]
    assert stored_ids_2 == inserted_question_ids
    assert returned_ids_2 == inserted_question_ids
    assert returned_ids == returned_ids_2
