from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import (
    Country,
    Organization,
    Question,
    QuestionRevision,
    State,
    Tag,
    TagType,
    Test,
    TestQuestion,
    TestState,
    TestTag,
    User,
)
from app.models.question import QuestionType
from app.tests.utils.location import create_random_state
from app.tests.utils.organization import create_random_organization
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.tag import create_random_tag
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import random_lower_string


def setup_data(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> Any:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    user = db.get(User, user_id)
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    stata_a = State(name=random_lower_string(), country_id=india.id)
    db.add(stata_a)
    state_b = State(name=random_lower_string(), country_id=india.id)
    db.add(state_b)
    db.commit()

    organization = Organization(name=random_lower_string())
    db.add(organization)
    db.commit()

    tag_type = TagType(
        name=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user_id,
    )
    db.add(tag_type)
    db.commit()

    tag_a = Tag(
        name=random_lower_string(),
        created_by_id=user_id,
        tag_type_id=tag_type.id,
        organization_id=organization.id,
    )

    tag_b = Tag(
        name=random_lower_string(),
        created_by_id=user_id,
        tag_type_id=tag_type.id,
        organization_id=organization.id,
    )
    db.add(tag_a)
    db.add(tag_b)
    db.commit()

    org = Organization(name=random_lower_string())
    db.add(org)
    db.commit()
    db.refresh(org)

    # Create questions with revisions
    question_one = Question(organization_id=org.id)
    question_two = Question(organization_id=org.id)
    db.add(question_one)
    db.add(question_two)
    db.commit()
    # db.flush()

    # Create question revisions
    question_revision_one = QuestionRevision(
        question_id=question_one.id,
        created_by_id=user_id,
        question_text="What is the size of Sun",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )

    question_revision_two = QuestionRevision(
        question_id=question_two.id,
        created_by_id=user_id,
        question_text="What is the speed of light",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )

    db.add(question_revision_one)
    db.add(question_revision_two)
    db.commit()
    db.flush()

    # Set last_revision_id on questions
    question_one.last_revision_id = question_revision_one.id
    question_two.last_revision_id = question_revision_two.id
    db.commit()
    db.refresh(question_one)
    db.refresh(question_two)
    db.refresh(question_revision_one)
    db.refresh(question_revision_two)

    return (
        user,
        india,
        stata_a,
        state_b,
        organization,
        tag_type,
        tag_a,
        tag_b,
        question_one,
        question_two,
        question_revision_one,
        question_revision_two,
    )


def test_create_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    (
        user,
        india,
        punjab,
        goa,
        organization,
        tag_type,
        tag_hindi,
        tag_marathi,
        question_one,
        question_two,
        question_revision_one,
        question_revision_two,
    ) = setup_data(client, db, get_user_superadmin_token)
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 2,
        "marks": 3,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "marks_level": None,
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "tag_ids": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question_revision_one.id, question_revision_two.id],
        "state_ids": [punjab.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["time_limit"] == payload["time_limit"]
    assert data["marks"] == payload["marks"]
    assert data["completion_message"] == payload["completion_message"]
    assert data["start_instructions"] == payload["start_instructions"]
    assert data["marks_level"] == payload["marks_level"]
    assert data["link"] == payload["link"]
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["created_by_id"] == user_id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert len(data["tags"]) == 2
    assert [data["tags"][0]["name"], data["tags"][1]["name"]] == [
        tag_hindi.name,
        tag_marathi.name,
    ]

    test_tag_link = db.exec(select(TestTag).where(TestTag.test_id == data["id"])).all()

    assert test_tag_link[0].tag_id == tag_hindi.id
    assert test_tag_link[1].tag_id == tag_marathi.id

    test_question_link = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == data["id"])
    ).all()

    # Verify the test_question_link has the question_revision_id
    assert test_question_link[0].question_revision_id == question_revision_one.id
    assert test_question_link[1].question_revision_id == question_revision_two.id

    sample_test = Test(
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
        created_by_id=user_id,
    )
    db.add(sample_test)
    db.commit()

    marathi_test_name = random_lower_string()
    marathi_test_description = random_lower_string()

    payload = {
        "name": marathi_test_name,
        "description": marathi_test_description,
        "time_limit": 10,
        "marks": 3,
        "completion_message": "Congratulations!!",
        "start_instructions": "Please keep your mobile phones away",
        "marks_level": None,
        "link": "string",
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "template_id": sample_test.id,
        "tag_ids": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question_revision_one.id, question_revision_two.id],
        "state_ids": [punjab.id, goa.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["time_limit"] == payload["time_limit"]
    assert data["marks"] == payload["marks"]
    assert data["completion_message"] == payload["completion_message"]
    assert data["start_instructions"] == payload["start_instructions"]
    assert data["marks_level"] == payload["marks_level"]
    assert data["link"] == payload["link"]
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == payload["template_id"]
    assert data["created_by_id"] == user_id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "states" in data
    assert len(data["tags"]) == 2
    assert len(data["states"]) == 2
    assert len(data["question_revisions"]) == 2

    test_tag_link = db.exec(select(TestTag).where(TestTag.test_id == data["id"])).all()

    assert test_tag_link[0].tag_id == tag_hindi.id
    assert test_tag_link[1].tag_id == tag_marathi.id

    test_question_link = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == data["id"])
    ).all()

    # Verify the test_question_link has the question_revision_id
    assert test_question_link[0].question_revision_id == question_revision_one.id
    assert test_question_link[1].question_revision_id == question_revision_two.id

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 10,
        "marks": 3,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "marks_level": None,
        "link": "string",
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "template_id": sample_test.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    data = response.json()
    assert response.status_code == 200
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["time_limit"] == payload["time_limit"]
    assert data["marks"] == payload["marks"]
    assert data["completion_message"] == payload["completion_message"]
    assert data["start_instructions"] == payload["start_instructions"]
    assert data["marks_level"] == payload["marks_level"]
    assert data["link"] == payload["link"]
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == sample_test.id
    assert data["created_by_id"] == user_id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "question_revisions" in data
    assert len(data["tags"]) == 0
    assert len(data["question_revisions"]) == 0
    assert len(data["states"]) == 0

    test_tag_link = db.exec(select(TestTag).where(TestTag.test_id == data["id"])).all()

    assert test_tag_link == []

    test_question_link = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == data["id"])
    ).all()

    assert test_question_link == []


def test_create_test_random_question_field(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": random_lower_string(),
        "random_questions": True,
        "no_of_random_questions": 5,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": random_lower_string(),
        "random_questions": True,
        "no_of_random_questions": 0,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": random_lower_string(),
        "random_questions": True,
        "no_of_random_questions": None,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": random_lower_string(),
        "random_questions": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_test_auto_generate_link_uuid(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test that a UUID is auto-generated for the link field when not provided."""
    user = create_random_user(db)

    # Test 1: Create test without providing link field
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        # No link field provided
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert "link" in data
    assert data["link"] is not None
    assert len(data["link"]) == 36  # UUID length

    # Verify it's a valid UUID format
    import uuid

    try:
        uuid.UUID(data["link"])
        uuid_is_valid = True
    except ValueError:
        uuid_is_valid = False
    assert uuid_is_valid

    # Test 2: Create test with empty string link field
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": "",  # Empty string
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert "link" in data
    assert data["link"] is not None
    assert len(data["link"]) == 36  # UUID length

    # Verify it's a valid UUID format
    try:
        uuid.UUID(data["link"])
        uuid_is_valid = True
    except ValueError:
        uuid_is_valid = False
    assert uuid_is_valid

    # Test 3: Create test with provided link field (should not be overridden)
    custom_link = "my-custom-test-link"
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": custom_link,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["link"] == custom_link  # Should preserve custom link


def test_get_tests(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    (
        user,
        india,
        state_a,
        state_b,
        organization,
        tag_type,
        tag_a,
        tag_b,
        question_one,
        question_two,
        question_revision_one,
        question_revision_two,
    ) = setup_data(client, db, get_user_superadmin_token)

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

    test_tag_link = TestTag(test_id=test.id, tag_id=tag_a.id)
    db.add(test_tag_link)

    test_question_link = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    db.add(test_question_link)

    test_state_link = TestState(test_id=test.id, state_id=state_a.id)
    db.add(test_state_link)

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200

    assert any(item["name"] == test.name for item in data)
    assert any(item["description"] == test.description for item in data)
    assert any(item["time_limit"] == test.time_limit for item in data)
    assert any(item["marks"] == test.marks for item in data)
    assert any(item["completion_message"] == test.completion_message for item in data)
    assert any(item["start_instructions"] == test.start_instructions for item in data)
    assert any(item["marks_level"] == test.marks_level for item in data)
    assert any(item["link"] == test.link for item in data)
    assert any(item["no_of_attempts"] == test.no_of_attempts for item in data)
    assert any(item["shuffle"] == test.shuffle for item in data)
    assert any(item["random_questions"] == test.random_questions for item in data)
    assert any(
        item["no_of_random_questions"] == test.no_of_random_questions for item in data
    )
    assert any(item["question_pagination"] == test.question_pagination for item in data)
    assert any(item["is_template"] == test.is_template for item in data)
    assert any(item["created_by_id"] == test.created_by_id for item in data)

    assert any(
        len(item["tags"]) == 1 and item["tags"][0]["id"] == tag_a.id for item in data
    )
    assert any(
        len(item["states"]) == 1 and item["states"][0]["id"] == state_a.id
        for item in data
    )


def test_get_test_by_filter_name(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_name_1 = random_lower_string()
    test_name_2 = random_lower_string()
    test_1 = Test(
        name=random_lower_string() + test_name_1 + random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    test_2 = Test(
        name=test_name_2,
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    test_3 = Test(
        name=random_lower_string() + test_name_1 + random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    db.add_all([test_1, test_2, test_3])
    db.commit()
    db.refresh(test_1)
    db.refresh(test_2)
    db.refresh(test_3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?name={test_name_1}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?name={test_name_2}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_get_test_by_filter_description(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    random_text_1 = random_lower_string()
    random_text_2 = random_lower_string()
    test_1 = Test(
        name=random_lower_string(),
        description=random_text_1,
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string() + random_text_1 + random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    test_3 = Test(
        name=random_lower_string(),
        description=random_text_2,
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    db.add_all([test_1, test_2, test_3])
    db.commit()
    db.refresh(test_1)
    db.refresh(test_2)
    db.refresh(test_3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?description={random_text_1}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?description={random_text_2}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_get_test_by_filter_start_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)

    test_1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 25, 10, 30),
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 27, 12, 30),
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 28, 15, 30),
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 28, 19, 30),
    )
    db.add_all([test_1, test_2, test_3, test_4])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-25T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 4

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-27T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-28T15:30:59Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-28T19:31:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-24T00:00:00Z&start_time_lte=2025-07-26T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-27T12:30:00Z&start_time_lte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_lte=2025-07-28T15:30:00Z&start_time_gte=2025-07-25T10:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_get_test_by_filter_end_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 25, 10, 30),
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 27, 12, 30),
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 28, 15, 30),
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 28, 19, 30),
    )
    db.add_all([test_1, test_2, test_3, test_4])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-25T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-27T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-28T15:30:59Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-28T19:31:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-24T00:00:00Z&end_time_lte=2025-07-26T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-27T12:30:00Z&end_time_lte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_lte=2025-07-28T15:30:00Z&end_time_gte=2025-07-25T10:30:00Z",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_get_test_by_filter_start_end_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)

    test_1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 24, 10, 30),
        end_time=datetime(2025, 4, 25, 11, 30),
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 26, 10, 30),
        end_time=datetime(2025, 4, 27, 12, 30),
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 28, 14, 30),
        end_time=datetime(2025, 4, 28, 15, 30),
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 28, 19, 10),
        end_time=datetime(2025, 4, 28, 19, 30),
    )
    db.add_all([test_1, test_2, test_3, test_4])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-04-24T10:00:00Z&end_time_lte=2025-04-27T12:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_lte=2025-04-28T00:00:00Z&end_time_gte=2025-04-27T12:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_get_test_by_filter_time_limit(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)

    test_1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        time_limit=30,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        time_limit=40,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        time_limit=45,
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3, test_4])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?time_limit_gte=25&time_limit_lte=40&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?time_limit_gte=31&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?time_limit_lte=40&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_test_by_filter_completion_message(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    random_text_1 = random_lower_string()
    random_text_2 = random_lower_string()

    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        completion_message=random_lower_string() + random_text_1,
    )

    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        completion_message=random_lower_string()
        + random_text_1
        + random_lower_string(),
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        completion_message=random_text_2,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?completion_message={random_text_1}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?completion_message={random_text_2}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?completion_message={random_lower_string()}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_get_test_by_filter_start_instructions(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    random_text_1 = random_lower_string()
    random_text_2 = random_lower_string()

    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_instructions=random_lower_string() + random_text_1,
    )

    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_instructions=random_lower_string()
        + random_text_1
        + random_lower_string(),
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_instructions=random_text_2,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_instructions={random_text_1}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_instructions={random_text_2}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_instructions={random_lower_string()}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_get_test_by_filter_no_of_attempts(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        no_of_attempts=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        no_of_attempts=2,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        no_of_attempts=3,
    )

    db.add_all([test_1, test_2, test_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts_gte=1&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts_gte=2&no_of_attempts_lte=3&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts_lte=2&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts=1&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts=7&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


def test_get_test_by_filter_shuffle(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=True,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=False,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=True,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=False,
    )

    db.add_all([test_1, test_2, test_3, test_4])
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?shuffle=true&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?shuffle=false&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4


def test_get_test_by_filter_random_questions(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=True,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=False,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=True,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=False,
    )

    db.add_all([test_1, test_2, test_3, test_4])
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?random_questions=true&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?random_questions=false&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4


def test_get_test_by_filter_no_random_questions(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=20,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=10,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=45,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_random_questions_gte=10&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_random_questions_lte=10&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_random_questions_gte=20&no_of_random_questions_lte=45&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_get_test_by_filter_question_pagination(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=2,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=0,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?question_pagination=1&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?question_pagination=2&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


def test_get_test_by_filter_is_template(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)

    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        is_template=True,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        is_template=False,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        is_template=True,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?is_template=true&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?is_template=false&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


def test_get_test_by_filter_created_by(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_1 = create_random_user(db, organization_id=org_id)
    user_2 = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user_1.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user_1.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user_2.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user_1.id}&created_by={user_2.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user_1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_test_order_by(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()

    test_names = sorted([test_1.name, test_2.name, test_3.name], key=str.lower)

    response = client.get(
        f"{settings.API_V1_STR}/test/?order_by=name&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["name"] == test_names[0]
    assert data[1]["name"] == test_names[1]
    assert data[2]["name"] == test_names[2]

    response = client.get(
        f"{settings.API_V1_STR}/test/?order_by=-name&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["name"] == test_names[2]
    assert data[1]["name"] == test_names[1]
    assert data[2]["name"] == test_names[0]

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    test_created_date = [item["created_date"] for item in data]

    sorted_test_created_date = sorted(test_created_date)

    assert sorted_test_created_date == test_created_date

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}&order_by=-created_date",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    test_created_date = [item["created_date"] for item in data]

    sorted_test_created_date = sorted(test_created_date, reverse=True)

    assert sorted_test_created_date == test_created_date

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}&order_by=-name&order_by=created_date",
        headers=get_user_superadmin_token,
    )

    data = response.json()

    test_name_date = [
        {"created_date": item["created_date"], "name": item["name"]} for item in data
    ]

    sort_by_date = sorted(test_name_date, key=lambda x: x["created_date"])
    sorted_array = sorted(sort_by_date, key=lambda x: x["name"].lower(), reverse=True)

    assert sorted_array == test_name_date

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-setting",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid" in data["detail"].lower()

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid" in data["detail"].lower()


def test_get_test_by_id(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    state_a = State(name=random_lower_string(), country_id=country.id)
    db.add(state_a)
    state_b = State(name=random_lower_string(), country_id=country.id)
    db.add(state_b)

    tags = [
        create_random_tag(db),
        create_random_tag(db),
        create_random_tag(db),
        create_random_tag(db),
    ]

    db.add_all(tags)
    db.commit()

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )

    db.add(test)
    db.commit()

    test_tag_links = []
    for tag in tags:
        test_tag_link = TestTag(test_id=test.id, tag_id=tag.id)
        test_tag_links.append(test_tag_link)
    db.add_all(test_tag_links)
    db.commit()

    questions = [
        create_random_question_revision(db),
        create_random_question_revision(db),
        create_random_question_revision(db),
        create_random_question_revision(db),
    ]

    db.add_all(questions)
    db.commit()

    for question in questions:
        test_question_link = TestQuestion(
            test_id=test.id, question_revision_id=question.id
        )
        db.add(test_question_link)
        db.commit()

    states: list[State] = [
        create_random_state(db),
        create_random_state(db),
        create_random_state(db),
        create_random_state(db),
    ]

    db.add_all(states)
    db.commit()

    test_state_links = []
    for state in states:
        db.refresh(state)
        test_state_link = TestState(test_id=test.id, state_id=state.id)
        test_state_links.append(test_state_link)

    db.add_all(test_state_links)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == test.name
    assert data["link"] == test.link
    assert data["created_by_id"] == test.created_by_id
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["marks"] == test.marks
    assert data["completion_message"] == test.completion_message
    assert data["start_instructions"] == test.start_instructions
    assert data["marks_level"] is None
    assert data["no_of_attempts"] == test.no_of_attempts
    assert data["shuffle"] == test.shuffle
    assert data["random_questions"] == test.random_questions

    assert data["no_of_random_questions"] == test.no_of_random_questions

    assert data["question_pagination"] == test.question_pagination
    assert data["is_template"] == test.is_template
    assert data["template_id"] is None
    assert data["is_active"] == test.is_active
    assert data["id"] == test.id

    assert datetime.fromisoformat(data["created_date"]) == test.created_date
    assert datetime.fromisoformat(data["modified_date"]) == test.modified_date

    assert len(data["states"]) == len(states)
    assert len(data["tags"]) == len(tags)
    assert len(data["question_revisions"]) == len(questions)

    for state_data in data["states"]:
        assert any(state_data["id"] == state.id for state in states)
        assert any(state_data["name"] == state.name for state in states)

    for tag_data in data["tags"]:
        assert any(tag_data["id"] == tag.id for tag in tags)
        assert any(tag_data["name"] == tag.name for tag in tags)

    for question_data in data["question_revisions"]:
        assert any(question_data["id"] == question.id for question in questions)
        assert any(
            question_data["question_text"] == question.question_text
            for question in questions
        )
        assert any(
            question_data["question_type"] == question.question_type
            for question in questions
        )
        assert any(
            question_data["options"] == question.options for question in questions
        )
        assert any(
            question_data["correct_answer"] == question.correct_answer
            for question in questions
        )

    test_2 = Test(
        name=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )

    db.add(test_2)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test/{test_2.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test_2.id
    assert data["name"] == test_2.name
    assert data["link"] == test_2.link
    assert data["no_of_random_questions"] == test_2.no_of_random_questions
    assert data["created_by_id"] == test_2.created_by_id
    assert data["is_template"] == test_2.is_template
    assert data["is_active"] == test_2.is_active
    assert datetime.fromisoformat(data["created_date"]) == test_2.created_date
    assert datetime.fromisoformat(data["modified_date"]) == test_2.modified_date

    assert data["tags"] == []
    assert data["states"] == []
    assert data["question_revisions"] == []


def test_update_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    (
        user,
        india,
        stata_a,
        state_b,
        organization,
        tag_type,
        tag_a,
        tag_b,
        question_one,
        question_two,
        question_revision_one,
        question_revision_two,
    ) = setup_data(client, db, get_user_superadmin_token)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()
    modified_date_original = test.modified_date
    created_date_original = test.created_date

    test_tag_link = TestTag(test_id=test.id, tag_id=tag_a.id)
    db.add(test_tag_link)
    db.commit()

    test_tag_link = TestTag(test_id=test.id, tag_id=tag_b.id)
    db.add(test_tag_link)
    db.commit()

    # Create TestQuestion with question_revision_id
    test_question_link = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    db.add(test_question_link)
    db.commit()

    test_state_link = TestState(test_id=test.id, state_id=stata_a.id)
    db.add(test_state_link)
    db.commit()

    state_c = State(name=random_lower_string(), country_id=india.id)
    db.add(state_c)
    db.commit()
    test_state_link = TestState(test_id=test.id, state_id=state_c.id)
    db.add(test_state_link)
    db.commit()

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "start_time": None,
        "end_time": None,
        "time_limit": 120,
        "marks_level": "test",
        "marks": 100,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "no_of_attempts": 3,
        "shuffle": True,
        "random_questions": True,
        "no_of_random_questions": 50,
        "question_pagination": 1,
        "is_template": False,
        "template_id": None,
        "tag_ids": [tag_a.id, tag_b.id],
        "question_revision_ids": [question_revision_one.id],
        "state_ids": [stata_a.id, state_b.id],
    }

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["start_time"] == payload["start_time"]
    assert data["end_time"] == payload["end_time"]
    assert data["time_limit"] == payload["time_limit"]
    assert data["marks_level"] == payload["marks_level"]

    assert data["marks"] == payload["marks"]
    assert data["completion_message"] == payload["completion_message"]
    assert data["start_instructions"] == payload["start_instructions"]
    assert data["link"] == payload["link"]
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == payload["template_id"]
    assert data["created_by_id"] == user.id
    assert "id" in data
    assert "created_date" in data

    created_date = datetime.fromisoformat(data["created_date"])
    assert created_date == created_date_original
    modified_date = datetime.fromisoformat(data["modified_date"])
    assert modified_date != modified_date_original
    assert "modified_date" in data

    assert "tags" in data
    assert len(data["tags"]) == 2
    assert [data["tags"][0]["id"], data["tags"][1]["id"]] == [tag_a.id, tag_b.id]

    assert "question_revisions" in data
    assert len(data["question_revisions"]) == 1
    assert data["question_revisions"][0]["id"] == question_revision_one.id

    assert "states" in data
    assert len(data["states"]) == 2
    assert [data["states"][0]["id"], data["states"][1]["id"]] == [
        stata_a.id,
        state_b.id,
    ]

    # Check test_question_link has the correct question_revision_id
    updated_test_questions = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == test.id)
    ).all()
    assert len(updated_test_questions) == 1
    assert updated_test_questions[0].question_revision_id == question_revision_one.id


def test_visibility_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    response = client.patch(
        f"{settings.API_V1_STR}/test/{test.id}",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["is_active"] is True

    response = client.patch(
        f"{settings.API_V1_STR}/test/{test.id}",
        params={"is_active": False},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["is_active"] is False


def test_delete_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    (
        user,
        india,
        stata_a,
        state_b,
        organization,
        tag_type,
        tag_a,
        tag_b,
        question_one,
        question_two,
        question_revision_one,
        question_revision_two,
    ) = setup_data(client, db, get_user_superadmin_token)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    response = client.delete(
        f"{settings.API_V1_STR}/test/{test.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert "delete" in data["message"]

    response = client.delete(
        f"{settings.API_V1_STR}/test/{test.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert "id" not in data


def test_get_public_test_info(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test the public test endpoint that doesn't require authentication."""
    (
        user,
        india,
        punjab,
        goa,
        organization,
        tag_type,
        tag_hindi,
        tag_marathi,
        question_one,
        question_two,
        question_revision_one,
        question_revision_two,
    ) = setup_data(client, db, get_user_superadmin_token)

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

    # Add questions to test
    test_question_one = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    test_question_two = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_two.id
    )
    db.add_all([test_question_one, test_question_two])
    db.commit()

    # Test public endpoint - no authentication required, uses link UUID
    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["start_instructions"] == test.start_instructions
    assert data["total_questions"] == 2  # We added 2 questions


def test_get_public_test_info_inactive(client: TestClient, db: SessionDep) -> None:
    """Test that inactive tests are not accessible via public endpoint."""
    user = create_random_user(db)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        is_active=False,  # Inactive test
        is_deleted=False,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    assert response.status_code == 404
    assert "Test not found or not active" in response.json()["detail"]


def test_get_public_test_info_deleted(client: TestClient, db: SessionDep) -> None:
    """Test that deleted tests are not accessible via public endpoint."""
    user = create_random_user(db)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=True,  # Deleted test
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    assert response.status_code == 404
    assert "Test not found or not active" in response.json()["detail"]


def test_get_time_before_test_start_public(client: TestClient, db: SessionDep) -> None:
    fake_current_time = datetime(2024, 5, 24, 10, 0, 0)  # Fixed time for testing
    with patch("app.api.routes.test.get_current_time", return_value=fake_current_time):
        future_start_time = fake_current_time + timedelta(
            minutes=10
        )  # 10 minutes from now``
        test = Test(
            name="Public Start Timer Test",
            link="public-test-uuid",
            is_active=True,
            is_deleted=False,
            start_time=future_start_time,
            created_by_id=create_random_user(db).id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/{test.link}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data
        time_left = data["time_left"]
        assert isinstance(time_left, int)
        assert time_left == 600


def test_public_timer_when_test_already_started(
    client: TestClient, db: SessionDep
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch("app.api.routes.test.get_current_time", return_value=fake_current_time):
        test = Test(
            name="Public Start Timer Test",
            link="public-test-uuid1",
            is_active=True,
            is_deleted=False,
            start_time=datetime(2024, 5, 24, 9, 0, 0),
            end_time=fake_current_time + timedelta(days=1),
            created_by_id=create_random_user(db).id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/{test.link}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "time_left" in data
        assert data["time_left"] == 0


def test_public_timer_test_not_found_or_not_active(
    client: TestClient, db: SessionDep
) -> None:
    fake_current_time = datetime(2024, 5, 24, 11, 0, 0)  # Fixed time for testing
    with patch("app.api.routes.test.get_current_time", return_value=fake_current_time):
        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/nonexistent-test-link"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Test not found or not active"
        user = create_random_user(db)
        deleted_test = Test(
            name="Deleted Test",
            link="deleted-test-link",
            start_time=fake_current_time + timedelta(minutes=10),
            end_time=fake_current_time + timedelta(hours=2),
            time_limit=60,
            is_active=True,
            is_deleted=True,  # Marked as deleted
            created_by_id=user.id,
        )
        db.add(deleted_test)
        db.commit()
        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/{deleted_test.link}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Test not found or not active"


def test_public_timer_returns_zero_if_start_time_none(
    client: TestClient, db: SessionDep
) -> None:
    test = Test(
        name="Test with no start time",
        link="test-no-start-time",
        is_active=True,
        is_deleted=False,
        start_time=None,  # This is the key for this test
        created_by_id=create_random_user(db).id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    response = client.get(f"{settings.API_V1_STR}/test/public/time_left/{test.link}")
    assert response.status_code == 200
    data = response.json()
    assert data == {"time_left": 0}


def test_get_inactive_tests_not_listed(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 15,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "is_active": False,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    test_id = data["id"]
    assert data["is_active"] is False

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert all(item["id"] != test_id for item in data)


def test_get_tests_filtered_by_organization(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test1 = Test(
        name="Org Test",
        description=random_lower_string(),
        organization_id=org_id,
        time_limit=30,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=True,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test1)
    other_org = create_random_organization(db)
    other_user = create_random_user(db, organization_id=other_org.id)
    test2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=other_org.id,
        time_limit=30,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=True,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=False,
        created_by_id=other_user.id,
    )
    db.add(test2)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data]
    assert test1.id in ids
    assert test2.id not in ids
