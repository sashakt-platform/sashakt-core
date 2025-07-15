import base64
import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.candidate import Candidate, CandidateTest, CandidateTestAnswer
from app.models.location import Block, Country, District, State
from app.models.organization import Organization
from app.models.question import (
    Question,
    QuestionLocation,
    QuestionRevision,
    QuestionTag,
    QuestionType,
)
from app.models.tag import Tag, TagType
from app.models.test import Test, TestQuestion

# from app.models.user import User
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import random_lower_string


def test_create_question(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # First create an organization
    org_name = random_lower_string()
    org_response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": org_name},
        headers=get_user_superadmin_token,
    )
    org_data = org_response.json()
    org_id = org_data["id"]
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    # Create a tag type
    tag_type_response = client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json={
            "name": "Test Tag Type",
            "description": "For testing",
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
            "organization_id": org_id,
        },
        headers=get_user_superadmin_token,
    )
    tag_data = tag_response.json()
    tag_id = tag_data["id"]

    question_text = random_lower_string()
    question_data = {
        "organization_id": org_id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1],  # First option is correct
        "is_mandatory": True,
        "tag_ids": [tag_id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
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


def test_read_questions(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    # Create test organization

    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]

    # Create tag type and tag
    tag_type = TagType(
        name="Question Category",
        description="Categories for questions",
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(tag_type)
    db.flush()

    tag = Tag(
        name="Math",
        description="Mathematics questions",
        tag_type_id=tag_type.id,
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    # Check empty list first
    response = client.get(
        f"{settings.API_V1_STR}/questions/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200

    # Create two questions
    # First question
    q1 = Question(organization_id=org_id)
    db.add(q1)
    db.flush()

    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user_id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],  # Use dict format directly
        correct_answer=[2],
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
    q2 = Question(organization_id=org_id)
    db.add(q2)
    db.flush()

    rev2 = QuestionRevision(
        question_id=q2.id,
        created_by_id=user_id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
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
        f"{settings.API_V1_STR}/questions/",
        headers=get_user_superadmin_token,
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
    assert q1_data["created_by_id"] == user_id
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
        f"{settings.API_V1_STR}/questions/?created_by_id={user_id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # Verify that filtering works
    response = client.get(
        f"{settings.API_V1_STR}/questions/?organization_id={org_id}",
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
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
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


def test_update_question(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
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
        headers=get_user_superadmin_token,
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


def test_create_question_revision(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create users - original creator and revision creator
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    # Create question with initial revision
    q1 = Question(organization_id=org.id)
    db.add(q1)
    db.flush()

    initial_text = random_lower_string()
    rev1 = QuestionRevision(
        question_id=q1.id,
        created_by_id=user_id,
        question_text=initial_text,
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[2],
    )
    db.add(rev1)
    db.flush()

    q1.last_revision_id = rev1.id
    db.commit()
    db.refresh(q1)

    # Create a new revision with a different user
    new_text = random_lower_string()
    new_revision_data = {
        "question_text": new_text,
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1, 3],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{q1.id}/revisions",
        json=new_revision_data,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == q1.id
    assert data["question_text"] == new_text
    assert data["question_type"] == QuestionType.multi_choice
    assert len(data["options"]) == 3
    # Check created_by_id is updated to user2
    assert data["created_by_id"] == user_id

    # Verify in database
    db.refresh(q1)
    new_rev = db.get(QuestionRevision, q1.last_revision_id)
    assert new_rev is not None
    assert new_rev.question_text == new_text
    assert new_rev.id != rev1.id
    assert new_rev.created_by_id == user_id

    # Check revisions list
    response = client.get(f"{settings.API_V1_STR}/questions/{q1.id}/revisions")
    revisions = response.json()

    assert response.status_code == 200
    assert len(revisions) == 2
    assert revisions[0]["id"] == new_rev.id
    assert revisions[0]["is_current"] is True
    assert revisions[0]["created_by_id"] == user_id
    assert revisions[1]["id"] == rev1.id
    assert revisions[1]["is_current"] is False
    assert revisions[1]["created_by_id"] == user_id


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
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
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


def test_question_tag_operations(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    # Create tag type and tags
    tag_type = TagType(
        name="Question Category",
        description="Categories for questions",
        created_by_id=user_id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tag1 = Tag(
        name="Science",
        description="Science questions",
        tag_type_id=tag_type.id,
        created_by_id=user_id,
        organization_id=org.id,
    )
    tag2 = Tag(
        name="Physics",
        description="Physics questions",
        tag_type_id=tag_type.id,
        created_by_id=user_id,
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
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        "correct_answer": [2],
        "tag_ids": [tag1.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    question_id = data["id"]

    # Verify initial tag
    assert len(data["tags"]) == 1
    assert data["tags"][0]["id"] == tag1.id

    # Add another tag using PUT (sync approach)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={
            "tag_ids": [tag1.id, tag2.id],  # Keep tag1, add tag2
        },
    )

    assert response.status_code == 200
    updated_tags = response.json()
    assert len(updated_tags) == 2
    tag_ids = {tag["id"] for tag in updated_tags}
    assert tag_ids == {tag1.id, tag2.id}

    # Get question tags to verify
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    tags = response.json()

    assert response.status_code == 200
    assert len(tags) == 2
    tag_ids = {tag["id"] for tag in tags}
    assert tag1.id in tag_ids
    assert tag2.id in tag_ids

    # Remove a tag using PUT (sync approach)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={
            "tag_ids": [tag2.id],  # Keep only tag2, remove tag1
        },
    )

    assert response.status_code == 200
    updated_tags = response.json()
    assert len(updated_tags) == 1
    assert updated_tags[0]["id"] == tag2.id

    # Verify tag was removed
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    tags = response.json()

    assert response.status_code == 200
    assert len(tags) == 1
    assert tags[0]["id"] == tag2.id


def test_question_location_operations(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    # Create organization

    # Create user
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]
    # Set up location hierarchy similar to how it's done in test_location.py
    # Create country
    india = Country(name="India")
    db.add(india)
    db.commit()

    # Create state
    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()
    db.refresh(kerala)

    # Create districts
    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    thrissur = District(name="Thrissur", state_id=kerala.id)
    db.add(ernakulam)
    db.add(thrissur)
    db.commit()
    db.refresh(ernakulam)
    db.refresh(thrissur)

    # Create blocks
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    mayani = Block(name="Mayani", district_id=ernakulam.id)
    db.add(kovil)
    db.add(mayani)
    db.commit()
    db.refresh(kovil)

    question_data = {
        "organization_id": org_id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        "correct_answer": [2],
        # Add location data with real IDs
        "state_ids": [kerala.id],  # remove district, block for now
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["organization_id"] == org_id
    assert data["created_by_id"] == user_id
    assert len(data["locations"]) == 1
    assert data["locations"][0]["state_id"] == kerala.id
    assert data["locations"][0]["district_id"] is None
    assert data["locations"][0]["block_id"] is None

    # Test adding another location using PUT (sync approach)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json={
            "locations": [
                {
                    "state_id": kerala.id,
                    "district_id": None,
                    "block_id": None,
                },  # Keep existing state
                {
                    "state_id": None,
                    "district_id": thrissur.id,
                    "block_id": None,
                },  # Add district
            ]
        },
    )

    assert response.status_code == 200, response.text
    location_list = response.json()
    assert isinstance(location_list, list)
    assert len(location_list) == 2

    # Verify we have both state and district locations
    state_locations = [loc for loc in location_list if loc["state_id"] is not None]
    district_locations = [
        loc for loc in location_list if loc["district_id"] is not None
    ]
    assert len(state_locations) == 1
    assert len(district_locations) == 1
    assert state_locations[0]["state_id"] == kerala.id
    assert district_locations[0]["district_id"] == thrissur.id

    # Add block location as well using PUT
    response = client.put(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json={
            "locations": [
                {
                    "state_id": kerala.id,
                    "district_id": None,
                    "block_id": None,
                },  # Keep state
                {
                    "state_id": None,
                    "district_id": thrissur.id,
                    "block_id": None,
                },  # Keep district
                {
                    "state_id": None,
                    "district_id": None,
                    "block_id": kovil.id,
                },  # Add block
            ]
        },
    )

    assert response.status_code == 200, response.text
    location_list = response.json()
    assert isinstance(location_list, list)
    assert len(location_list) == 3

    # Find the block location
    block_locations = [loc for loc in location_list if loc["block_id"] is not None]
    assert len(block_locations) == 1
    assert block_locations[0]["block_id"] == kovil.id

    # Test location removal using PUT (by excluding from the list)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{data['id']}/locations",
        json={
            "locations": [
                {
                    "state_id": kerala.id,
                    "district_id": None,
                    "block_id": None,
                },  # Keep state
                {
                    "state_id": None,
                    "district_id": None,
                    "block_id": kovil.id,
                },  # Keep block, remove district
            ]
        },
    )
    assert response.status_code == 200

    location_list = response.json()
    assert len(location_list) == 2  # Now only state and block

    # Verify we can still filter by location
    response = client.get(
        f"{settings.API_V1_STR}/questions/?state_ids={kerala.id}",
        headers=get_user_superadmin_token,
    )
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
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[2],
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
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
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

    # Create user

    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    # Create country and state
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)

    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()
    db.refresh(punjab)

    # Create tag type
    response = client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json={
            "name": "Test Tag Type",
            "description": "For testing",
            "organization_id": org_id,
        },
        headers=get_user_superadmin_token,
    )

    # Create a CSV file with test data - add an empty row to test skipping
    # Also includes duplicate tags to test tag cache
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is 2+2?,4,3,5,6,A,Test Tag Type:Math,Punjab
What is the capital of France?,Paris,London,Berlin,Madrid,A,Test Tag Type:Geography,Punjab
What is H2O?,Water,Gold,Silver,Oxygen,A,Test Tag Type:Chemistry,Punjab
What are prime numbers?,Numbers divisible only by 1 and themselves,Even numbers,Odd numbers,Negative numbers,A,Test Tag Type:Math,Punjab
,,,,,,,
"""

    # Create a temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        empty_csv = ""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(empty_csv.encode("utf-8"))
            empty_csv_path = temp_file.name

        with open(empty_csv_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("empty.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
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
                headers=get_user_superadmin_token,
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
                headers=get_user_superadmin_token,
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
                headers=get_user_superadmin_token,
            )
        assert response.status_code in [400, 500]

        # Upload the valid CSV file
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 200
        data = response.json()

        assert "Created" in data["message"]

        # Check that questions were created
        response = client.get(
            f"{settings.API_V1_STR}/questions/",
            headers=get_user_superadmin_token,
        )
        questions = response.json()
        assert len(questions) >= 4  # Updated to reflect 4 questions

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

        for question in questions:
            # Check locations were correctly associated
            if question["question_text"] in [
                "What is 2+2?",
                "What is the capital of France?",
                "What is H2O?",
                "What are prime numbers?",
            ]:
                locations = question["locations"]
                assert len(locations) > 0
                assert any(loc["state_name"] == "Punjab" for loc in locations)

        # Test with non-existent tag type
        csv_content_bad_tag = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is a prime number?,A number only divisible by 1 and itself,An even number,An odd number,A fractional number,A,NonExistentType:Math,Punjab
"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
            temp_file.write(csv_content_bad_tag.encode("utf-8"))
            bad_tag_path = temp_file.name

        with open(bad_tag_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("bad_tag.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
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
                headers=get_user_superadmin_token,
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
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    question_text = random_lower_string()
    question_data = {
        "organization_id": organization.id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [2],  # First option is correct
        "is_mandatory": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    data_main_question = response.json()

    assert response.status_code == 200
    assert data_main_question["question_text"] == question_text
    assert data_main_question["question_type"] == QuestionType.single_choice
    assert len(data_main_question["options"]) == 3
    assert data_main_question["correct_answer"] == [2]  # First option is correct

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
    assert data_main_question["created_by_id"] == user_id

    # Create a new revision with a different user

    new_revision_data = {
        "question_text": random_lower_string(),
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1, 2],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}/revisions",
        json=new_revision_data,
        headers=get_user_superadmin_token,
    )

    new_revision_data = {
        "question_text": random_lower_string(),
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "value": "New Option 1"},
            {"id": 2, "key": "B", "value": "New Option 2"},
            {"id": 3, "key": "C", "value": "New Option 3"},
        ],
        "correct_answer": [2],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{data_main_question['id']}/revisions",
        json=new_revision_data,
        headers=get_user_superadmin_token,
    )

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


def test_invalid_correct_option(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = create_random_user(db)
    db.refresh(user)

    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        # Invalid correct answer index
        "correct_answer": [3],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 422
    assert "does not match" in response.json()["detail"][0]["msg"]


def test_valid_correct_option(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = create_random_user(db)
    db.refresh(user)

    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        # Invalid correct answer index
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert "correct_answer" in data

    assert isinstance(data["correct_answer"], list)
    assert len(data["correct_answer"]) == 1
    assert data["correct_answer"][0] == 1
    option_ids = [opt["id"] for opt in data["options"]]
    assert data["correct_answer"][0] in option_ids, (
        "Correct answer must be one of the option IDs"
    )


def test_valid_ids_option(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = create_random_user(db)
    db.refresh(user)

    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 1, "key": "B", "value": "Option 2"},
            {"id": 1, "key": "B", "value": "Option 2"},
        ],
        # Invalid correct answer index
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 422


def test_duplicate_option_ids_error_message(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user for test
    user = create_random_user(db)
    db.refresh(user)

    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 1, "key": "B", "value": "Option 2"},  # Duplicate ID
        ],
        # Invalid correct answer index
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 422
    assert "Option IDs must be unique" in response.json()["detail"][0]["msg"]


def test_bulk_tag_operations(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test bulk adding and removing tags."""
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Create tag type and multiple tags
    tag_type = TagType(
        name="Bulk Test Category",
        description="Categories for bulk testing",
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tags = []
    for i in range(5):
        tag = Tag(
            name=f"BulkTag{i}",
            description=f"Bulk test tag {i}",
            tag_type_id=tag_type.id,
            created_by_id=user.id,
            organization_id=org.id,
        )
        db.add(tag)
        tags.append(tag)

    db.commit()
    for tag in tags:
        db.refresh(tag)

    # Create question
    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    question_id = response.json()["id"]

    # Test bulk add tags using PUT
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={"tag_ids": [tags[0].id, tags[1].id, tags[2].id]},
    )

    assert response.status_code == 200
    tag_results = response.json()
    assert isinstance(tag_results, list)
    assert len(tag_results) == 3

    # Verify all tags were added
    tag_ids = {tag["id"] for tag in tag_results}
    assert tag_ids == {tags[0].id, tags[1].id, tags[2].id}

    # Verify question has all the tags
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    current_tags = response.json()
    assert len(current_tags) == 3

    # Test adding more tags (should replace the existing set)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={
            "tag_ids": [tags[0].id, tags[3].id]
        },  # Keep tags[0], remove tags[1,2], add tags[3]
    )

    assert response.status_code == 200
    tag_results = response.json()
    assert len(tag_results) == 2
    tag_ids = {tag["id"] for tag in tag_results}
    assert tag_ids == {tags[0].id, tags[3].id}

    # Verify we now have 2 tags total
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    current_tags = response.json()
    assert len(current_tags) == 2

    # Test bulk remove tags by setting to subset
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={"tag_ids": [tags[3].id]},  # Keep only tags[3]
    )

    assert response.status_code == 200
    tag_results = response.json()
    assert len(tag_results) == 1
    assert tag_results[0]["id"] == tags[3].id

    # Verify tags were removed
    response = client.get(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        headers=get_user_superadmin_token,
    )
    current_tags = response.json()
    assert len(current_tags) == 1
    assert current_tags[0]["id"] == tags[3].id


def test_bulk_location_operations(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test bulk adding and removing locations."""
    # Create organization
    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create user
    user = create_random_user(db)
    db.refresh(user)

    # Set up location hierarchy
    india = Country(name="India")
    db.add(india)
    db.commit()

    states = []
    districts = []
    blocks = []

    # Create multiple states
    for i in range(3):
        state = State(name=f"State{i}", country_id=india.id)
        db.add(state)
        states.append(state)

    db.commit()
    for state in states:
        db.refresh(state)

    # Create multiple districts for the first state
    for i in range(3):
        district = District(name=f"District{i}", state_id=states[0].id)
        db.add(district)
        districts.append(district)

    db.commit()
    for district in districts:
        db.refresh(district)

    # Create multiple blocks for the first district
    for i in range(3):
        block = Block(name=f"Block{i}", district_id=districts[0].id)
        db.add(block)
        blocks.append(block)

    db.commit()
    for block in blocks:
        db.refresh(block)

    # Create question
    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    question_id = response.json()["id"]

    # Test bulk add locations using PUT
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/locations",
        json={
            "locations": [
                {
                    "state_id": states[0].id,
                    "district_id": None,
                    "block_id": None,
                },
                {
                    "state_id": states[1].id,
                    "district_id": None,
                    "block_id": None,
                },
                {
                    "state_id": None,
                    "district_id": districts[0].id,
                    "block_id": None,
                },
                {
                    "state_id": None,
                    "district_id": None,
                    "block_id": blocks[0].id,
                },
            ]
        },
    )

    assert response.status_code == 200
    location_results = response.json()
    assert isinstance(location_results, list)
    assert len(location_results) == 4

    # Verify all location types were added
    has_state0 = any(loc["state_id"] == states[0].id for loc in location_results)
    has_state1 = any(loc["state_id"] == states[1].id for loc in location_results)
    has_district0 = any(
        loc["district_id"] == districts[0].id for loc in location_results
    )
    has_block0 = any(loc["block_id"] == blocks[0].id for loc in location_results)

    assert has_state0
    assert has_state1
    assert has_district0
    assert has_block0

    # Get question to verify locations were added
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}")
    question = response.json()
    assert len(question["locations"]) == 4

    # Test modifying locations (add new, remove some existing)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/locations",
        json={
            "locations": [
                {
                    "state_id": states[0].id,  # Keep this one
                    "district_id": None,
                    "block_id": None,
                },
                {
                    "state_id": states[2].id,  # Add new state, remove states[1]
                    "district_id": None,
                    "block_id": None,
                },
                # Remove district and block entirely
            ]
        },
    )

    assert response.status_code == 200
    location_results = response.json()
    # Should only return 2 results for the new state
    assert len(location_results) == 2

    # Verify we now have only 2 locations total
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}")
    question = response.json()
    assert len(question["locations"]) == 2

    # Test removing all locations
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/locations",
        json={"locations": []},
    )

    assert response.status_code == 200
    location_results = response.json()
    assert len(location_results) == 0

    # Verify all locations were removed
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}")
    question = response.json()
    assert len(question["locations"]) == 0


def test_mixed_single_and_bulk_operations(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test that the PUT update operations work seamlessly."""
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
        name="Mixed Test Category",
        description="Categories for mixed testing",
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tags = []
    for i in range(3):
        tag = Tag(
            name=f"MixedTag{i}",
            description=f"Mixed test tag {i}",
            tag_type_id=tag_type.id,
            created_by_id=user.id,
            organization_id=org.id,
        )
        db.add(tag)
        tags.append(tag)

    db.commit()
    for tag in tags:
        db.refresh(tag)

    # Create question
    question_data = {
        "organization_id": org.id,
        "question_text": random_lower_string(),
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        "correct_answer": [1],
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    question_id = response.json()["id"]

    # Add a single tag using PUT
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={"tag_ids": [tags[0].id]},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Add multiple tags using PUT (replace previous)
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={"tag_ids": [tags[1].id, tags[2].id]},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2

    # Verify all tags are present
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    current_tags = response.json()
    assert len(current_tags) == 2
    tag_ids = {tag["id"] for tag in current_tags}
    assert tag_ids == {tags[1].id, tags[2].id}

    # Update to have all three tags using PUT
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={"tag_ids": [tags[0].id, tags[1].id, tags[2].id]},
    )
    assert response.status_code == 200

    # Remove all tags using PUT
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question_id}/tags",
        json={"tag_ids": []},
    )
    assert response.status_code == 200

    # Verify all tags are removed
    response = client.get(f"{settings.API_V1_STR}/questions/{question_id}/tags")
    current_tags = response.json()
    assert len(current_tags) == 0


def test_update_question_tags(client: TestClient, db: SessionDep) -> None:
    """Test updating all tags for a question using PUT."""
    # Create organization, user, and initial tags
    org = Organization(name=random_lower_string())
    db.add(org)
    user = create_random_user(db)
    tag_type = TagType(
        name="Update Test Category",
        created_by_id=user.id,
        organization_id=org.id,
    )
    db.add(tag_type)
    db.flush()

    tags = []
    for i in range(5):
        tag = Tag(
            name=f"UpdateTag{i}",
            tag_type_id=tag_type.id,
            created_by_id=user.id,
            organization_id=org.id,
        )
        db.add(tag)
        tags.append(tag)

    db.commit()
    for tag in tags:
        db.refresh(tag)

    # Create a question with initial tags (tag0, tag1)
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()
    question.revisions.append(
        QuestionRevision(
            question_id=question.id,
            question_text="test",
            created_by_id=user.id,
            question_type=QuestionType.single_choice,
        )
    )
    db.add(QuestionTag(question_id=question.id, tag_id=tags[0].id))
    db.add(QuestionTag(question_id=question.id, tag_id=tags[1].id))
    db.commit()
    db.refresh(question)

    # 1. Test Sync: remove tag1, keep tag0, add tag2, tag3
    update_payload = {"tag_ids": [tags[0].id, tags[2].id, tags[3].id]}
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question.id}/tags",
        json=update_payload,
    )

    assert response.status_code == 200
    updated_tags = response.json()
    assert len(updated_tags) == 3
    updated_tag_ids = {t["id"] for t in updated_tags}
    assert updated_tag_ids == {tags[0].id, tags[2].id, tags[3].id}

    # 2. Test Add: send all existing plus a new one
    update_payload = {"tag_ids": [tags[0].id, tags[2].id, tags[3].id, tags[4].id]}
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question.id}/tags",
        json=update_payload,
    )
    assert response.status_code == 200
    assert len(response.json()) == 4

    # 3. Test Remove: send a subset of existing
    update_payload = {"tag_ids": [tags[2].id]}
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question.id}/tags",
        json=update_payload,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == tags[2].id

    # 4. Test Clear All: send an empty list
    update_payload = {"tag_ids": []}
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question.id}/tags",
        json=update_payload,
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_update_question_locations(client: TestClient, db: SessionDep) -> None:
    # Create organization and user
    org = Organization(name=random_lower_string())
    db.add(org)
    user = create_random_user(db)

    # Create locations
    country = Country(name="Country")
    db.add(country)
    db.commit()
    db.refresh(country)

    state1 = State(name="State1", country_id=country.id)
    state2 = State(name="State2", country_id=country.id)
    db.add_all([state1, state2])
    db.commit()
    db.refresh(state1)
    db.refresh(state2)

    district1 = District(name="District1", state_id=state1.id)
    db.add(district1)
    db.commit()
    db.refresh(district1)

    block1 = Block(name="Block1", district_id=district1.id)
    db.add(block1)
    db.commit()
    db.refresh(block1)

    # Create question with initial location (state1)
    question = Question(organization_id=org.id)
    db.add(question)
    db.flush()
    question.revisions.append(
        QuestionRevision(
            question_id=question.id,
            question_text="test",
            created_by_id=user.id,
            question_type=QuestionType.single_choice,
        )
    )
    db.add(QuestionLocation(question_id=question.id, state_id=state1.id))
    db.commit()

    # Test sync: keep state1, add district1 and block1
    update_payload = {
        "locations": [
            {"state_id": state1.id, "district_id": None, "block_id": None},
            {"state_id": None, "district_id": district1.id, "block_id": None},
            {"state_id": None, "district_id": None, "block_id": block1.id},
        ]
    }
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question.id}/locations",
        json=update_payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    state_ids = {loc["state_id"] for loc in data if loc["state_id"]}
    district_ids = {loc["district_id"] for loc in data if loc["district_id"]}
    block_ids = {loc["block_id"] for loc in data if loc["block_id"]}
    assert state_ids == {state1.id}
    assert district_ids == {district1.id}
    assert block_ids == {block1.id}

    # Test clear: send empty list
    response = client.put(
        f"{settings.API_V1_STR}/questions/{question.id}/locations",
        json={"locations": []},
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_inactive_question_listed(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]
    tag_type = TagType(
        name="hard questions",
        description="Categories for questions",
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(tag_type)
    db.flush()
    tag = Tag(
        name="Data science",
        description="data science Science related questions",
        tag_type_id=tag_type.id,
        created_by_id=user_id,
        organization_id=org_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    question_text = random_lower_string()
    question_data = {
        "organization_id": org_id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1],  # First option is correct
        "is_mandatory": True,
        "tag_ids": [tag.id],
        "is_active": False,  # Set question as inactive
    }
    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert "id" in data
    assert data["question_text"] == question_text
    assert data["question_type"] == QuestionType.single_choice
    assert len(data["options"]) == 3
    assert data["correct_answer"] == [1]  # First option is correct
    assert data["is_active"] is False  # Check if question is inactive
    question_id = data["id"]

    response = client.get(
        f"{settings.API_V1_STR}/questions/?is_active=true",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    # Make sure the inactive question is NOT in the response
    assert all(item["id"] != question_id for item in data)


def test_deactivate_question_with_new_revision(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]

    question_text = random_lower_string()
    question_data = {
        "organization_id": org_id,
        "question_text": question_text,
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1],  # First option is correct
        "is_mandatory": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["question_text"] == question_text
    assert data["question_type"] == QuestionType.single_choice
    assert len(data["options"]) == 3
    assert data["correct_answer"] == [1]  # First option is correct
    assert data["is_active"] is True  # Check if question is active
    question_id = data["id"]

    # Create a new revision for the question
    new_revision_data = {
        "question_text": random_lower_string(),
        "question_type": QuestionType.multi_choice,
        "options": [
            {"id": 1, "key": "A", "value": "New Option 1"},
            {"id": 2, "key": "B", "value": "New Option 2"},
            {"id": 3, "key": "C", "value": "New Option 3"},
        ],
        "correct_answer": [2],
        "is_active": False,  # Deactivate the question in the new revision
    }

    response = client.post(
        f"{settings.API_V1_STR}/questions/{question_id}/revisions",
        json=new_revision_data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data_revision = response.json()
    assert data_revision["question_text"] == new_revision_data["question_text"]
    assert data_revision["question_type"] == new_revision_data["question_type"]
    assert len(data_revision["options"]) == 3
    assert data_revision["correct_answer"] == [2]  # Second option is correct
    assert data_revision["is_active"] is False  # Check if question is inactive

    # Fetch the latest revision to ensure it is inactive
    response = client.get(
        f"{settings.API_V1_STR}/questions/",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    # Make sure the inactive question is NOT in the response
    assert any(item["id"] == question_id for item in data)


def test_filter_questions_by_latest_revision_text(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    q = Question(organization_id=org_id)
    db.add(q)
    db.flush()
    rev1_text = "First revision text"
    rev1 = QuestionRevision(
        question_id=q.id,
        created_by_id=user_id,
        question_text=rev1_text,
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )
    db.add(rev1)
    db.flush()
    q.last_revision_id = rev1.id
    db.commit()
    db.refresh(q)
    rev2_text = "Unique latest revision text"
    rev2 = QuestionRevision(
        question_id=q.id,
        created_by_id=user_id,
        question_text=rev2_text,
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[2],
    )
    db.add(rev2)
    db.flush()
    q.last_revision_id = rev2.id
    db.commit()
    db.refresh(q)
    response = client.get(
        f"{settings.API_V1_STR}/questions/?question_text=Unique+latest+revision+text",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data]
    assert q.id in ids
    response = client.get(
        f"{settings.API_V1_STR}/questions/?question_text=First+revision+text",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data]
    assert q.id not in ids


def test_filter_questions_by_latest_revision_subtext(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    question = Question(organization_id=org_id)
    db.add(question)
    db.flush()
    rev1 = QuestionRevision(
        question_id=question.id,
        created_by_id=user_id,
        question_text="First revision text is Here",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )
    db.add(rev1)
    db.flush()
    question.last_revision_id = rev1.id
    db.commit()
    db.refresh(question)

    rev2 = QuestionRevision(
        question_id=question.id,
        created_by_id=user_id,
        question_text="Unique latest revision text is here",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[2],
    )
    db.add(rev2)
    db.flush()
    question.last_revision_id = rev2.id
    db.commit()
    db.refresh(question)
    response = client.get(
        f"{settings.API_V1_STR}/questions/?question_text=Unique",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data]
    assert question.id in ids
    response = client.get(
        f"{settings.API_V1_STR}/questions/?question_text=First+revision+text",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data]
    assert question.id not in ids


def test_bulk_upload_questions_response_format(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    # Prepare a CSV with some valid and some invalid rows
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()
    db.refresh(punjab)
    tag_type = TagType(
        name="Response Model Type",
        description="For testing the response model",
        organization_id=org_id,
        created_by_id=user_data["id"],
    )
    db.add(tag_type)
    db.commit()
    db.refresh(tag_type)
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is 4+4?,4,3,5,8,A,Response Model Type:Math,Punjab
What is the capital of France?,Paris,London,Berlin,Madrid,A,Response Model Type:Geography,Punjab
Water,Gold,Silver,Carbon,A,Response Model Type:Chemistry,Punjab
Invalid state?,A,B,C,D,A,Response Model Type:Math,NonExistentState
Invalid tagtype?,A,B,C,D,A,NonExistentType:Math,Punjab
"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )
        assert response.status_code == 200
        data = response.json()
        # Check response structure
        assert "message" in data
        assert "uploaded_questions" in data
        assert "success_questions" in data
        assert "failed_questions" in data
        assert data["uploaded_questions"] == 5
        assert data["success_questions"] == 2
        assert data["failed_questions"] == 3
        assert "Bulk upload complete." in data["message"]
        assert "Created 2 questions successfully." in data["message"]
        assert "Failed to create 3 questions." in data["message"]
    finally:
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_get_questions_by_is_active_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    active_question = Question(organization_id=org_id, is_active=True)
    db.add(active_question)
    db.flush()
    rev1 = QuestionRevision(
        question_id=active_question.id,
        created_by_id=user_id,
        question_text="Active question",
        question_type="single_choice",
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )
    db.add(rev1)
    db.flush()
    active_question.last_revision_id = rev1.id
    inactive_question = Question(organization_id=org_id, is_active=False)
    db.add(inactive_question)
    db.flush()
    rev2 = QuestionRevision(
        question_id=inactive_question.id,
        created_by_id=user_id,
        question_text="Inactive question",
        question_type="single_choice",
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[2],
    )
    db.add(rev2)
    db.flush()
    inactive_question.last_revision_id = rev2.id
    db.commit()
    db.refresh(active_question)
    db.refresh(inactive_question)
    response = client.get(
        f"{settings.API_V1_STR}/questions/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [q["id"] for q in data]
    assert active_question.id in ids
    assert inactive_question.id in ids
    response = client.get(
        f"{settings.API_V1_STR}/questions/?is_active=true",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [q["id"] for q in data]
    assert active_question.id in ids
    assert inactive_question.id not in ids
    response = client.get(
        f"{settings.API_V1_STR}/questions/?is_active=false",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [q["id"] for q in data]
    assert inactive_question.id in ids
    assert active_question.id not in ids


def test_bulk_upload_questions_without_tagtype(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()
    db.refresh(punjab)
    tag_type = TagType(
        name="Subject",
        description="Subject tags",
        organization_id=org_id,
        created_by_id=user_data["id"],
    )
    db.add(tag_type)
    db.commit()
    db.refresh(tag_type)
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is 10+10?,20,10,30,40,A,Math,Punjab
What is the color of the sky?,Blue,Green,Red,Yellow,A,Science,Punjab
What is 5x5?,25,10,15,20,A,Subject:Multiplication,Punjab
What is the capital of India?,Delhi,Mumbai,Kolkata,Chennai,A,Subject:Geography,Punjab
"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions_no_tagtype.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "Created" in data["message"]
        assert data["uploaded_questions"] == 4
        assert data["success_questions"] == 4
        response = client.get(
            f"{settings.API_V1_STR}/questions/",
            headers=get_user_superadmin_token,
        )
        questions = response.json()
        question_texts = [q["question_text"] for q in questions]
        assert "What is 10+10?" in question_texts
        assert "What is the color of the sky?" in question_texts
        for question in questions:
            if question["question_text"] == "What is 10+10?":
                assert any(tag["name"] == "Math" for tag in question["tags"])
            if question["question_text"] == "What is the color of the sky?":
                assert any(tag["name"] == "Science" for tag in question["tags"])
                assert any(tag["tag_type"] is None for tag in question["tags"])
            if question["question_text"] == "What is 5x5?":
                assert any(tag["name"] == "Multiplication" for tag in question["tags"])
                assert any(
                    tag["tag_type"]["name"] == "Subject" for tag in question["tags"]
                )
            if question["question_text"] == "What is the capital of India?":
                assert any(tag["name"] == "Geography" for tag in question["tags"])
                assert any(
                    tag["tag_type"]["name"] == "Subject" for tag in question["tags"]
                )
    finally:
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_bulk_upload_questions_with_invalid_tagtype(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()
    db.refresh(punjab)
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
    What is 10+10?,20,10,30,40,A,Math,Punjab
    What is the color of the sky?,Blue,Green,Red,Yellow,A,Science,Punjab
    What is 5x5?,25,10,15,20,A,InvalidTagType:Multiplication,Punjab
    What is the capital of India?,Delhi,Mumbai,Kolkata,Chennai,A,InvalidTagType:Geography,Punjab"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={
                    "file": ("test_questions_invalid_tagtype.csv", file, "text/csv")
                },
                headers=get_user_superadmin_token,
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "Failed to create 2 questions." in data["message"]
        assert data["uploaded_questions"] == 4
        assert data["success_questions"] == 2
        assert data["failed_questions"] == 2
    finally:
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_create_duplicate_question(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    # user_id = user_data["id"]
    tag_type_response = client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json={
            "name": "Test Tag Type",
            "description": "For testing",
            "organization_id": org_id,
        },
        headers=get_user_superadmin_token,
    )
    tag_type_data = tag_type_response.json()
    tag_type_id = tag_type_data["id"]
    tag_response = client.post(
        f"{settings.API_V1_STR}/tag/",
        json={
            "name": "Test Tag",
            "description": "For testing questions",
            "tag_type_id": tag_type_id,
            "organization_id": org_id,
        },
        headers=get_user_superadmin_token,
    )
    tag_data = tag_response.json()
    tag_id = tag_data["id"]
    question_data = {
        "organization_id": org_id,
        "question_text": "What is PYTHON",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [tag_id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["question_text"] == "What is PYTHON"
    assert data["organization_id"] == org_id
    assert data["question_type"] == QuestionType.single_choice
    assert len(data["tags"]) == 1
    assert data["tags"][0]["id"] == tag_id
    question = db.get(Question, data["id"])
    assert question is not None
    duplicate_response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    assert duplicate_response.status_code == 400
    duplicate_data = duplicate_response.json()
    assert (
        duplicate_data["detail"]
        == "Duplicate question: Same question text and tags already exist."
    )


def test_create_question_same_text_different_tags_should_pass(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    tag_type = TagType(
        name="MCQ TagType",
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.flush()
    tag = Tag(
        name="Programming",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    db.add(tag)
    db.flush()
    different_tag = Tag(
        name="DSA",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    db.add(different_tag)
    db.flush()
    question = Question(
        organization_id=org_id,
        is_active=True,
        created_by_id=user_id,
    )
    db.add(question)
    db.flush()
    revision = QuestionRevision(
        question_id=question.id,
        created_by_id=user_id,
        question_text="What is C++?",
        question_type=QuestionType.single_choice,
        is_mandatory=True,
        correct_answer=[1],
        options=[
            {"id": 1, "key": "A", "value": "A snake"},
            {"id": 2, "key": "B", "value": "A language"},
        ],
    )
    db.add(revision)
    db.flush()
    question.last_revision_id = revision.id
    db.add(question)
    question_tag = QuestionTag(
        question_id=question.id,
        tag_id=tag.id,
    )
    db.add(question_tag)
    db.commit()
    duplicate_question_data = {
        "organization_id": org_id,
        "question_text": "What is c++?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "A snake"},
            {"id": 2, "key": "B", "value": "A language"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [different_tag.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=duplicate_question_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question_text"] == "What is c++?"
    assert data["tags"][0]["id"] == different_tag.id


def test_create_question_same_text_no_tags_vs_with_tags_should_pass(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    tag_type = TagType(
        name="Tech TagType",
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.flush()

    tag1 = Tag(
        name="Java",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    tag2 = Tag(
        name="Backend",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    db.add_all([tag1, tag2])
    db.flush()
    db.commit()
    question1_data = {
        "organization_id": org_id,
        "question_text": "What is Java?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [],
    }
    response1 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question1_data,
        headers=get_user_superadmin_token,
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["question_text"] == "What is Java?"
    assert data1["tags"] == []

    question2_data = {
        "organization_id": org_id,
        "question_text": "What is Java?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [tag2.id, tag1.id],
    }

    response2 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question2_data,
        headers=get_user_superadmin_token,
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["question_text"] == "What is Java?"
    assert len(data2["tags"]) == 2
    returned_tag_ids = [tag["id"] for tag in data2["tags"]]
    assert set(returned_tag_ids) == {tag1.id, tag2.id}


def test_bulk_upload_questions_with_duplicate(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    tag_type = TagType(
        name="Bulk TagType",
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.flush()

    tag1 = Tag(
        name="BulkTag",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    tag2 = Tag(
        name="BulkTag 2",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    db.add_all([tag1, tag2])
    db.flush()
    db.commit()
    question1_data = {
        "organization_id": org_id,
        "question_text": "What   is   Python?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [tag1.id],
    }
    response1 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question1_data,
        headers=get_user_superadmin_token,
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["question_text"] == "What   is   Python?"
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()
    db.refresh(punjab)
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
    What is 10+10?,20,10,30,40,A,Math,Punjab
     What is 10+10?,20,10,30,40,A,Math,Punjab
    What is PYTHON?,Programming Language,Snake,Car,Food,A,Bulk TagType:BulkTag,Punjab
    What is Python?,Programming Language,Snake,Car,Food,A,Bulk TagType:BulkTag |BulkTag 2,Punjab
    What is Python?,Programming Language,Snake,Car,Food,A,Bulk TagType:BulkTag 2,Punjab
    What is the color of the sky?,Blue,Green,Red,Yellow,A,Science,Punjab"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={
                    "file": ("test_questions_invalid_tagtype.csv", file, "text/csv")
                },
                headers=get_user_superadmin_token,
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "Failed to create 3 questions." in data["message"]
        assert data["uploaded_questions"] == 6
        assert data["success_questions"] == 3
        assert data["failed_questions"] == 3
    finally:
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_duplicate_question_detected_if_any_tag_matches(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    tag_type = TagType(
        name="level",
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.flush()

    tag1 = Tag(
        name="level 1",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    tag2 = Tag(
        name="level 2",
        description=random_lower_string(),
        organization_id=org_id,
        tag_type_id=tag_type.id,
        created_by_id=user_id,
    )
    db.add_all([tag1, tag2])
    db.flush()
    db.commit()
    question1_data = {
        "organization_id": org_id,
        "question_text": "What is SQL?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
        ],
        "correct_answer": [2],
        "is_mandatory": True,
        "tag_ids": [tag1.id],
    }
    response1 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question1_data,
        headers=get_user_superadmin_token,
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["question_text"] == "What is SQL?"

    question2_data = {
        "organization_id": org_id,
        "question_text": "What is SQL?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option A"},
            {"id": 2, "key": "B", "value": "Option B"},
        ],
        "correct_answer": [2],
        "is_mandatory": True,
        "tag_ids": [tag2.id, tag1.id],
    }

    response2 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question2_data,
        headers=get_user_superadmin_token,
    )
    assert response2.status_code == 400
    data2 = response2.json()
    assert (
        data2["detail"]
        == "Duplicate question: Same question text and tags already exist."
    )


def test_question_revision_with_same_text_and_tags_is_allowed(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    tag_type = TagType(
        name="Subject",
        description=random_lower_string(),
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.flush()
    tag = Tag(
        name="cyber security",
        description=random_lower_string(),
        tag_type_id=tag_type.id,
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag)
    db.flush()
    question_payload = {
        "organization_id": org_id,
        "question_text": "What is gravity?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Force"},
            {"id": 2, "key": "B", "value": "Energy"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [tag.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    question = response.json()
    question_id = question["id"]
    revision_payload = {
        "question_text": "What is gravity?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "A force that attracts objects"},
            {"id": 2, "key": "B", "value": "No force at all"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "is_active": True,
    }
    revision_response = client.post(
        f"{settings.API_V1_STR}/questions/{question_id}/revisions",
        json=revision_payload,
        headers=get_user_superadmin_token,
    )
    assert revision_response.status_code == 200
    updated_question = revision_response.json()
    assert updated_question["id"] == question_id
    assert updated_question["question_text"] == "What is gravity?"
    assert updated_question["options"][0]["value"] == "A force that attracts objects"
    assert "tags" in updated_question


def test_check_question_duplication_if_deleted(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    tag_type = TagType(
        name="Test Tag Type",
        description="For testing",
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.commit()

    db.flush()
    tag = Tag(
        name="Test Tag",
        description="For testing questions",
        tag_type_id=tag_type.id,
        organization_id=org_id,
        created_by_id=user_id,
    )
    db.add(tag)
    db.commit()
    db.flush()
    question_data = {
        "organization_id": org_id,
        "question_text": "What is Python?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [tag.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question_data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    question_id = data["id"]

    # Delete the question
    delete_response = client.delete(
        f"{settings.API_V1_STR}/questions/{question_id}",
        headers=get_user_superadmin_token,
    )
    assert delete_response.status_code == 200

    # Try to create a new question with the same text and tags
    duplicate_question_data = {
        "organization_id": org_id,
        "question_text": "What is Python?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [tag.id],
    }
    duplicate_response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=duplicate_question_data,
        headers=get_user_superadmin_token,
    )
    assert duplicate_response.status_code == 200
    duplicate_data = duplicate_response.json()
    assert duplicate_data["question_text"] == "What is Python?"
    assert duplicate_data["tags"][0]["id"] == tag.id
    assert duplicate_data["organization_id"] == org_id
    assert duplicate_data["question_type"] == QuestionType.single_choice
    assert len(duplicate_data["options"]) == 3
    assert duplicate_data["options"][0]["value"] == "Option 1"
    assert duplicate_data["options"][1]["value"] == "Option 2"
    assert duplicate_data["options"][2]["value"] == "Option 3"
    assert duplicate_data["correct_answer"] == [1]
    assert duplicate_data["is_mandatory"] is True

    duplicate_question_data = {
        "organization_id": org_id,
        "question_text": "What is Python?",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 33"},
        ],
        "correct_answer": [2],
        "is_mandatory": True,
        "tag_ids": [tag.id],
    }

    another_duplicate_response = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=duplicate_question_data,
        headers=get_user_superadmin_token,
    )
    assert another_duplicate_response.status_code == 400


def test_bulk_upload_questions_with_multiple_errors_report(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)

    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()
    db.refresh(punjab)
    csv_content = """Questions,Option A,Option B,Option C,Option D,Correct Option,Training Tags,State
What is 10+10?,20,10,30,40,A,Math,Punjab
What is the color of the sky?,Blue,Green,Red,Yellow,A,Science,Punjab
What is 5x5?,25,10,15,20,A,InvalidTagType:Multiplication,Punjab
What is the capital of India?,Delhi,Mumbai,Kolkata,Chennai,A,InvalidTagType:Geography,Punjab
Which option is missing?,,10,20,30,A,Math,Punjab
What is 2 + 2?,4,5,6,7,Z,Math,Punjab
,1,2,3,4,A,Math,Punjab
What is 9+1?,10,20,30,40,A,Math,NonExistentState
Which planet is known as the Red Planet?,Earth,Mars,Jupiter,Venus,,Math,Punjab"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name
    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/questions/bulk-upload",
                files={"file": ("test_questions_error_report.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded_questions"] == 9
        assert data["success_questions"] == 2
        assert data["failed_questions"] == 7
        assert "Failed to create 7 questions." in data["message"]
        expected_errors = {
            3: "Invalid tag type",
            4: "Invalid tag type",
            5: "one or more options (a-d) are missing",
            6: "Invalid correct option",
            7: "Question text is missing",
            8: "Invalid states: NonExistentState",
            9: "Correct option is missing",
        }
        assert (
            "Download failed questions: data:text/csv;base64,"
            in data["failed_question_details"]
        )
        base64_csv = data["failed_question_details"].split("base64,")[-1]
        csv_bytes = base64.b64decode(base64_csv)
        csv_text = csv_bytes.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(csv_reader)
        assert len(rows) == 7
        for row in rows:
            assert "row_number" in row
            assert "question_text" in row
            assert "error" in row
            assert row["error"]
            row_number = int(row["row_number"])
            expected_error = expected_errors.get(row_number)
            assert expected_error is not None
            assert expected_error.lower() in row["error"].lower()

    finally:
        import os

        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
