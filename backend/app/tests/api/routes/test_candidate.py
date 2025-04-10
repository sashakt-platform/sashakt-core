from fastapi.testclient import TestClient

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
        no_of_questions=2,
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
        no_of_questions=2,
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
        no_of_questions=2,
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
        no_of_questions=2,
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
        no_of_questions=2,
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
        no_of_questions=2,
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
        no_of_questions=2,
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
        no_of_questions=2,
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
