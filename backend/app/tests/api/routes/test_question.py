from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.organization import Organization
from app.models.question import Question, QuestionRevision, QuestionType
from app.tests.utils.utils import random_lower_string


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
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
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
        options=[{"text": "Option A"}, {"text": "Option B"}, {"text": "Option C"}],
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

    # Check first question
    assert data[0]["id"] == q1.id
    assert data[0]["organization_id"] == org.id
    assert data[0]["question_text"] == rev1.question_text
    assert data[0]["question_type"] == QuestionType.single_choice
    assert len(data[0]["options"]) == 2

    # Check second question
    assert data[1]["id"] == q2.id
    assert data[1]["organization_id"] == org.id
    assert data[1]["question_text"] == rev2.question_text
    assert data[1]["question_type"] == QuestionType.multi_choice
    assert len(data[1]["options"]) == 3

    # Test filtering by organization
    response = client.get(
        f"{settings.API_V1_STR}/questions/", params={"organization_id": org.id}
    )
    data = response.json()
    assert len(data) == 2

    # Invalid organization filter should return empty list
    response = client.get(
        f"{settings.API_V1_STR}/questions/", params={"organization_id": 999999}
    )
    data = response.json()
    assert len(data) == 0


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
    assert data["is_current"] is True

    # Non-existent revision
    response = client.get(f"{settings.API_V1_STR}/questions/revisions/99999")
    assert response.status_code == 404


def test_question_location_operations(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create question with initial location
    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [{"text": "Option 1"}, {"text": "Option 2"}],
        "correct_answer": [0],
        # Add location data -- does this data exist in db?!
        "state_id": 1,
        "district_id": 2,
        "block_id": 3,
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["locations"]) == 1
    assert data["locations"][0]["state_id"] == 1
    assert data["locations"][0]["district_id"] == 2
    assert data["locations"][0]["block_id"] == 3

    # Add another location to the question
    location_data = {"question_id": data["id"], "state_id": 4, "district_id": 5}

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json=location_data,
    )
    location_data = response.json()

    assert response.status_code == 200
    assert location_data["state_id"] == 4
    assert location_data["district_id"] == 5
    assert location_data["block_id"] is None

    # Verify question now has two locations
    response = client.get(f"{settings.API_V1_STR}/questions/{data['id']}")
    updated_question = response.json()

    assert len(updated_question["locations"]) == 2

    # Test filtering by location
    response = client.get(f"{settings.API_V1_STR}/questions/", params={"state_id": 1})
    filtered_questions = response.json()

    assert len(filtered_questions) == 1
    assert filtered_questions[0]["id"] == data["id"]

    # Filter by a different state
    response = client.get(f"{settings.API_V1_STR}/questions/", params={"state_id": 4})
    filtered_questions = response.json()

    assert len(filtered_questions) == 1
    assert filtered_questions[0]["id"] == data["id"]

    # Filter by state and district
    response = client.get(
        f"{settings.API_V1_STR}/questions/", params={"state_id": 1, "district_id": 2}
    )
    filtered_questions = response.json()

    assert len(filtered_questions) == 1

    # Filter by non-existent location
    response = client.get(f"{settings.API_V1_STR}/questions/", params={"state_id": 999})
    filtered_questions = response.json()

    assert len(filtered_questions) == 0


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
