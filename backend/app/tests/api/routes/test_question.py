from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.candidate import Candidate, CandidateTest, CandidateTestAnswer
from app.models.location import Block, Country, District, State
from app.models.organization import Organization
from app.models.question import Question, QuestionRevision, QuestionTag, QuestionType
from app.models.tag import Tag, TagType
from app.models.test import Test, TestQuestion
from app.tests.utils.user import create_random_user
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

    user = create_random_user(db)
    user_id = user.id

    # Create a tag type
    tag_type_response = client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json={
            "name": "Test Tag Type",
            "description": "For testing",
            "created_by_id": user_id,
            "organization_id": org_id,
        },
    )
    tag_type_data = tag_type_response.json()
    tag_type_id = tag_type_data["id"]

    # Create a tag
    tag_response = client.post(
        f"{settings.API_V1_STR}/tag/",
        json={
            "name": "Test Tag",
            "description": "For testing questions",
            "tag_type_id": tag_type_id,
            "created_by_id": user_id,
            "organization_id": org_id,
        },
    )
    tag_data = tag_response.json()
    tag_id = tag_data["id"]

    question_text = random_lower_string()
    question_data = {
        "organization_id": org_id,
        "created_by_id": user_id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [{"text": "Option 1"}, {"text": "Option 2"}, {"text": "Option 3"}],
        "correct_answer": [0],  # First option is correct
        "is_mandatory": True,
        "tag_ids": [tag_id],
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
    # Check created_by_id
    assert data["created_by_id"] == user_id
    # Check tags
    assert len(data["tags"]) == 1
    assert data["tags"][0]["id"] == tag_id

    # Verify in the database
    question = db.get(Question, data["id"])
    assert question is not None
    assert question.organization_id == org_id

    # Check revision was created and has created_by_id
    revision = db.get(QuestionRevision, question.last_revision_id)
    assert revision is not None
    assert revision.question_text == question_text
    assert revision.created_by_id == user_id

    # Check tag relationships in database
    question_tags = db.exec(
        select(QuestionTag).where(QuestionTag.question_id == question.id)
    ).all()
    assert len(question_tags) == 1
    assert question_tags[0].tag_id == tag_id


def test_read_questions(client: TestClient, db: SessionDep) -> None:
    # Create test organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create test user
    user = create_random_user(db)
    db.refresh(user)
    db.refresh(user)

    # Create tag type and tag
    tag_type = TagType(
        name="Question Category",
        description="Categories for questions",
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tag = Tag(
        name="Math",
        description="Mathematics questions",
        tag_type_id=tag_type.id,
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    # Check empty list first
    response = client.get(f"{settings.API_V1_STR}/questions/")
    data = response.json()
    assert response.status_code == 200

    # Create two questions
    # First question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
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

    # Add tag to first question
    q1_tag = QuestionTag(
        question_id=q1.id,
        tag_id=tag.id,
    )
    db.add(q1_tag)

    # Second question
    q2 = Question(organization_id=org.id)
    db.add(q2)
    db.flush()

    rev2 = QuestionRevision(
        question_id=q2.id,
        created_by_id=user.id,
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
    assert len(data) >= 2

    # Check that the questions have the expected properties
    question_ids = [q["id"] for q in data]
    assert q1.id in question_ids
    assert q2.id in question_ids

    # Find q1 in response
    q1_data = next(q for q in data if q["id"] == q1.id)
    # Check created_by_id
    assert q1_data["created_by_id"] == user.id
    # Check tag information
    assert len(q1_data["tags"]) == 1
    assert q1_data["tags"][0]["id"] == tag.id

    # Test filtering by tag
    response = client.get(f"{settings.API_V1_STR}/questions/?tag_ids={tag.id}")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["id"] == q1.id

    # Test filtering by created_by
    response = client.get(f"{settings.API_V1_STR}/questions/?created_by_id={user.id}")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # Verify that filtering works
    response = client.get(f"{settings.API_V1_STR}/questions/?organization_id={org.id}")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # Check pagination
    response = client.get(f"{settings.API_V1_STR}/questions/?limit=1")
    data = response.json()
    assert response.status_code == 200
    assert len(data) <= 1


def test_read_question_by_id(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create tag type and tag
    tag_type = TagType(
        name="Question Category",
        description="Categories for questions",
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tag = Tag(
        name="History",
        description="History questions",
        tag_type_id=tag_type.id,
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    # Create question with revision and location
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    question_text = random_lower_string()
    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
        question_text=question_text,
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id

    # Add tag to question
    q1_tag = QuestionTag(
        question_id=q1.id,
        tag_id=tag.id,
    )
    db.add(q1_tag)

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
    # Check created_by_id
    assert data["created_by_id"] == user.id
    # Check tags
    assert len(data["tags"]) == 1
    assert data["tags"][0]["id"] == tag.id
    assert data["tags"][0]["name"] == "History"

    # Test non-existent question
    response = client.get(f"{settings.API_V1_STR}/questions/99999")
    assert response.status_code == 404


def test_update_question(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
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
    # Check created_by_id is preserved
    assert data["created_by_id"] == user.id

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

    # Create users - original creator and revision creator
    user1 = create_random_user(db)
    user2 = create_random_user(db)
    db.add(user1)
    db.add(user2)
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    # Create question with initial revision
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    initial_text = random_lower_string()
    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user1.id,
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

    # Create a new revision with a different user
    new_text = random_lower_string()
    new_revision_data = {
        "question_id": q1.id,
        "created_by_id": user2.id,
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
    # Check created_by_id is updated to user2
    assert data["created_by_id"] == user2.id

    # Verify in database
    db.refresh(q1)
    new_rev = db.get(QuestionRevision, q1.last_revision_id)
    assert new_rev.question_text == new_text
    assert new_rev.id != rev1.id
    assert new_rev.created_by_id == user2.id

    # Check revisions list
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}/revisions")
    revisions = response.json()

    assert response.status_code == 200
    assert len(revisions) == 2
    assert revisions[0]["id"] == new_rev.id
    assert revisions[0]["is_current"] is True
    assert revisions[0]["created_by_id"] == user2.id
    assert revisions[1]["id"] == rev1.id
    assert revisions[1]["is_current"] is False
    assert revisions[1]["created_by_id"] == user1.id


def test_get_revision(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create question with revision
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
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
    # Check created_by_id is included
    assert data["created_by_id"] == user.id
    # The is_current is a dynamic property added by the API, it's not part of the model
    # So we don't assert it here

    # Non-existent revision
    response = client.get(f"{settings.API_V1_STR}/questions/revisions/99999")
    assert response.status_code == 404


def test_question_tag_operations(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create tag type and tags
    tag_type = TagType(
        name="Question Category",
        description="Categories for questions",
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tag1 = Tag(
        name="Science",
        description="Science questions",
        tag_type_id=tag_type.id,
        created_by_id=user.id,
        organization_id=org.id,
    )
    tag2 = Tag(
        name="Physics",
        description="Physics questions",
        tag_type_id=tag_type.id,
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag1)
    db.add(tag2)
    db.commit()
    db.refresh(tag1)
    db.refresh(tag2)

    # Create question with one tag initially
    question_data = {
        "organization_id": org.id,
        "created_by_id": user.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [{"text": "Option 1"}, {"text": "Option 2"}],
        "correct_answer": [0],
        "tag_ids": [tag1.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )
    data = response.json()

    assert response.status_code == 200
    question_id = data["id"]

    # Verify initial tag
    assert len(data["tags"]) == 1
    assert data["tags"][0]["id"] == tag1.id

    # Add another tag
    response = client.post(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={
            "question_id": question_id,
            "tag_id": tag2.id,
        },
    )

    assert response.status_code == 200
    tag_data = response.json()
    assert tag_data["question_id"] == question_id
    assert tag_data["tag_id"] == tag2.id

    # Get question tags
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    tags = response.json()

    assert response.status_code == 200
    assert len(tags) == 2
    tag_ids = [tag["id"] for tag in tags]
    assert tag1.id in tag_ids
    assert tag2.id in tag_ids

    # Remove a tag
    response = client.delete(
        f"{settings.API_V1_STR}/questions/{question_id}/tags/{tag1.id}"
    )

    assert response.status_code == 200
    assert "removed" in response.json()["message"]

    # Verify tag was removed
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    tags = response.json()

    assert response.status_code == 200
    assert len(tags) == 1
    assert tags[0]["id"] == tag2.id


def test_question_location_operations(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

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

    question_data = {
        "organization_id": org.id,
        "created_by_id": user.id,  # Add created_by_id
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [{"text": "Option 1"}, {"text": "Option 2"}],
        "correct_answer": [0],
        # Add location data with real IDs
        "state_id": kerala.id,  # remove district, block for now
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["organization_id"] == org.id
    assert data["created_by_id"] == user.id
    assert len(data["locations"]) == 1
    assert data["locations"][0]["state_id"] == kerala.id
    assert data["locations"][0]["district_id"] is None
    assert data["locations"][0]["block_id"] is None

    # Test adding another location to the same question
    location_data = {
        "question_id": data["id"],  # Include the question_id field
        "state_id": None,
        "district_id": thrissur.id,
        "block_id": None,  # Test with a null block_id
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json=location_data,
    )

    assert response.status_code == 200, response.text
    location = response.json()
    assert location["state_id"] is None
    assert location["district_id"] == thrissur.id
    assert location["block_id"] is None

    # check for block location as well
    block_location_data = {
        "question_id": data["id"],
        "state_id": None,
        "district_id": None,
        "block_id": kovil.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json=block_location_data,
    )

    assert response.status_code == 200, response.text
    location = response.json()
    assert location["state_id"] is None
    assert location["district_id"] is None
    assert location["block_id"] == kovil.id

    # test location deletion endpoint
    response = client.get(f"{settings.API_V1_STR}/questions/{data['id']}")
    assert response.status_code == 200
    question = response.json()
    assert len(question["locations"]) == 3  # State, district, and block

    district_location_id = None
    for loc in question["locations"]:
        if loc["district_id"] == thrissur.id:
            district_location_id = loc["id"]
            break

    assert district_location_id is not None

    response = client.delete(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations/{district_location_id}"
    )
    assert response.status_code == 200
    assert "removed" in response.json()["message"]

    # Verify location was removed
    response = client.get(f"{settings.API_V1_STR}/questions/{data['id']}")
    assert response.status_code == 200
    question = response.json()
    assert len(question["locations"]) == 2  # Now only state and block

    # Verify we can still filter by location
    response = client.get(f"{settings.API_V1_STR}/questions/?state_ids={kerala.id}")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_delete_question(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
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


def test_get_question_candidate_tests(client: TestClient, db: SessionDep) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = create_random_user(db)
    db.refresh(user)

    # Create question
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
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
