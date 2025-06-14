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
    assert data["is_active"] is None
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
    assert data["is_active"] is None
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
    assert data["is_active"] is None
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
    assert data["is_active"] is None
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
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
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
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )

    question_revision_b = QuestionRevision(
        question_id=question_b.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[{"text": "Option A"}, {"text": "Option B"}, {"text": "Option C"}],
        correct_answer=[0, 1],
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
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )

    question_revision_b = QuestionRevision(
        question_id=question_b.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[{"text": "Option A"}, {"text": "Option B"}, {"text": "Option C"}],
        correct_answer=[0, 1],
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
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )

    question_revision_b = QuestionRevision(
        question_id=question_b.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[{"text": "Option A"}, {"text": "Option B"}, {"text": "Option C"}],
        correct_answer=[0, 1],
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
        options=[{"text": "3"}, {"text": "4"}, {"text": "5"}],
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
        options=[{"text": "5"}, {"text": "6"}, {"text": "7"}],
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
        options=[{"text": "7"}, {"text": "8"}, {"text": "9"}],
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
        options=[{"text": "9"}, {"text": "10"}, {"text": "11"}],
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
