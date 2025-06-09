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


def test_create_question(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # First create an organization
    print(">>>> running updated test with new options >>>>")

    org_name = random_lower_string()
    org_response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": org_name},
        headers=get_user_superadmin_token,
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
        headers=get_user_superadmin_token,
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
        headers=get_user_superadmin_token,
    )
    tag_data = tag_response.json()
    tag_id = tag_data["id"]

    question_text = random_lower_string()
    question_data = {
        "organization_id": org_id,
        "created_by_id": user_id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
            {"id": 3, "key": "C", "text": "Option 3"},
        ],
        "correct_answer": [1],  # First option is correct
        "is_mandatory": True,
        "tag_ids": [tag_id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )
    data = response.json()
    print(response.status_code)
    print(response.json())

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


def test_read_questions(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
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
    response = client.get(
        f"{settings.API_V1_STR}/questions/", headers=get_user_superadmin_token
    )
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
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],  # Use dict format directly
        correct_answer=[1],
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
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],  # Use dict format directly
        correct_answer=[1, 2],
    )
    db.add(rev2)
    db.flush()

    q2.last_revision_id = rev2.id

    db.commit()
    db.refresh(q1)
    db.refresh(q2)

    # Get all questions
    response = client.get(
        f"{settings.API_V1_STR}/questions/", headers=get_user_superadmin_token
    )
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
    response = client.get(
        f"{settings.API_V1_STR}/questions/?tag_ids={tag.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["id"] == q1.id

    # Test filtering by created_by
    response = client.get(
        f"{settings.API_V1_STR}/questions/?created_by_id={user.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # Verify that filtering works
    response = client.get(
        f"{settings.API_V1_STR}/questions/?organization_id={org.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # Check pagination
    response = client.get(
        f"{settings.API_V1_STR}/questions/?limit=1", headers=get_user_superadmin_token
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data) <= 1


def test_read_question_by_id(client: TestClient, db: SessionDep) -> None:
    """
    Test the bulk upload of questions from CSV.

    This function tests various scenarios including
    valid uploads, invalid data, missing users, and empty files.
    """
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
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
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
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
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
        no_of_random_questions=10,
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
        no_of_random_questions=10,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test1)
    db.add(test2)
    db.flush()

    # Link question to tests
    test_question1 = TestQuestion(
        test_id=test1.id, question_id=q1.id, question_revision_id=rev1.id
    )
    test_question2 = TestQuestion(
        test_id=test2.id, question_id=q1.id, question_revision_id=rev1.id
    )
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
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Create a new revision with a different user
    new_text = random_lower_string()
    new_revision_data = {
        "created_by_id": user2.id,
        "question_text": new_text,
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
            {"id": 3, "key": "C", "text": "Option 3"},
        ],
        "correct_answer": [1, 2],
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
    assert new_rev is not None
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
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
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
        "options": [
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        "correct_answer": [1],
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
        "options": [
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        "correct_answer": [1],
        # Add location data with real IDs
        "state_ids": [kerala.id],  # remove district, block for now
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
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
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
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
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
        no_of_random_questions=10,
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
        question_revision_id=rev1.id,
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


def test_bulk_upload_questions(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # Create organization
    org_name = random_lower_string()
    org_response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": org_name},
        headers=get_user_superadmin_token,
    )
    org_data = org_response.json()
    org_id = org_data["id"]

    # Create user
    user = create_random_user(db)
    user.organization_id = org_id
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    # Create country and state
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)

    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()
    db.refresh(kerala)

    # Create tag type
    client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json={
            "name": "Test Tag Type",
            "description": "For testing",
            "created_by_id": user_id,
            "organization_id": org_id,
        },
        headers=get_user_superadmin_token,
    )

    # Create a CSV file with test data - add an empty row to test skipping
    # Also includes duplicate tags to test tag cache
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is 2+2?,4,3,5,6,A,Test Tag Type:Math,Kerala
What is the capital of France?,Paris,London,Berlin,Madrid,A,Test Tag Type:Geography,Kerala
What is H2O?,Water,Gold,Silver,Oxygen,A,Test Tag Type:Chemistry,Kerala
What are prime numbers?,Numbers divisible only by 1 and themselves,Even numbers,Odd numbers,Negative numbers,A,Test Tag Type:Math,Kerala
,,,,,,,
"""
    # Create temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        # Test with invalid user ID (test user not found)
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions.csv", file, "text/csv")},
                data={"user_id": "999999"},  # Non-existent user
            )
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

        # Test with completely empty CSV file (line 1015)
        empty_csv = ""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(empty_csv.encode("utf-8"))
            empty_csv_path = temp_file.name

        with open(empty_csv_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("empty.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )
        assert response.status_code in [400, 500]

        # Test with whitespace-only CSV (line 1029)
        whitespace_csv = "   \n  \t  "
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(whitespace_csv.encode("utf-8"))
            whitespace_csv_path = temp_file.name

        with open(whitespace_csv_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("whitespace.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )
        assert response.status_code in [400, 500]

        # Test with headers-only CSV (line 1045)
        headers_only_csv = "Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State\n"
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(headers_only_csv.encode("utf-8"))
            headers_only_csv_path = temp_file.name

        with open(headers_only_csv_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("headers_only.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )
        assert response.status_code in [400, 500]

        # Test with missing required columns
        invalid_csv = "Questions,Option A,Option B\n1,2,3"
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(invalid_csv.encode("utf-8"))
            invalid_csv_path = temp_file.name

        with open(invalid_csv_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("invalid.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )
        assert response.status_code in [400, 500]

        # Upload the valid CSV file
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )

        assert response.status_code == 200
        data = response.json()
        assert "Created" in data["message"]

        # Check that questions were created
        response = client.get(
            f"{settings.API_V1_STR}/questions/?organization_id={org_id}"
        )
        questions = response.json()
        assert len(questions) >= 4

        # Verify each question has its own set of option IDs starting from 1
        for question in questions:
            option_ids = [opt["id"] for opt in question["options"]]
            assert min(option_ids) == 1, (
                f"Question {question['id']} does not start with option ID 1"
            )
            assert max(option_ids) == len(option_ids), (
                f"Question {question['id']} has non-sequential option IDs"
            )
            assert len(set(option_ids)) == len(option_ids), (
                f"Question {question['id']} has duplicate option IDs"
            )

        # Check for specific question content
        question_texts = [q["question_text"] for q in questions]
        assert "What is 2+2?" in question_texts
        assert "What is the capital of France?" in question_texts
        assert "What is H2O?" in question_texts
        assert "What are prime numbers?" in question_texts

        # Check that duplicate tags are handled correctly (Math tag appears twice)
        math_tag_count = 0
        for question in questions:
            if question["question_text"] in ["What is 2+2?", "What are prime numbers?"]:
                if any(tag["name"] == "Math" for tag in question["tags"]):
                    math_tag_count += 1
        assert math_tag_count == 2  # Ensure both questions have Math tag

        # Check tags were correctly associated
        for question in questions:
            if question["question_text"] == "What is 2+2?":
                assert any(tag["name"] == "Math" for tag in question["tags"])
            elif question["question_text"] == "What is the capital of France?":
                assert any(tag["name"] == "Geography" for tag in question["tags"])
            elif question["question_text"] == "What is H2O?":
                assert any(tag["name"] == "Chemistry" for tag in question["tags"])
            elif question["question_text"] == "What are prime numbers?":
                assert any(tag["name"] == "Math" for tag in question["tags"])

        # Check locations were correctly associated
        for question in questions:
            locations = question["locations"]
            assert len(locations) > 0
            assert any(loc["state_name"] == "Kerala" for loc in locations)

        # Test with non-existent tag type
        csv_content_bad_tag = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is a prime number?,A number only divisible by 1 and itself,An even number,An odd number,A fractional number,A,NonExistentType:Math,Kerala
"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(csv_content_bad_tag.encode("utf-8"))
            bad_tag_path = temp_file.name

        with open(bad_tag_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("bad_tag.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )
        assert response.status_code == 200
        data = response.json()
        assert "Failed to create" in data["message"]

        # Test upload with non-existent state
        csv_content_bad_state = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is the highest mountain?,Everest,K2,Denali,Kilimanjaro,A,Test Tag Type:Geography,NonExistentState
"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(csv_content_bad_state.encode("utf-8"))
            temp_file_path_bad = temp_file.name

        with open(temp_file_path_bad, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions_bad_state.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )

        assert response.status_code == 200
        data = response.json()
        assert "Failed to create" in data["message"]
        assert "NonExistentState" in data["message"]

        # Clean up all temp files
        import os

        for path in [
            temp_file_path,
            empty_csv_path,
            whitespace_csv_path,
            headers_only_csv_path,
            invalid_csv_path,
            bad_tag_path,
            temp_file_path_bad,
        ]:
            if os.path.exists(path):
                os.unlink(path)

    finally:
        # Cleanup
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


# Test Case to check if the latest question revision is returned when fetching questions
def test_latest_question_revision(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    organization = Organization(name=random_lower_string())
    db.add(organization)
    db.commit()
    db.refresh(organization)

    # Create user for test
    user = create_random_user(db)
    db.refresh(user)

    question_text = random_lower_string()
    question_data = {
        "organization_id": organization.id,
        "created_by_id": user.id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
            {"id": 3, "key": "C", "text": "Option 3"},
        ],
        "correct_answer": [1],  # First option is correct
        "is_mandatory": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
    )
    assert response.status_code == 200, response.json()
    data_main_question = response.json()

    assert response.status_code == 200
    assert data_main_question["question_text"] == question_text
    assert data_main_question["question_type"] == QuestionType.single_choice
    assert len(data_main_question["options"]) == 3
    assert data_main_question["correct_answer"] == [1]  # First option is correct

    response = client.get(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}/revisions",
        headers=get_user_superadmin_token,
    )

    data_revision_1 = response.json()

    assert response.status_code == 200
    assert len(data_revision_1) == 1
    assert data_main_question["latest_question_revision_id"] == data_revision_1[0]["id"]
    assert data_main_question["question_text"] == data_revision_1[0]["text"]
    assert data_main_question["question_type"] == data_revision_1[0]["type"]
    assert data_main_question["created_by_id"] == data_revision_1[0]["created_by_id"]

    # Create a new revision with a different user
    user2 = create_random_user(db)
    new_revision_data = {
        "created_by_id": user2.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "text": "New Option 1"},
            {"id": 2, "key": "B", "text": "New Option 2"},
            {"id": 3, "key": "C", "text": "New Option 3"},
        ],
        "correct_answer": [1, 2],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}/revisions",
        json=new_revision_data,
    )
    assert response.status_code == 200, response.json()

    user3 = create_random_user(db)
    new_revision_data = {
        "created_by_id": user3.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "text": "New Option 1"},
            {"id": 2, "key": "B", "text": "New Option 2"},
            {"id": 3, "key": "C", "text": "New Option 3"},
        ],
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}/revisions",
        json=new_revision_data,
    )
    assert response.status_code == 200, response.json()
    response = client.get(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}/revisions",
        headers=get_user_superadmin_token,
    )

    data_revision_3 = response.json()

    assert response.status_code == 200
    assert len(data_revision_3) == 3

    max_revision_id = max(rev["id"] for rev in data_revision_3)

    response = client.get(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}",
        headers=get_user_superadmin_token,
    )
    data_latest_question = response.json()
    assert response.status_code == 200
    assert data_latest_question["latest_question_revision_id"] == max_revision_id

    response = client.get(
        f"{settings.API_V1_STR}/questions/revisions/{max_revision_id}",
        headers=get_user_superadmin_token,
    )
    data_latest_revision = response.json()
    assert response.status_code == 200
    assert data_latest_revision["question_id"] == data_main_question["id"]


def test_prepare_for_db_with_different_option_types(
    client: TestClient, db: SessionDep
) -> None:
    """Test prepare_for_db function with different option types and data structures."""
    from app.api.routes.question import prepare_for_db
    from app.models.question import QuestionCreate, Option

    # Test with dict-like options
    data1 = QuestionCreate(
        organization_id=1,
        created_by_id=1,
        question_text="Test question",
        question_type="single_choice",
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
        marking_scheme={"correct": 1, "wrong": 0},
        media={"type": "image", "url": "test.jpg"},
    )
    options1, marking_scheme1, media1 = prepare_for_db(data1)
    assert len(options1) == 2
    assert marking_scheme1 == {"correct": 1, "wrong": 0}
    assert media1 == {"type": "image", "url": "test.jpg"}

    # Test with Option model instances
    data2 = QuestionCreate(
        organization_id=1,
        created_by_id=1,
        question_text="Test question 2",
        question_type="single_choice",
        options=[
            Option(id=1, key="A", text="Option 1"),
            Option(id=2, key="B", text="Option 2"),
        ],
        correct_answer=[1],
        marking_scheme=None,
        media=None,
    )
    options2, marking_scheme2, media2 = prepare_for_db(data2)
    assert len(options2) == 2
    assert marking_scheme2 is None
    assert media2 is None

    # Test with options without IDs
    data3 = QuestionCreate(
        organization_id=1,
        created_by_id=1,
        question_text="Test question 3",
        question_type="single_choice",
        options=[{"key": "A", "text": "Option 1"}, {"key": "B", "text": "Option 2"}],
        correct_answer=[1],
    )
    options3, marking_scheme3, media3 = prepare_for_db(data3)
    assert len(options3) == 2
    assert options3[0]["id"] == 1
    assert options3[1]["id"] == 2


def test_get_revision_with_media(client: TestClient, db: SessionDep) -> None:
    """Test get_revision endpoint with media handling."""
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create question with revision containing media
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    media_data = {"type": "image", "url": "test.jpg", "alt_text": "Test image"}

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "text": "Option 1"},
            {"id": 2, "key": "B", "text": "Option 2"},
        ],
        correct_answer=[1],
        media=media_data,
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
    assert data["media"] == media_data


def test_bulk_upload_with_tag_type_errors(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    """Test bulk upload with tag type errors."""
    # Create organization
    org_name = random_lower_string()
    org_response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": org_name},
        headers=get_user_superadmin_token,
    )
    org_data = org_response.json()
    org_id = org_data["id"]

    # Create user
    user = create_random_user(db)
    user.organization_id = org_id
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    # Create country and state
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)

    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()
    db.refresh(kerala)

    # Create CSV with non-existent tag type
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is 2+2?,4,3,5,6,A,NonExistentType:Math,Kerala
What is the capital of France?,Paris,London,Berlin,Madrid,A,AnotherNonExistentType:Geography,Kerala
"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        # Upload the CSV file
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions.csv", file, "text/csv")},
                data={"user_id": str(user_id)},
            )

        assert response.status_code == 200
        data = response.json()
        assert "Failed to create" in data["message"]
        assert "NonExistentType" in data["message"]
        assert "AnotherNonExistentType" in data["message"]

    finally:
        # Clean up
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
