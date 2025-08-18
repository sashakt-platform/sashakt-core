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
from app.models.location import Country, District, State
from app.models.question import QuestionType
from app.models.tag import Tag, TagType
from app.models.test import TestDistrict, TestQuestion, TestState, TestTag
from app.tests.utils.organization import create_random_organization
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.user import create_random_user, get_current_user_data

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

    questions = [
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
    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_test_id = start_data["candidate_test_id"]
    candidate_uuid = start_data["candidate_uuid"]

    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test_id,
        question_revision_id=questions[0].id,
        response=2,
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test_id,
        question_revision_id=questions[1].id,  # Assuming question revision ID 1 exists
        response=2,
        visited=True,
        time_spent=30,
    )

    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test_id,
        question_revision_id=revision.id,
        response="2",
        visited=True,
        time_spent=30,
    )
    db.add(candidate_test_answer)
    db.commit()
    db.refresh(candidate_test_answer)
    candidate_test_answer = CandidateTestAnswer(
        candidate_test_id=candidate_test_id,
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
        f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
        headers=get_user_superadmin_token,
        params={"candidate_uuid": candidate_uuid},
    )

    assert response.status_code == 200
    data = response.json()

    # assert data["test_id"] == test.id
    assert data["correct_answer"] == 2
    assert data["incorrect_answer"] == 2
    assert data["mandatory_not_attempted"] == 0
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 2
    assert data["marks_maximum"] == 4


def test_get_score_and_time_test_not_found(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]
    tag_type = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.commit()
    db.refresh(tag_type)
    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tag_type.id,
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    resp = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?district_ids={district.id}",
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_avg_time_minutes"] == 0.0
    assert data["overall_avg_score"] == 0.0
    resp = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?state_ids={state.id}",
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_avg_time_minutes"] == 0.0
    assert data["overall_avg_score"] == 0.0
    response = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?tag_type_ids={tag_type.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["overall_avg_time_minutes"] == 0.0
    assert data["overall_avg_score"] == 0.0


def test_overall_avg_score_two_tests(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]
    tag_type = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.commit()
    db.refresh(tag_type)
    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tag_type.id,
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=False,
        marks_level="question",
        tag_ids=[tag.id],
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    test_tag_link = TestTag(test_id=test.id, tag_id=tag.id)
    db.add(test_tag_link)
    db.commit()

    revisions = []
    for i in range(5):
        question = Question(organization_id=org_id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user_id,
            "question_id": question.id,
            "question_text": f"Question {i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
            "marking_scheme": {"correct": 2, "wrong": -1, "skipped": 0},
        }
        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)

    for rev in revisions:
        db.add(TestQuestion(test_id=test.id, question_revision_id=rev.id))
    db.commit()

    candidate_answers = {
        "cand1": {
            1: [2],
            2: [2],
        },
        "cand2": {
            1: [2],
            2: [2],
            3: [2],
        },
        "cand3": {
            1: [2],
            2: [2],
            3: [2],
            4: [2],
            5: [1],
        },
        "cand4": {
            1: [2],
            2: [2],
            3: [2],
            4: [2],
        },
    }

    for cand_label, answers in candidate_answers.items():
        payload = {"test_id": test.id, "device_info": f"{cand_label}-device"}
        start_response = client.post(
            f"{settings.API_V1_STR}/candidate/start_test", json=payload
        )
        start_data = start_response.json()
        candidate_test_id = start_data["candidate_test_id"]
        candidate_uuid = start_data["candidate_uuid"]

        for q_idx, resp in answers.items():
            db.add(
                CandidateTestAnswer(
                    candidate_test_id=candidate_test_id,
                    question_revision_id=revisions[q_idx - 1].id,
                    response=resp,
                    visited=True,
                    time_spent=10,
                )
            )
        db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?tag_type_ids={tag_type.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_avg_score"] == 62.5

    test2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=False,
        marks_level="test",
        marking_scheme={"correct": 4, "wrong": -2, "skipped": 0},
        tag_ids=[tag.id],
    )
    db.add(test2)
    db.commit()
    db.refresh(test2)
    test_tag_link = TestTag(test_id=test2.id, tag_id=tag.id)
    db.add(test_tag_link)
    db.commit()

    revisions2 = []
    for i in range(5):
        question = Question(organization_id=org_id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision = QuestionRevision(
            created_by_id=user_id,
            question_id=question.id,
            question_text=f"Test2 Question {i + 1}",
            question_type=QuestionType.single_choice,
            options=[
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            correct_answer=[2],
            is_mandatory=True,
            is_active=True,
            is_deleted=False,
        )
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions2.append(revision)

    for rev in revisions2:
        db.add(TestQuestion(test_id=test2.id, question_revision_id=rev.id))
    db.commit()

    candidate_answers2 = {
        "cand1": {1: [2], 2: [2], 3: [2]},
        "cand2": {1: [2], 2: [2], 3: [2], 4: [2], 5: [1]},
        "cand3": {1: [2], 2: [2], 3: [2], 4: [2]},
        "cand4": {
            1: [2],
            2: [2],
            3: [2],
            4: [2],
            5: [2],
        },
    }

    for cand_label, answers in candidate_answers2.items():
        payload = {"test_id": test2.id, "device_info": f"{cand_label}-device"}
        start_response = client.post(
            f"{settings.API_V1_STR}/candidate/start_test", json=payload
        )
        start_data = start_response.json()
        candidate_test_id = start_data["candidate_test_id"]
        candidate_uuid = start_data["candidate_uuid"]

        for q_idx, resp in answers.items():
            db.add(
                CandidateTestAnswer(
                    candidate_test_id=candidate_test_id,
                    question_revision_id=revisions2[q_idx - 1].id,
                    response=resp,
                    visited=True,
                    time_spent=10,
                )
            )
        db.commit()

        response = client.get(
            f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
            params={"candidate_uuid": candidate_uuid},
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?tag_type_ids={tag_type.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_avg_score"] == 72.5


def test_overall_avg_time_two_tests(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    test1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=False,
        state_ids=[state.id],
        district_ids=[district.id],
    )
    db.add(test1)
    db.commit()
    db.refresh(test1)

    test_state_link = TestState(test_id=test1.id, state_id=state.id)
    db.add(test_state_link)
    db.commit()
    test_district_link = TestDistrict(test_id=test1.id, district_id=district.id)
    db.add(test_district_link)
    db.commit()

    test2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=False,
        state_ids=[state.id],
    )
    db.add(test2)
    db.commit()
    db.refresh(test2)
    test_state_link = TestState(test_id=test2.id, state_id=state.id)
    db.add(test_state_link)
    db.commit()

    t1_durations = [10, 12, 14, 25]
    t2_durations = [32, 20, 41, 45]

    for idx, mins in enumerate(t1_durations, start=1):
        resp = client.post(
            f"{settings.API_V1_STR}/candidate/start_test",
            json={"test_id": test1.id, "device_info": f"T1-cand{idx}"},
        )
        assert resp.status_code == 200
        cand_data = resp.json()
        cand_test_id = cand_data["candidate_test_id"]

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=mins)

        ct = db.get(CandidateTest, cand_test_id)
        assert ct is not None
        ct.start_time = start_time
        ct.end_time = end_time
        db.add(ct)
        db.commit()

    for idx, mins in enumerate(t2_durations, start=1):
        resp = client.post(
            f"{settings.API_V1_STR}/candidate/start_test",
            json={"test_id": test2.id, "device_info": f"T2-cand{idx}"},
        )
        assert resp.status_code == 200
        cand_data = resp.json()
        cand_test_id = cand_data["candidate_test_id"]

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=mins)

        ct = db.get(CandidateTest, cand_test_id)
        assert ct is not None
        ct.start_time = start_time
        ct.end_time = end_time
        db.add(ct)
        db.commit()

    resp = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?state_ids={state.id}",
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    data = resp.json()

    expected_avg_time = (sum(t1_durations) + sum(t2_durations)) / (
        len(t1_durations) + len(t2_durations)
    )

    assert data["overall_avg_time_minutes"] == expected_avg_time

    resp = client.get(
        f"{settings.API_V1_STR}/candidate/overall-analytics/?district_ids={district.id}",
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    data = resp.json()

    expected_avg_time = (sum(t1_durations)) / (len(t1_durations))

    assert data["overall_avg_time_minutes"] == expected_avg_time


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
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Test Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
        question_revision_ids=[revision.id, revision2.id],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

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
    assert data["marks_obtained"] == 1
    assert data["marks_maximum"] == 2


def test_result_with_mixed_answers_test_level_marking(
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
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        marks_level="test",
        marking_scheme={
            "correct": 5,
            "wrong": -2,
            "skipped": 0,
        },
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    revisions = []
    for i in range(3):
        question = Question(organization_id=org.id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user.id,
            "question_id": question.id,
            "question_text": f"Question {i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
        }
        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)
    for rev in revisions:
        test_question = TestQuestion(test_id=test.id, question_revision_id=rev.id)
        db.add(test_question)
        db.commit()
    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_test_id = start_data["candidate_test_id"]
    candidate_uuid = start_data["candidate_uuid"]

    # Q2: Correct
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test_id,
            question_revision_id=revisions[1].id,
            response=[2],
            visited=True,
            time_spent=10,
        )
    )

    # Q3: Wrong
    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test_id,
            question_revision_id=revisions[2].id,
            response=[1],
            visited=True,
            time_spent=10,
        )
    )

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
        params={"candidate_uuid": candidate_uuid},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    # 1 correct = +5, 1 wrong = -2, 1 skipped = 0
    assert data["correct_answer"] == 1
    assert data["incorrect_answer"] == 1
    assert data["mandatory_not_attempted"] == 1
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 3  # 5 - 2 + 0
    assert data["marks_maximum"] == 15  # 3 questions × 5 each


def test_result_with_mixed_answers_question_level_marking(
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
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Create candidate
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    revisions = []

    marking_schemes = [
        {"correct": 2, "wrong": -1, "skipped": 0},  # Q1
        {"correct": 5, "wrong": -2, "skipped": 0},  # Q2
        {"correct": 3, "wrong": -1, "skipped": 0},  # Q3
    ]

    for i in range(3):
        question = Question(organization_id=org.id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user.id,
            "question_id": question.id,
            "question_text": f"Q{i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
            "marking_scheme": marking_schemes[i],
        }
        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)
    for rev in revisions:
        test_question = TestQuestion(test_id=test.id, question_revision_id=rev.id)
        db.add(test_question)
        db.commit()
    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_test_id = start_data["candidate_test_id"]
    candidate_uuid = start_data["candidate_uuid"]

    # Candidate answers:
    db.add_all(
        [
            # Q2: Correct
            CandidateTestAnswer(
                candidate_test_id=candidate_test_id,
                question_revision_id=revisions[1].id,
                response=[2],
                visited=True,
                time_spent=5,
            ),
            # Q3: Wrong
            CandidateTestAnswer(
                candidate_test_id=candidate_test_id,
                question_revision_id=revisions[2].id,
                response=[1],
                visited=True,
                time_spent=5,
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
        params={"candidate_uuid": candidate_uuid},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["correct_answer"] == 1
    assert data["incorrect_answer"] == 1
    assert data["mandatory_not_attempted"] == 1
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 4  # 0+5-1
    assert data["marks_maximum"] == 10  # 2 + 5 + 3


def test_result_with_default_question_level_when_test_marks_level_not_set(
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
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Create candidate
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    revisions = []

    for i in range(3):
        question = Question(organization_id=org.id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user.id,
            "question_id": question.id,
            "question_text": f"Q{i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
        }

        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
        question_revision_ids=[rev.id for rev in revisions],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)
    # Candidate answers:
    db.add_all(
        [
            # Q1:Correct ( +10)
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[0].id,
                response=[2],
                visited=True,
                time_spent=5,
            ),
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[1].id,
                response="",
                visited=True,
                time_spent=5,
            ),
            # Q3: Wrong (default: 0)
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[2].id,
                response=[1],
                visited=True,
                time_spent=5,
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        params={"candidate_uuid": str(candidate.identity)},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["correct_answer"] == 1
    assert data["incorrect_answer"] == 1
    assert data["mandatory_not_attempted"] == 1
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 1
    assert data["marks_maximum"] == 3


def test_result_with_Marks_level_None(
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
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        marks_level=None,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    revisions = []

    for i in range(3):
        question = Question(organization_id=org.id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user.id,
            "question_id": question.id,
            "question_text": f"Q{i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
            "marking_scheme": None,
        }

        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
        question_revision_ids=[rev.id for rev in revisions],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    db.add_all(
        [
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[0].id,
                response=[2],
                visited=True,
                time_spent=5,
            ),
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[1].id,
                response="",
                visited=True,
                time_spent=5,
            ),
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[2].id,
                response=[1],
                visited=True,
                time_spent=5,
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        params={"candidate_uuid": str(candidate.identity)},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["correct_answer"] == 1
    assert data["incorrect_answer"] == 1
    assert data["mandatory_not_attempted"] == 1
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] is None
    assert data["marks_maximum"] is None


def test_result_with_some_questions_marks_scheme_None(
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
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        marks_level="question",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    revisions = []

    for i in range(3):
        question = Question(organization_id=org.id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user.id,
            "question_id": question.id,
            "question_text": f"Q{i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
            "marking_scheme": None
            if i < 1
            else {"correct": 2, "wrong": 0, "skipped": 0},
        }
        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
        question_revision_ids=[rev.id for rev in revisions],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    db.add_all(
        [
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[0].id,
                response=[2],
                visited=True,
                time_spent=5,
            ),
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[1].id,
                response=[2],
                visited=True,
                time_spent=5,
            ),
            CandidateTestAnswer(
                candidate_test_id=candidate_test.id,
                question_revision_id=revisions[2].id,
                response=[2],
                visited=True,
                time_spent=5,
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test.id}",
        params={"candidate_uuid": str(candidate.identity)},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["correct_answer"] == 3
    assert data["incorrect_answer"] == 0
    assert data["mandatory_not_attempted"] == 0
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 4
    assert data["marks_maximum"] == 4


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


def test_randomized_question_selection_and_result_calculation_with_mixed_answers(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    revisions = []

    marking_scheme = {"correct": 2, "wrong": -1, "skipped": 0}
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        marks_level="question",
        random_questions=True,
        no_of_random_questions=6,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    for i in range(10):
        question = Question(organization_id=org.id)
        db.add(question)
        db.commit()
        db.refresh(question)

        revision_data = {
            "created_by_id": user.id,
            "question_id": question.id,
            "question_text": f"Q{i + 1}",
            "question_type": QuestionType.single_choice,
            "options": [
                {"id": 1, "key": "A", "value": "Option A"},
                {"id": 2, "key": "B", "value": "Option B"},
                {"id": 3, "key": "C", "value": "Option C"},
            ],
            "correct_answer": [2],
            "is_mandatory": True,
            "is_active": True,
            "is_deleted": False,
            "marking_scheme": marking_scheme,
        }
        revision = QuestionRevision(**revision_data)
        db.add(revision)
        db.commit()
        db.refresh(revision)
        revisions.append(revision)

        test_question = TestQuestion(test_id=test.id, question_revision_id=revision.id)
        db.add(test_question)
        db.commit()
    payload = {"test_id": test.id, "device_info": "Test Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    candidate_test_id = start_data["candidate_test_id"]
    candidate_uuid = start_data["candidate_uuid"]
    candidate_test = db.exec(
        select(CandidateTest).where(CandidateTest.id == candidate_test_id)
    ).first()
    assert candidate_test is not None
    assigned_revision_ids = candidate_test.question_revision_ids

    responses_map = {
        assigned_revision_ids[0]: [2],
        assigned_revision_ids[1]: [1],
        assigned_revision_ids[2]: [2],
        assigned_revision_ids[3]: [3],
    }

    candidate_answers = [
        CandidateTestAnswer(
            candidate_test_id=candidate_test_id,
            question_revision_id=rev_id,
            response=responses_map.get(rev_id, []),
            visited=rev_id in responses_map,
            time_spent=5,
        )
        for rev_id in assigned_revision_ids
        if rev_id in responses_map
    ]
    db.add_all(candidate_answers)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
        params={"candidate_uuid": candidate_uuid},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["marks_maximum"] == 12
    assert data["correct_answer"] == 2
    assert data["incorrect_answer"] == 2
    assert data["mandatory_not_attempted"] == 2
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 2


def test_convert_to_list_with_int_response(
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
    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device="Test Device",
        consent=True,
        start_time="2025-02-10T10:00:00Z",
        end_time=None,
        is_submitted=True,
        question_revision_ids=[revision.id, revision2.id],
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)
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
    assert data["marks_obtained"] == 0
    assert data["marks_maximum"] == 2


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


def test_get_test_result_with_random_question_true(
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
        random_questions=True,
        show_result=True,
        no_of_random_questions=6,
        start_instructions="Test instructions",
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

    candidate_test_id = data["candidate_test_id"]
    candidate_uuid = data["candidate_uuid"]

    candidate_test = db.get(CandidateTest, candidate_test_id)
    assert candidate_test is not None
    candidate_test.is_submitted = True
    db.add(candidate_test)
    db.commit()
    selected_ids = candidate_test.question_revision_ids
    assert len(selected_ids) == 6
    for i, qid in enumerate(selected_ids):
        if i == 2:
            answer = CandidateTestAnswer(
                candidate_test_id=candidate_test_id,
                question_revision_id=qid,
                response="",
                visited=True,
                time_spent=10,
            )
        else:
            answer_value = [1] if i % 2 == 0 else [2]
            answer = CandidateTestAnswer(
                candidate_test_id=candidate_test_id,
                question_revision_id=qid,
                response=answer_value,
                visited=True,
                time_spent=30,
            )
        db.add(answer)
    db.commit()
    result_response = client.get(
        f"{settings.API_V1_STR}/candidate/result/{candidate_test_id}",
        headers=get_user_superadmin_token,
        params={"candidate_uuid": candidate_uuid},
    )
    assert result_response.status_code == 200
    data = result_response.json()
    assert data["correct_answer"] == 2
    assert data["incorrect_answer"] == 3
    assert data["mandatory_not_attempted"] == 1
    assert data["optional_not_attempted"] == 0
    assert data["marks_obtained"] == 2
    assert data["marks_maximum"] == 6


def test_test_level_marking_scheme_applied_on_questions(
    client: TestClient, db: SessionDep
) -> None:
    """Test the test_questions endpoint with candidate UUID verification."""
    user = create_random_user(db)
    org = create_random_organization(db)

    # Create question with revision
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="what is functions in cpp",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "3"},
            {"id": 2, "key": "B", "value": "4"},
            {"id": 3, "key": "C", "value": "5"},
        ],
        marking_scheme={"correct": 10, "wrong": -5, "skipped": 0},
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
        marks_level="test",
        marking_scheme={"correct": 5, "wrong": -1, "skipped": 1},
    )
    db.add(test)
    db.commit()

    # Link question to test

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision.id
    )
    db.add(test_question)
    db.commit()

    # Create candidate and candidate_test using start_test endpoint
    payload = {"test_id": test.id, "device_info": " Test Marks level Device"}
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
    assert "id" in data
    assert "name" in data
    assert "question_revisions" in data
    assert "candidate_test" in data
    assert data["id"] == test.id
    assert isinstance(data["question_revisions"], list)
    assert data["candidate_test"]["id"] == candidate_test_id
    for question_data in data["question_revisions"]:
        assert question_data["marking_scheme"] == test.marking_scheme


def test_question_level_marking_scheme_applied_on_questions(
    client: TestClient, db: SessionDep
) -> None:
    """Test that question-level marking scheme is applied when marks_level is 'question'."""
    user = create_random_user(db)
    org = create_random_organization(db)

    # Create question with custom marking scheme
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()

    question_level_scheme = {"correct": 3, "wrong": -2, "skipped": 0}

    question_revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user.id,
        question_text="Define polymorphism in C++",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Runtime"},
            {"id": 2, "key": "B", "value": "Compile-time"},
            {"id": 3, "key": "C", "value": "Both"},
        ],
        marking_scheme=question_level_scheme,
        correct_answer=[3],
    )
    db.add(question_revision)
    db.flush()

    question.last_revision_id = question_revision.id
    db.commit()
    db.refresh(question_revision)

    # Create test with marks_level = 'question'
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
        marks_level="question",
        marking_scheme={"correct": 5, "wrong": -1, "skipped": 1},  # should not be used
    )
    db.add(test)
    db.commit()

    # Link the question to the test
    from app.models.test import TestQuestion

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision.id
    )
    db.add(test_question)
    db.commit()

    # Start test
    payload = {"test_id": test.id, "device_info": "Question Marks level Device"}
    start_response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test", json=payload
    )
    start_data = start_response.json()
    identity = start_data["candidate_uuid"]
    candidate_test_id = start_data["candidate_test_id"]

    response = client.get(
        f"{settings.API_V1_STR}/candidate/test_questions/{candidate_test_id}",
        params={"candidate_uuid": identity},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test.id
    assert isinstance(data["question_revisions"], list)
    assert data["candidate_test"]["id"] == candidate_test_id

    for question_data in data["question_revisions"]:
        assert question_data["marking_scheme"] == question_level_scheme


def test_submitted_candidate_with_end_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    resp_before = client.get(
        f"{settings.API_V1_STR}/candidate/summary", headers=get_user_superadmin_token
    )
    assert resp_before.status_code == 200
    before = resp_before.json()

    fake_now = datetime(2025, 8, 8, 12, 0, 0)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=30,
            marks=100,
            start_time="2025-07-01T12:00:00Z",
            end_time="2025-08-10T12:00:00Z",
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=True,
                start_time=datetime(2025, 8, 8, 10, 0),
                end_time=datetime(2025, 8, 8, 11, 0),
                device="laptop",
                consent=True,
            )
        )
        db.commit()
        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 1
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 0
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 0


def test_candidate_active_before_end_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    resp_before = client.get(
        f"{settings.API_V1_STR}/candidate/summary", headers=get_user_superadmin_token
    )
    assert resp_before.status_code == 200
    before = resp_before.json()

    fake_now = datetime(2025, 8, 8, 10, 45)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=None,
            marks=100,
            start_time=datetime(2025, 8, 8, 10, 0),
            end_time=datetime(2025, 8, 8, 12, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 10, 15),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 1
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 0


def test_candidate_active_inside_time_limit(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 11, 15)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()
        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=90,
            marks=100,
            start_time=datetime(2025, 8, 8, 10, 0),
            end_time=datetime(2025, 8, 8, 12, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 10, 30),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 1
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 0


def test_candidate_active_no_start_end(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 10, 15)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=None,
            marks=100,
            start_time=None,
            end_time=None,
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 9, 45),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 1
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 0


def test_candidate_active_inside_60_min_before_end(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 3, 15)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=60,
            marks=100,
            start_time=datetime(2025, 8, 8, 2, 0),
            end_time=datetime(2025, 8, 8, 4, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 2, 30),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 1
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 0


def test_candidate_inactive_past_end_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 12, 5)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=None,
            marks=100,
            start_time=datetime(2025, 8, 8, 10, 0),
            end_time=datetime(2025, 8, 8, 12, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 10, 30),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 1


def test_candidate_inactive_time_limit_exceeded(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 11, 15)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=60,
            marks=100,
            start_time=datetime(2025, 8, 8, 10, 0),
            end_time=datetime(2025, 8, 8, 12, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 10, 0),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 1


def test_candidate_inactive_time_limit_exceeded_no_test_end(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 10, 45)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=90,
            marks=100,
            start_time=None,
            end_time=None,
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 9, 0),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 1


def test_candidate_inactive_past_end_time_no_time_limit(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 15, 10)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=None,
            marks=100,
            start_time=datetime(2025, 8, 8, 14, 0),
            end_time=datetime(2025, 8, 8, 15, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 14, 15),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 1


def test_candidate_with_end_time_counted_as_submitted(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 15, 10)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=None,
            marks=100,
            start_time=datetime(2025, 8, 8, 14, 0),
            end_time=datetime(2025, 8, 8, 15, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 14, 15),
                end_time=datetime(2025, 8, 8, 14, 45),
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 1
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 0
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 0


def test_candidate_inactive_due_to_time_limit_exceeded(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    fake_now = datetime(2025, 8, 8, 11, 15)
    with patch("app.api.routes.candidate.get_current_time", return_value=fake_now):
        resp_before = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_before.status_code == 200
        before = resp_before.json()

        active_test = Test(
            name=random_lower_string(),
            description=random_lower_string(),
            time_limit=60,
            marks=100,
            start_time=datetime(2025, 8, 8, 10, 0),
            end_time=datetime(2025, 8, 8, 12, 0),
            is_template=False,
            created_by_id=user_id,
            link=random_lower_string(),
        )
        db.add(active_test)
        db.commit()

        candidate = Candidate(user_id=user_id)
        db.add(candidate)
        db.commit()

        db.add(
            CandidateTest(
                test_id=active_test.id,
                candidate_id=candidate.id,
                is_submitted=False,
                start_time=datetime(2025, 8, 8, 10, 0),
                end_time=None,
                device="laptop",
                consent=True,
            )
        )
        db.commit()

        resp_after = client.get(
            f"{settings.API_V1_STR}/candidate/summary",
            headers=get_user_superadmin_token,
        )
        assert resp_after.status_code == 200
        after = resp_after.json()

        assert after["total_test_submitted"] - before["total_test_submitted"] == 0
        assert (
            after["total_test_not_submitted"] - before["total_test_not_submitted"] == 1
        )
        assert after["not_submitted_active"] - before["not_submitted_active"] == 0
        assert after["not_submitted_inactive"] - before["not_submitted_inactive"] == 1


def test_candidate_summary_invalid_date_range(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    start_date = "2025-08-10T10:00:00"
    end_date = "2025-08-09T10:00:00"
    response = client.get(
        f"{settings.API_V1_STR}/candidate/summary",
        headers=get_user_superadmin_token,
        params={"start_date": start_date, "end_date": end_date},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "End date must be after start date"
