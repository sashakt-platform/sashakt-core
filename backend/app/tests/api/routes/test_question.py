from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.candidate import Candidate, CandidateTest, CandidateTestAnswer
from app.models.location import Block, Country, District, State
from app.models.organization import Organization
from app.models.question import Question, QuestionRevision, QuestionType
from app.models.test import Test, TestQuestion
from app.models.user import User
from app.tests.utils.utils import random_email, random_lower_string


def test_create_question(client: TestClient, db: SessionDep) -> None:
    # First create an organization
    org_name = random_lower_string()
    org_response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": org_name},
    )
    org_data = org_response.json()
    org_id = org_data["id"]

    # Create a question
    question_text = random_lower_string()
    question_data = {
        "organization_id": org_id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [{"text": "Option 1"}, {"text": "Option 2"}, {"text": "Option 3"}],
        "correct_answer": [0],  # First option is correct
        "is_mandatory": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["question_text"] == question_text
    assert data["organization_id"] == org_id
    assert data["question_type"] == QuestionType.single_choice
    assert len(data["options"]) == 3
    assert "id" in data
    assert data["is_active"] is True
    assert not data["is_deleted"]

    # Verify in the database
    question = db.get(Question, data["id"])
    assert question is not None
    assert question.organization_id == org_id

    # Check revision was created
    revision = db.get(QuestionRevision, question.last_revision_id)
    assert revision is not None
    assert revision.question_text == question_text


def test_read_questions(client: TestClient, db: SessionDep) -> None:
    # Create test organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Check empty list first
    response = client.get(f"{settings.API_V1_STR}/questions/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    # Create two questions
    # First question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"text": "Option 1"},
            {"text": "Option 2"},
        ],  # Use dict format directly
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id

    # Second question
    q2 = Question(organization_id=org.id)
    db.add(q2)
    db.flush()

    rev2 = QuestionRevision(
        question_id=q2.id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[
            {"text": "Option A"},
            {"text": "Option B"},
            {"text": "Option C"},
        ],  # Use dict format directly
        correct_answer=[0, 1],
    )
    db.add(rev2)
    db.flush()

    q2.last_revision_id = rev2.id

    db.commit()
    db.refresh(q1)
    db.refresh(q2)

    # Get all questions
    response = client.get(f"{settings.API_V1_STR}/questions/")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2

    # Check that the questions have the expected properties
    question_ids = [q["id"] for q in data]
    assert q1.id in question_ids
    assert q2.id in question_ids

    # Verify that filtering works
    response = client.get(f"{settings.API_V1_STR}/questions/?organization_id={org.id}")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # Check pagination
    response = client.get(f"{settings.API_V1_STR}/questions/?limit=1")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1


def test_read_question_by_id(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question with revision and location
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    question_text = random_lower_string()
    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=question_text,
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Get question by ID
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == q1.id
    assert data["organization_id"] == org.id
    assert data["question_text"] == question_text
    assert data["question_type"] == QuestionType.single_choice
    assert len(data["options"]) == 2

    # Test non-existent question
    response = client.get(f"{settings.API_V1_STR}/questions/99999")
    assert response.status_code == 404


def test_update_question(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Update question (metadata only - is_active)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{q1.id}",
        json={"is_active": False},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == q1.id
    assert data["is_active"] is False

    # Check that the content hasn't changed
    assert data["question_text"] == rev1.question_text
    assert data["question_type"] == rev1.question_type

    # Verify in database
    db.refresh(q1)
    assert q1.is_active is False


def test_create_question_revision(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question with initial revision
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    initial_text = random_lower_string()
    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=initial_text,
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Create a new revision
    new_text = random_lower_string()
    new_revision_data = {
        "question_id": q1.id,
        "question_text": new_text,
        "question_type": QuestionType.multi_choice,
        "options": [
            {"text": "New Option 1"},
            {"text": "New Option 2"},
            {"text": "New Option 3"},
        ],
        "correct_answer": [0, 1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{q1.id}/revisions",
        json=new_revision_data,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == q1.id
    assert data["question_text"] == new_text
    assert data["question_type"] == QuestionType.multi_choice
    assert len(data["options"]) == 3

    # Verify in database
    db.refresh(q1)
    new_rev = db.get(QuestionRevision, q1.last_revision_id)
    assert new_rev.question_text == new_text
    assert new_rev.id != rev1.id

    # Check revisions list
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}/revisions")
    revisions = response.json()

    assert response.status_code == 200
    assert len(revisions) == 2
    assert revisions[0]["id"] == new_rev.id
    assert revisions[0]["is_current"] is True
    assert revisions[1]["id"] == rev1.id
    assert revisions[1]["is_current"] is False


def test_get_revision(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question with revision
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)
    db.refresh(rev1)

    # Get revision
    response = client.get(f"{settings.API_V1_STR}/questions/revisions/{rev1.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == rev1.id
    assert data["question_text"] == rev1.question_text
    assert data["question_type"] == rev1.question_type
    # The is_current is a dynamic property added by the API, it's not part of the model
    # So we don't assert it here

    # Non-existent revision
    response = client.get(f"{settings.API_V1_STR}/questions/revisions/99999")
    assert response.status_code == 404


def test_question_location_operations(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)

    # Set up location hierarchy similar to how it's done in test_location.py
    # Create country
    india = Country(name="India")
    db.add(india)
    db.commit()

    # Create state
    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()

    # Create districts
    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    thrissur = District(name="Thrissur", state_id=kerala.id)
    db.add(ernakulam)
    db.add(thrissur)
    db.commit()

    # Create blocks
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    mayani = Block(name="Mayani", district_id=ernakulam.id)
    db.add(kovil)
    db.add(mayani)
    db.commit()

    db.refresh(org)
    db.refresh(kerala)
    db.refresh(ernakulam)
    db.refresh(kovil)

    # Create question with initial location using proper IDs
    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [{"text": "Option 1"}, {"text": "Option 2"}],
        "correct_answer": [0],
        # Add location data with real IDs
        "state_id": kerala.id,
        "district_id": ernakulam.id,
        "block_id": kovil.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["organization_id"] == org.id
    assert len(data["locations"]) == 1
    assert data["locations"][0]["state_id"] == kerala.id
    assert data["locations"][0]["district_id"] == ernakulam.id
    assert data["locations"][0]["block_id"] == kovil.id

    # Test adding another location to the same question
    # Here's the fix - we need to include the question_id in the request
    location_data = {
        "question_id": data["id"],  # Include the question_id field
        "state_id": kerala.id,
        "district_id": thrissur.id,
        "block_id": None,  # Test with a null block_id
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json=location_data,
    )

    assert response.status_code == 200, response.text
    location = response.json()
    assert location["state_id"] == kerala.id
    assert location["district_id"] == thrissur.id
    assert location["block_id"] is None

    # Verify that both locations are returned when getting the question
    response = client.get(f"{settings.API_V1_STR}/questions/{data['id']}")
    assert response.status_code == 200
    question = response.json()
    assert len(question["locations"]) == 2


def test_delete_question(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Delete non-existent question
    response = client.delete(f"{settings.API_V1_STR}/questions/99999")
    assert response.status_code == 404

    # Delete question
    response = client.delete(f"{settings.API_V1_STR}/questions/{q1.id}")
    data = response.json()

    assert response.status_code == 200
    assert "deleted" in data["message"]

    # Verify in database
    db.refresh(q1)
    assert q1.is_deleted is True
    assert q1.is_active is False

    # Check that it's no longer accessible via API
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}")
    assert response.status_code == 404


def test_get_question_tests(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = User(
        full_name="Test User",
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Create a couple of tests
    test1 = Test(
        name="Test 1",
        organization_id=org.id,
        time_limit=60,  # Using time_limit instead of duration as in test_test.py
        marks=10,
        completion_message="Good job!",
        start_instructions="Read carefully",
        link="http://example.com/test1",
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_questions=10,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    test2 = Test(
        name="Test 2",
        organization_id=org.id,
        time_limit=30,  # Using time_limit instead of duration
        marks=20,
        completion_message="Well done!",
        start_instructions="Complete all questions",
        link="http://example.com/test2",
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_questions=10,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test1)
    db.add(test2)
    db.flush()

    # Link question to tests
    test_question1 = TestQuestion(test_id=test1.id, question_id=q1.id)
    test_question2 = TestQuestion(test_id=test2.id, question_id=q1.id)
    db.add(test_question1)
    db.add(test_question2)
    db.commit()

    # Get tests for question
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}/tests")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2

    # Verify test data
    test_ids = [test["id"] for test in data]
    assert test1.id in test_ids
    assert test2.id in test_ids

    # Check for test names
    test_names = [test["name"] for test in data]
    assert "Test 1" in test_names
    assert "Test 2" in test_names

    # Non-existent question
    response = client.get(f"{settings.API_V1_STR}/questions/99999/tests")
    assert response.status_code == 404


def test_get_question_candidate_tests(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = User(
        full_name="Test User",
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Create a candidate
    candidate = Candidate()
    db.add(candidate)
    db.flush()

    # Create a test with proper fields
    test = Test(
        name="Test 1",
        organization_id=org.id,
        time_limit=60,
        marks=10,
        completion_message="Good job!",
        start_instructions="Read carefully",
        link="http://example.com/test1",
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_questions=10,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.flush()

    # Create candidate test with end_time
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(hours=1)
    candidate_test = CandidateTest(
        candidate_id=candidate.id,
        test_id=test.id,
        device="web",
        consent=True,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(candidate_test)
    db.flush()

    # Link question to candidate test
    answer = CandidateTestAnswer(
        candidate_test_id=candidate_test.id,
        question_revision_id=q1.id,
        response="0",
        visited=True,
        time_spent=30,
    )
    db.add(answer)
    db.commit()

    # Get candidate tests for question
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}/candidate-tests")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 1

    # Verify candidate test data
    assert data[0]["id"] == candidate_test.id
    assert data[0]["candidate_id"] == candidate.id
    assert data[0]["test_id"] == test.id
    assert data[0]["is_submitted"] == candidate_test.is_submitted

    # Non-existent question
    response = client.get(f"{settings.API_V1_STR}/questions/99999/candidate-tests")
    assert response.status_code == 404
