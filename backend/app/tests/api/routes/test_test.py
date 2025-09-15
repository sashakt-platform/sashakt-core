import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.api.routes.utils import get_current_time
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
from app.models.candidate import Candidate, CandidateTest, CandidateTestAnswer
from app.models.entity import Entity, EntityType
from app.models.location import Block, District
from app.models.question import QuestionType
from app.models.test import TestDistrict
from app.tests.utils.location import create_random_state
from app.tests.utils.organization import (
    create_random_organization,
)
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.tag import create_random_tag
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import assert_paginated_response, random_lower_string


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

    district_a = District(name=random_lower_string(), state_id=punjab.id)
    db.add(district_a)
    db.commit()

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 2,
        "marks": 3,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
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
        "district_ids": [district_a.id],
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
    assert data["marks_level"] == "question"
    assert data["link"] == payload["link"]
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["created_by_id"] == user_id
    assert len(data["districts"]) == 1
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
    assert data["marks_level"] == "question"
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
    assert data["marks_level"] == "question"
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


def test_create_test_with_random_tag_count(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    tag1 = create_random_tag(db)
    tag2 = create_random_tag(db)

    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": random_lower_string(),
        "random_tag_count": [
            {"tag_id": tag1.id, "count": 3},
            {"tag_id": tag2.id, "count": 2},
        ],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data["random_tag_counts"]) == 2
    assert data["random_tag_counts"][0]["count"] == 3
    assert data["random_tag_counts"][0]["tag"]["id"] == tag1.id
    assert data["random_tag_counts"][1]["count"] == 2
    assert data["random_tag_counts"][1]["tag"]["id"] == tag2.id


def test_create_test_random_question_field(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)

    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "link": random_lower_string(),
        "random_questions": False,
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
    district = District(name=random_lower_string(), state_id=state_a.id)
    db.add(district)
    db.commit()
    db.refresh(district)
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
    test_district_link = TestDistrict(test_id=test.id, district_id=district.id)
    db.add(test_district_link)
    db.commit()

    get_response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )
    response = get_response.json()
    data = response["items"]
    assert_paginated_response(get_response, min_expected_total=1)

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
    assert any(
        len(item["districts"]) == 1 and item["districts"][0]["id"] == district.id
        for item in data
    )


def test_get_tests_with_tag_random_count(
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
    district = District(name=random_lower_string(), state_id=state_a.id)
    db.add(district)
    db.commit()
    db.refresh(district)

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
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
        random_tag_count=[
            {"tag_id": tag_a.id, "count": 3},
            {"tag_id": tag_b.id, "count": 2},
        ],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestTag(test_id=test.id, tag_id=tag_a.id))
    db.commit()

    get_response = client.get(
        f"{settings.API_V1_STR}/test/?name={test.name}",
        headers=get_user_superadmin_token,
    )
    response = get_response.json()
    data = response["items"]
    assert any(item["name"] == test.name for item in data)
    assert any(item["description"] == test.description for item in data)
    assert any(item["time_limit"] == test.time_limit for item in data)

    test_data = data[0]
    assert len(test_data["random_tag_counts"]) == 2
    first_random_tag = test_data["random_tag_counts"][0]
    assert first_random_tag["count"] == 3
    assert first_random_tag["tag"]["id"] == tag_a.id
    assert first_random_tag["tag"]["name"] == tag_a.name
    second_random_tag = test_data["random_tag_counts"][1]
    assert second_random_tag["count"] == 2
    assert second_random_tag["tag"]["id"] == tag_b.id
    assert second_random_tag["tag"]["name"] == tag_b.name


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

    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    assert_paginated_response(response, min_expected_total=3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?name={test_name_2}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    assert_paginated_response(response)


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

    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, min_expected_total=3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?description={random_text_2}",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)


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

    assert_paginated_response(response, expected_total=4)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-27T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=2)
    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-28T15:30:59Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)
    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-28T19:31:00Z",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    assert_paginated_response(
        response, expected_total=0, expected_page=1, expected_pages=0
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-24T00:00:00Z&start_time_lte=2025-07-26T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_gte=2025-07-27T12:30:00Z&start_time_lte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_lte=2025-07-28T15:30:00Z&start_time_gte=2025-07-25T10:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=3)


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

    assert_paginated_response(response, expected_total=4)
    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-27T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=3)
    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=2)
    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-28T15:30:59Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)
    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-28T19:31:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(
        response, expected_total=0, expected_page=1, expected_pages=0
    )

    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-24T00:00:00Z&end_time_lte=2025-07-26T00:00:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)
    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_gte=2025-07-27T12:30:00Z&end_time_lte=2025-07-28T15:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=2)
    response = client.get(
        f"{settings.API_V1_STR}/test/?end_time_lte=2025-07-28T15:30:00Z&end_time_gte=2025-07-25T10:30:00Z",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=3)


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

    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_time_lte=2025-04-28T00:00:00Z&end_time_gte=2025-04-27T12:30:00Z",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)


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

    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?time_limit_gte=31&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?time_limit_lte=40&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=2)


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
    assert_paginated_response(response, min_expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?completion_message={random_text_2}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response)

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, min_expected_total=3, min_expected_pages=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?completion_message={random_lower_string()}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(
        response, expected_total=0, expected_page=1, expected_pages=0
    )


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
    assert_paginated_response(response, min_expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_instructions={random_text_2}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, min_expected_total=3, min_expected_pages=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?start_instructions={random_lower_string()}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(
        response, expected_total=0, expected_page=1, expected_pages=0
    )


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
    assert_paginated_response(response, expected_total=3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts_gte=2&no_of_attempts_lte=3&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=2)
    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts_lte=2&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts=1&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_attempts=7&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=0, expected_pages=0)


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
    assert_paginated_response(response, expected_total=2)
    response = client.get(
        f"{settings.API_V1_STR}/test/?shuffle=false&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=2)
    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=4)


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
    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?random_questions=false&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=4)


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
    assert_paginated_response(response, expected_total=3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_random_questions_lte=10&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?no_of_random_questions_gte=20&no_of_random_questions_lte=45&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=3)


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
    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?question_pagination=2&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=3)


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
    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?is_template=false&created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=1)

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=3)


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

    assert_paginated_response(response, expected_total=3)

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user_1.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=2)


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
    item = response.json()
    data = item["items"]
    assert_paginated_response(response, expected_total=3)
    assert data[0]["name"] == test_names[0]
    assert data[1]["name"] == test_names[1]
    assert data[2]["name"] == test_names[2]

    response = client.get(
        f"{settings.API_V1_STR}/test/?order_by=-name&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    data = data["items"]
    assert_paginated_response(response, expected_total=3)
    assert data[0]["name"] == test_names[2]
    assert data[1]["name"] == test_names[1]
    assert data[2]["name"] == test_names[0]

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    data = data["items"]

    test_created_date = [item["created_date"] for item in data]

    sorted_test_created_date = sorted(test_created_date)

    assert sorted_test_created_date == test_created_date

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}&order_by=-created_date",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    data = data["items"]
    test_created_date = [item["created_date"] for item in data]

    sorted_test_created_date = sorted(test_created_date, reverse=True)

    assert sorted_test_created_date == test_created_date

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}&order_by=-name&order_by=created_date",
        headers=get_user_superadmin_token,
    )

    data = response.json()
    data = data["items"]
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


def test_get_test_random_tag_count(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    tag1 = Tag(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=org_id,
    )

    tag2 = Tag(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=org_id,
    )

    db.add_all([tag1, tag2])
    db.commit()
    db.refresh(tag1)
    db.refresh(tag2)

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link="test-link",
        random_tag_count=[
            {"tag_id": tag1.id, "count": 3},
            {"tag_id": tag2.id, "count": 2},
        ],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    data = response.json()
    random_tag_counts = data["random_tag_counts"]

    assert len(random_tag_counts) == 2
    assert random_tag_counts[0]["count"] == 3
    assert random_tag_counts[0]["tag"]["id"] == tag1.id
    assert random_tag_counts[0]["tag"]["name"] == tag1.name
    assert random_tag_counts[1]["count"] == 2
    assert random_tag_counts[1]["tag"]["id"] == tag2.id
    assert random_tag_counts[1]["tag"]["name"] == tag2.name


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
    assert data["marks_level"] == "question"
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
    district_a = District(name=random_lower_string(), state_id=state_b.id)
    db.add(district_a)
    db.commit()
    district_b = District(name=random_lower_string(), state_id=state_b.id)
    db.add(district_b)
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
    modified_date_original = test.modified_date
    created_date_original = test.created_date

    test_tag_link = TestTag(test_id=test.id, tag_id=tag_a.id)
    db.add(test_tag_link)
    db.commit()

    test_tag_link = TestTag(test_id=test.id, tag_id=tag_b.id)
    db.add(test_tag_link)
    db.commit()

    test_district_b = TestDistrict(test_id=test.id, district_id=district_b.id)
    db.add(test_district_b)
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
        "no_of_random_questions": 1,
        "question_pagination": 1,
        "is_template": False,
        "template_id": None,
        "tag_ids": [tag_a.id, tag_b.id],
        "question_revision_ids": [question_revision_one.id],
        "state_ids": [stata_a.id, state_b.id],
        "district_ids": [district_a.id],
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
    assert "districts" in data
    assert len(data["districts"]) == 1
    assert data["districts"][0]["id"] == district_a.id

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


def test_visibility_test_with_random_tag_count(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    tag1 = create_random_tag(db)
    tag2 = create_random_tag(db)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=False,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
        random_tag_count=[
            {"tag_id": tag1.id, "count": 3},
            {"tag_id": tag2.id, "count": 2},
        ],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.patch(
        f"{settings.API_V1_STR}/test/{test.id}",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["is_active"] is True
    assert len(data["random_tag_counts"]) == 2
    assert data["random_tag_counts"][0]["count"] == 3
    assert data["random_tag_counts"][0]["tag"]["id"] == tag1.id
    assert data["random_tag_counts"][1]["count"] == 2
    assert data["random_tag_counts"][1]["tag"]["id"] == tag2.id

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data["random_tag_counts"]) == 2
    assert data["random_tag_counts"][0]["count"] == 3
    assert data["random_tag_counts"][0]["tag"]["id"] == tag1.id
    assert data["random_tag_counts"][1]["count"] == 2
    assert data["random_tag_counts"][1]["tag"]["id"] == tag2.id


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


def test_bulk_delete_test(
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
        link=random_lower_string(),
        no_of_attempts=1,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()
    test2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        link=random_lower_string(),
        no_of_attempts=1,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test2)
    db.commit()

    response = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/test/",
        json=[test.id, test2.id],
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["delete_success_count"] == 2
    assert data["delete_failure_list"] is None or len(data["delete_failure_list"]) == 0


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


def test_get_public_test_info_with_random_tag_count(
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

    # Create a test
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
        random_tag_count=[{"tag_id": 1, "count": 3}, {"tag_id": 2, "count": 2}],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    test_question_one = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    test_question_two = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_two.id
    )
    db.add_all([test_question_one, test_question_two])
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["start_instructions"] == test.start_instructions
    assert data["total_questions"] == 7


def test_get_public_test_info_with_random_questions(
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

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user.id,
        random_questions=True,
        no_of_random_questions=1,
        random_tag_count=[{"tag_id": 1, "count": 3}, {"tag_id": 2, "count": 2}],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    test_question_one = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    test_question_two = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_two.id
    )
    db.add_all([test_question_one, test_question_two])
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["total_questions"] == 6


def test_get_public_test_info_with_tag_count_only(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test public test endpoint with only tag-based random questions (no fixed questions, random_questions=False)."""
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

    test = Test(
        name=random_lower_string(),
        time_limit=30,
        marks=50,
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        random_tag_count=[{"tag_id": 1, "count": 4}, {"tag_id": 2, "count": 3}],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["total_questions"] == 7


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


def test_get_inactive_tests_listed(
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
        f"{settings.API_V1_STR}/test/?is_active=false",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert_paginated_response(response, expected_total=1)
    assert "items" in data
    items = data["items"]
    assert response.status_code == 200
    assert any(item["id"] == test_id for item in items)


def test_clone_test(
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
    user1 = create_random_user(db)
    superadmin = get_current_user_data(client, get_user_superadmin_token)
    district = District(name="Ludhiana", state_id=punjab.id)
    db.add(district)
    db.commit()
    db.refresh(district)
    test = Test(
        name="Original Test",
        description=random_lower_string(),
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
        created_by_id=user1.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    db.add_all(
        [
            TestTag(test_id=test.id, tag_id=tag_hindi.id),
            TestTag(test_id=test.id, tag_id=tag_marathi.id),
            TestState(test_id=test.id, state_id=punjab.id),
            TestState(test_id=test.id, state_id=goa.id),
            TestDistrict(test_id=test.id, district_id=district.id),
            TestQuestion(
                test_id=test.id, question_revision_id=question_revision_one.id
            ),
            TestQuestion(
                test_id=test.id, question_revision_id=question_revision_two.id
            ),
        ]
    )
    db.commit()
    response = client.post(
        f"{settings.API_V1_STR}/test/{test.id}/clone",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] != test.id
    assert data["name"].startswith("Copy of ")
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["marks"] == test.marks
    assert data["completion_message"] == test.completion_message
    assert data["start_instructions"] == test.start_instructions
    assert data["no_of_attempts"] == test.no_of_attempts
    assert data["shuffle"] == test.shuffle
    assert data["random_questions"] == test.random_questions
    assert data["no_of_random_questions"] == test.no_of_random_questions
    assert data["question_pagination"] == test.question_pagination
    assert data["is_template"] == test.is_template
    assert data["created_by_id"] != test.created_by_id
    assert data["created_by_id"] == superadmin["id"]
    assert data["link"] is not None
    assert data["link"] != test.link
    assert len(data["tags"]) == 2
    tag_ids = [tag["id"] for tag in data["tags"]]
    assert set(tag_ids) == {tag_hindi.id, tag_marathi.id}
    assert len(data["states"]) == 2
    state_ids = [state["id"] for state in data["states"]]
    assert set(state_ids) == {punjab.id, goa.id}
    assert len(data["question_revisions"]) == 2
    qrev_ids = [q["id"] for q in data["question_revisions"]]
    assert set(qrev_ids) == {question_revision_one.id, question_revision_two.id}
    assert len(data["districts"]) == 1
    district_ids = [d["id"] for d in data["districts"]]
    assert district.id in district_ids


def test_clone_test_with_random_tag(
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
    user1 = create_random_user(db)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        no_of_attempts=1,
        shuffle=True,
        random_questions=True,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=False,
        created_by_id=user1.id,
        random_tag_count=[
            {"tag_id": tag_hindi.id, "count": 5},
            {"tag_id": tag_marathi.id, "count": 3},
        ],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Clone the test
    response = client.post(
        f"{settings.API_V1_STR}/test/{test.id}/clone",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] != test.id
    assert data["name"].startswith("Copy of ")
    assert data["description"] == test.description

    assert len(data["random_tag_counts"]) == 2
    assert data["random_tag_counts"][0]["count"] == 5
    assert data["random_tag_counts"][0]["tag"]["id"] == tag_hindi.id
    assert data["random_tag_counts"][1]["count"] == 3
    assert data["random_tag_counts"][1]["tag"]["id"] == tag_marathi.id


def test_clone_soft_deleted_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    test = Test(
        name="Soft Deleted Test",
        description=random_lower_string(),
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
        is_deleted=True,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    response = client.post(
        f"{settings.API_V1_STR}/test/{test.id}/clone",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Test not found"


def test_clone_template_test_link_not_copied(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    tag = create_random_tag(db)
    state = create_random_state(db)
    question_revision = create_random_question_revision(db)

    # Create a template test
    test = Test(
        name="Template Test",
        description=random_lower_string(),
        time_limit=30,
        marks=10,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        no_of_attempts=1,
        shuffle=True,
        random_questions=False,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    db.add(TestTag(test_id=test.id, tag_id=tag.id))
    db.add(TestState(test_id=test.id, state_id=state.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision.id))
    db.commit()

    # Clone the template test
    response = client.post(
        f"{settings.API_V1_STR}/test/{test.id}/clone",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] != test.id
    assert data["is_template"] is True
    assert data["name"].startswith("Copy of ")
    assert data.get("link") is None


def test_get_test_by_filter_case_insensitive_name(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name="python test",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    test_2 = Test(
        name="PyThon advanced test",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )

    test_3 = Test(
        name=" beginner test PYTHON",
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
        f"{settings.API_V1_STR}/test/?name=python",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 3

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) >= 3

    response = client.get(
        f"{settings.API_V1_STR}/test/?name=PYTHON",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=3)


def test_get_tests_by_tags_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    tag_type = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(tag_type)
    db.commit()
    db.refresh(tag_type)
    tag_1 = Tag(
        name=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type.id,
    )
    tag_2 = Tag(
        name=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type.id,
    )
    tag_3 = Tag(
        name="english",
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type.id,
    )
    db.add_all([tag_1, tag_2, tag_3])
    db.commit()
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_5 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3, test_4, test_5])
    db.commit()
    db.refresh(test_1)
    db.refresh(test_2)
    db.refresh(test_3)
    test_tag_link_1 = TestTag(test_id=test_1.id, tag_id=tag_1.id)
    test_tag_link_2 = TestTag(test_id=test_2.id, tag_id=tag_2.id)
    test_tag_link_3 = TestTag(test_id=test_3.id, tag_id=tag_3.id)
    test_tag_link_4 = TestTag(test_id=test_4.id, tag_id=tag_1.id)
    test_tag_link_5 = TestTag(test_id=test_5.id, tag_id=tag_2.id)
    test_tag_link_6 = TestTag(test_id=test_5.id, tag_id=tag_3.id)

    db.add_all(
        [
            test_tag_link_1,
            test_tag_link_2,
            test_tag_link_3,
            test_tag_link_4,
            test_tag_link_5,
            test_tag_link_6,
        ]
    )
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_ids={tag_1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    assert {test["id"] for test in items} == {test_1.id, test_4.id}
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_ids={tag_2.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    assert {test["id"] for test in items} == {test_2.id, test_5.id}
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_ids={tag_3.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    assert {test["id"] for test in items} == {test_3.id, test_5.id}
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_ids={tag_2.id}&tag_ids={tag_3.id}",
        headers=get_user_superadmin_token,
    )
    assert_paginated_response(response, expected_total=3)


def test_get_tests_by_tags_type_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    tag_type1 = TagType(
        name="Skill Category",
        description="Example tag type",
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(tag_type1)
    db.commit()
    db.refresh(tag_type1)
    tag_type2 = TagType(
        name="proficiency",
        description="Example tag type for proficiency",
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(tag_type2)
    db.commit()
    db.refresh(tag_type2)
    tag_type3 = TagType(
        name="skills",
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(tag_type3)
    db.commit()
    db.refresh(tag_type3)
    tag_1 = Tag(
        name="aptitude",
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type1.id,
    )
    tag_2 = Tag(
        name="logic",
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type1.id,
    )
    tag_3 = Tag(
        name="english",
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type2.id,
    )
    db.add_all([tag_1, tag_2, tag_3])
    db.commit()
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_5 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_6 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3, test_4, test_5, test_6])
    db.commit()
    db.refresh(test_1)
    db.refresh(test_2)
    db.refresh(test_3)
    test_tag_link_1 = TestTag(test_id=test_1.id, tag_id=tag_1.id)
    test_tag_link_2 = TestTag(test_id=test_2.id, tag_id=tag_2.id)
    test_tag_link_3 = TestTag(test_id=test_3.id, tag_id=tag_3.id)
    test_tag_link_4 = TestTag(test_id=test_4.id, tag_id=tag_1.id)
    test_tag_link_5 = TestTag(test_id=test_5.id, tag_id=tag_2.id)
    test_tag_link_6 = TestTag(test_id=test_5.id, tag_id=tag_3.id)

    db.add_all(
        [
            test_tag_link_1,
            test_tag_link_2,
            test_tag_link_3,
            test_tag_link_4,
            test_tag_link_5,
            test_tag_link_6,
        ]
    )
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 4
    assert {test["id"] for test in data["items"]} == {
        test_1.id,
        test_2.id,
        test_4.id,
        test_5.id,
    }
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type2.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert {test["id"] for test in data["items"]} == {test_3.id, test_5.id}
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type2.id}&tag_type_ids={tag_type1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert test_6.id not in (test["id"] for test in data["items"])
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type3.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


def test_get_tests_by_state_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    country = Country(name="India", is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state_1 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_2 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_1, state_2])
    db.commit()
    db.refresh(state_1)
    db.refresh(state_2)
    test_1 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()
    db.refresh(test_1)
    db.refresh(test_2)
    db.refresh(test_3)
    test_state_1 = TestState(test_id=test_1.id, state_id=state_1.id)
    test_state_2 = TestState(test_id=test_2.id, state_id=state_2.id)
    test_state_3a = TestState(test_id=test_3.id, state_id=state_1.id)
    test_state_3b = TestState(test_id=test_3.id, state_id=state_2.id)
    db.add_all([test_state_1, test_state_2, test_state_3a, test_state_3b])
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?state_ids={state_1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    assert {test["id"] for test in items} == {test_1.id, test_3.id}
    response = client.get(
        f"{settings.API_V1_STR}/test/?state_ids={state_2.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    assert {test["id"] for test in items} == {test_2.id, test_3.id}
    response = client.get(
        f"{settings.API_V1_STR}/test/?state_ids={state_1.id}&state_ids={state_2.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 3
    assert {test["id"] for test in items} == {test_1.id, test_2.id, test_3.id}


def test_get_tests_by_combined_name_tag_state_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    country = Country(name="India", is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    tag_type = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(tag_type)
    db.commit()
    db.refresh(tag_type)
    tag = Tag(
        name="aptitude",
        organization_id=user.organization_id,
        created_by_id=user.id,
        tag_type_id=tag_type.id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    test_1 = Test(
        name="Python Aptitude Test",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add(test_1)
    db.commit()
    db.refresh(test_1)
    db.add_all(
        [
            TestTag(test_id=test_1.id, tag_id=tag.id),
            TestState(test_id=test_1.id, state_id=state.id),
        ]
    )
    db.commit()
    test_2 = Test(
        name="Java Test",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add(test_2)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?name=python&tag_ids={tag.id}&state_ids={state.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 1
    assert items[0]["id"] == test_1.id
    assert_paginated_response(response, expected_total=1)


def test_get_tests_by_case_insensitive_description_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    keyword = "importantDescription"
    test_1 = Test(
        name=random_lower_string(),
        description=keyword,  # exact case
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_2 = Test(
        name=random_lower_string(),
        description="someText" + keyword.upper() + "moreText",  # upper case
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    test_3 = Test(
        name=random_lower_string(),
        description="completely different",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?description={keyword}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) == 2
    returned_ids = {test["id"] for test in items}
    assert test_1.id in returned_ids
    assert test_2.id in returned_ids
    assert test_3.id not in returned_ids


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
        f"{settings.API_V1_STR}/test/?size=100",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    items = data["items"]
    ids = [item["id"] for item in items]
    assert test1.id in ids
    assert test2.id not in ids


def test_get_all_tests_includes_active_and_inactive(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    active_test = Test(
        name="Active Test",
        is_active=True,
        is_deleted=False,
        created_by_id=user_id,
    )
    db.add(active_test)
    inactive_test = Test(
        name="Inactive Test",
        is_active=False,
        is_deleted=False,
        created_by_id=user_id,
    )
    db.add(inactive_test)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/?size=100",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    test_names = [test["name"] for test in items]
    assert "Active Test" in test_names
    assert "Inactive Test" in test_names
    response = client.get(
        f"{settings.API_V1_STR}/test/?is_active=true&size=100",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    names = [test["name"] for test in items]
    assert "Active Test" in names
    assert "Inactive Test" not in names
    response = client.get(
        f"{settings.API_V1_STR}/test/?is_active=false&size=100",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    name = [test["name"] for test in items]
    assert "Inactive Test" in name
    assert "Active Test" not in name


def test_create_test_end_time_before_start_time(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    start_time = "2025-07-19T10:00:00Z"
    end_time = "2025-07-18T12:00:00Z"
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "start_time": start_time,
        "end_time": end_time,
        "time_limit": 10,
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert "End time cannot be earlier than start time" in response.json()["detail"]


def test_create_test_time_limit_exceeds_duration(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    start_time = "2025-07-19T10:00:00Z"
    end_time = "2025-07-19T10:30:00Z"
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "start_time": start_time,
        "end_time": end_time,
        "time_limit": 70,
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert (
        "Time limit cannot be more than the duration between start and end time"
        in response.json()["detail"]
    )


def test_update_test_time_limit_exceeds_duration(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        start_time="2025-07-19T10:00:00Z",
        end_time="2025-07-19T10:30:00Z",
        time_limit=30,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 60,
    }
    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    data = response.json()
    assert "Time limit cannot be more than the duration" in data["detail"]


def test_update_test_end_time_before_start_time(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        start_time="2025-07-19T10:00:00Z",
        end_time="2025-07-19T11:00:00Z",
        time_limit=60,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    payload = {
        "name": random_lower_string(),
        "start_time": "2025-07-20T10:00:00Z",
        "end_time": "2025-07-19T10:00:00Z",
        "time_limit": 10,
    }
    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert "End time cannot be earlier than start time" in response.json()["detail"]


def test_create_test_start_and_end_time_same(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    start_time = "2025-07-19T10:00:00Z"
    end_time = "2025-07-19T10:00:00Z"
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "start_time": start_time,
        "end_time": end_time,
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert "End time cannot be earlier than start time" in response.json()["detail"]


def test_create_test_valid_data_success(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)
    payload = {
        "name": random_lower_string(),
        "created_by_id": user.id,
        "start_time": "2025-07-19T10:00:00Z",
        "end_time": "2025-07-19T11:00:00Z",
        "time_limit": 30,
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200


def test_get_public_test_info_expire_test(
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
    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        marks=80,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        start_time=get_current_time() - timedelta(hours=1),
        end_time=get_current_time() - timedelta(minutes=10),
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    test_question_one = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    test_question_two = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_two.id
    )
    db.add_all([test_question_one, test_question_two])
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()
    assert response.status_code == 400
    assert data["detail"] == "Test has already ended"


def test_random_questions_validation(
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

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 20,
        "marks": 30,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "marks_level": None,
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": True,
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
    assert response.status_code == 400
    assert "cannot be greater than total questions added" in response.json()["detail"]


def test_random_questions_valid_case(
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

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 30,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": True,
        "no_of_random_questions": 2,
        "question_pagination": 1,
        "is_template": False,
        "tag_ids": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [
            question_revision_one.id,
            question_revision_two.id,
        ],
        "state_ids": [punjab.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["random_questions"] is True
    assert data["no_of_random_questions"] == 2
    assert len(data["question_revisions"]) == 2


def test_update_test_random_question_validation_fails(
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
        name="Sample Test",
        description="Initial test",
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link=random_lower_string(),
        no_of_attempts=2,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=None,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    test_question = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    db.add(test_question)
    db.commit()

    payload = {
        "name": "Sample Test",
        "random_questions": True,
        "no_of_random_questions": 5,
        "tag_ids": [tag_a.id],
        "state_ids": [state_a.id],
    }

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No. of random questions (5) cannot be greater than total questions added (1)"
    )


def test_update_test_random_question_success(
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
        name="Sample Test",
        description=random_lower_string(),
        time_limit=30,
        marks=5,
        completion_message=random_lower_string(),
        start_instructions=random_lower_string(),
        marks_level=None,
        link="test-link",
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision_one.id))

    db.commit()

    payload = {
        "name": "Sample Test Updated",
        "random_questions": True,
        "no_of_random_questions": 2,
        "tag_ids": [tag_a.id, tag_b.id],
        "state_ids": [state_a.id, state_b.id],
        "question_revision_ids": [question_revision_one.id, question_revision_two.id],
    }

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["random_questions"] is True
    assert data["no_of_random_questions"] == 2


def test_get_public_test(
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

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=45,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
        random_questions=True,
        no_of_random_questions=4,
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
        db.flush()
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
        db.flush()
        db.refresh(q)
        all_question_ids.append(q.id)
        question.last_revision_id = q.id
        db.add(question)
        tq = TestQuestion(test_id=test.id, question_revision_id=q.id)
        db.add(tq)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    assert data["total_questions"] == 4


def test_default_marks_level_question(
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
    org_id = user_data["organization_id"]

    question_one = Question(organization_id=org_id)
    question_two = Question(organization_id=org_id)
    db.add(question_one)
    db.add(question_two)
    db.commit()
    question_revision1 = QuestionRevision(
        question_id=question_one.id,
        created_by_id=user_id,
        question_text="what is pen",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
    )

    question_revision2 = QuestionRevision(
        question_id=question_two.id,
        created_by_id=user_id,
        question_text="what is paper",
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
        ],
        correct_answer=[1],
        marking_scheme={"correct": 2.0, "wrong": 0.0, "skipped": 0.0},
    )

    db.add(question_revision1)
    db.add(question_revision2)
    db.commit()
    db.flush()

    question_one.last_revision_id = question_revision1.id
    question_two.last_revision_id = question_revision2.id
    db.commit()
    db.refresh(question_one)
    db.refresh(question_two)
    db.refresh(question_revision1)
    db.refresh(question_revision2)

    payload = {
        "name": "test for default marking scheme",
        "description": random_lower_string(),
        "time_limit": 2,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "tag_ids": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question_revision1.id, question_revision2.id],
        "state_ids": [punjab.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["marks_level"] == "question"
    assert len(data["question_revisions"]) == 2
    assert data["question_revisions"][0]["marking_scheme"] == {
        "correct": 1.0,
        "wrong": 0.0,
        "skipped": 0.0,
    }
    assert data["question_revisions"][1]["marking_scheme"] == {
        "correct": 2.0,
        "wrong": 0.0,
        "skipped": 0.0,
    }


def test_create_test_marks_level_test(
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

    org_id = user_data["organization_id"]
    question1_data = {
        "organization_id": org_id,
        "question_text": "What is dict in Python",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Object-oriented language"},
            {"id": 2, "key": "B", "value": "Database"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
        "tag_ids": [],
        "marking_scheme": {"correct": 5.0, "wrong": 0.0, "skipped": 0.0},
    }
    response1 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question1_data,
        headers=get_user_superadmin_token,
    )
    assert response1.status_code == 200
    data1 = response1.json()

    question1_data_id = data1["latest_question_revision_id"]
    assert data1["question_text"] == "What is dict in Python"
    assert data1["tags"] == []

    question2_data = {
        "organization_id": org_id,
        "question_text": "What are the concept of Python",
        "question_type": QuestionType.single_choice,
        "options": [
            {"id": 1, "key": "A", "value": "Object-oriented language"},
            {"id": 2, "key": "B", "value": "Database"},
        ],
        "correct_answer": [1],
        "is_mandatory": True,
    }
    response2 = client.post(
        f"{settings.API_V1_STR}/questions/",
        json=question2_data,
        headers=get_user_superadmin_token,
    )

    assert response2.status_code == 200

    data2 = response2.json()
    assert data2["question_text"] == "What are the concept of Python"
    question2_data_id = data2["latest_question_revision_id"]

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 20,
        "marks": 4,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "tag_ids": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question1_data_id, question2_data_id],
        "state_ids": [punjab.id],
        "marks_level": "test",
        "marking_scheme": {"correct": 7, "wrong": 0, "skipped": 0},
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
    assert data["marks_level"] == "test"
    assert data["link"] == payload["link"]
    revision1 = db.get(QuestionRevision, question1_data_id)
    revision2 = db.get(QuestionRevision, question2_data_id)
    expected_scheme1 = {"correct": 5.0, "wrong": 0, "skipped": 0}
    expected_scheme2 = {"correct": 1, "wrong": 0, "skipped": 0}
    assert revision1 is not None
    assert revision2 is not None
    assert revision1.marking_scheme == expected_scheme1
    assert revision2.marking_scheme == expected_scheme2
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 20,
        "marks": 4,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "tag_ids": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question1_data_id, question2_data_id],
        "state_ids": [punjab.id],
        "marks_level": "test",
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert revision1.marking_scheme == expected_scheme1
    assert revision2.marking_scheme == expected_scheme2


def test_mapping_test_with_district(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district_1 = District(name=random_lower_string(), is_active=True, state_id=state.id)
    district_2 = District(name=random_lower_string(), is_active=True, state_id=state.id)
    db.add_all([district_1, district_2])
    db.commit()
    db.refresh(district_1)
    db.refresh(district_2)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "completion_message": random_lower_string(),
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": True,
        "random_questions": False,
        "no_of_random_questions": 2,
        "question_pagination": 1,
        "is_template": False,
        "created_by_id": user.id,
        "tag_ids": [],
        "district_ids": [district_1.id, district_2.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_payload["name"]
    assert data["description"] == test_payload["description"]

    assert len(data["districts"]) == 2
    districts_ids = [d["id"] for d in data["districts"]]
    districts_names = [d["name"] for d in data["districts"]]
    districts_state_ids = [d["state_id"] for d in data["districts"]]

    # Check that both district IDs from our test are in the response
    assert district_1.id in districts_ids
    assert district_2.id in districts_ids

    # Check that both district names are in the response
    assert district_1.name in districts_names
    assert district_2.name in districts_names

    # Check that both districts have the correct state ID
    assert all(sid == state.id for sid in districts_state_ids)

    # Check that all districts are active
    assert all(d["is_active"] for d in data["districts"])

    # Check all district entries have required fields
    for district in data["districts"]:
        assert "is_active" in district
        assert "created_date" in district
        assert "modified_date" in district

    state_3 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_3)
    db.commit()
    db.refresh(state_3)

    district_3 = District(
        name=random_lower_string(), is_active=True, state_id=state_3.id
    )
    db.add(district_3)
    db.commit()
    db.refresh(district_3)

    # Update the test to include a new district
    test_payload["district_ids"] = [district_2.id, district_3.id]
    response = client.put(
        f"{settings.API_V1_STR}/test/{data['id']}",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["name"] == test_payload["name"]
    assert updated_data["description"] == test_payload["description"]
    assert len(updated_data["districts"]) == 2
    updated_districts_ids = [d["id"] for d in updated_data["districts"]]
    assert district_2.id in updated_districts_ids
    assert district_3.id in updated_districts_ids

    response = client.get(
        f"{settings.API_V1_STR}/test/{data['id']}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    fetched_data = response.json()
    assert fetched_data["name"] == test_payload["name"]
    assert fetched_data["description"] == test_payload["description"]
    assert len(fetched_data["districts"]) == 2
    fetched_districts_ids = [d["id"] for d in fetched_data["districts"]]
    assert district_2.id in fetched_districts_ids
    assert district_3.id in fetched_districts_ids
    assert district_1.id not in fetched_districts_ids


def test_get_tests_by_district_filter(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district_1 = District(name=random_lower_string(), is_active=True, state_id=state.id)
    db.add(district_1)
    db.commit()
    db.refresh(district_1)

    district_2 = District(name=random_lower_string(), is_active=True, state_id=state.id)
    db.add(district_2)
    db.commit()
    db.refresh(district_2)

    response_1 = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "description": random_lower_string(),
            "link": random_lower_string(),
            "district_ids": [district_1.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_1.status_code == 200
    test_data_1 = response_1.json()

    response_2 = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "description": random_lower_string(),
            "link": random_lower_string(),
            "district_ids": [district_1.id, district_2.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_2.status_code == 200
    test_data_2 = response_2.json()

    response_3 = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "description": random_lower_string(),
            "link": random_lower_string(),
            "district_ids": [district_2.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_3.status_code == 200
    test_data_3 = response_3.json()

    response = client.get(
        f"{settings.API_V1_STR}/test/?district_ids={district_1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert any(test_data_1["id"] == item["id"] for item in data["items"])
    assert any(test_data_2["id"] == item["id"] for item in data["items"])

    response = client.get(
        f"{settings.API_V1_STR}/test/?district_ids={district_2.id}&&district_ids={district_1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert any(test_data_1["id"] == item["id"] for item in data["items"])
    assert any(test_data_2["id"] == item["id"] for item in data["items"])
    assert any(test_data_3["id"] == item["id"] for item in data["items"])

    response = client.get(
        f"{settings.API_V1_STR}/test/?district_ids=-1",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0


def test_delete_test_with_attempted_candidate_should_fail(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)

    question = Question(organization_id=org_id)
    db.add(question)
    db.commit()
    db.refresh(question)

    revision = QuestionRevision(
        created_by_id=user.id,
        question_id=question.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "3"},
            {"id": 2, "key": "B", "value": "4"},
            {"id": 3, "key": "C", "value": "5"},
        ],
        correct_answer=[2],
        is_mandatory=True,
        is_active=True,
        is_deleted=False,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 100,
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [revision.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    test_id = response.json()["id"]
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        test_id=test_id,
        candidate_id=candidate.id,
        device="Laptop",
        consent=True,
        start_time="2025-01-01T10:00:00Z",
        is_submitted=True,
    )
    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response=[2],
            visited=True,
            time_spent=15,
        )
    )
    db.commit()

    response = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 422
    assert "Cannot delete" in response.json()["detail"]
    test_payload1 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 100,
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [revision.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload1,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    test_id2 = response.json()["id"]
    response = client.delete(
        f"{settings.API_V1_STR}/test/{test_id2}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200


def test_bulk_delete_test_with_attempted_candidate_should_fail(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id, is_active=True)
    db.add(district)
    db.commit()
    db.refresh(district)
    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        organization_id=org_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)

    question = Question(organization_id=org_id)
    db.add(question)
    db.commit()
    db.refresh(question)

    revision = QuestionRevision(
        created_by_id=user.id,
        question_id=question.id,
        question_text=random_lower_string(),
        question_type=QuestionType.single_choice,
        options=[
            {"id": 1, "key": "A", "value": "3"},
            {"id": 2, "key": "B", "value": "4"},
            {"id": 3, "key": "C", "value": "5"},
        ],
        correct_answer=[2],
        is_mandatory=True,
        is_active=True,
        is_deleted=False,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [revision.id],
        "tag_ids": [tag.id],
        "state_ids": [state.id],
        "district_ids": [district.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    test_id = response.json()["id"]
    candidate = Candidate(identity=uuid.uuid4())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        test_id=test_id,
        candidate_id=candidate.id,
        device="device 1",
        consent=True,
        start_time="2025-01-01T10:00:00Z",
        is_submitted=True,
    )

    db.add(candidate_test)
    db.commit()
    db.refresh(candidate_test)

    db.add(
        CandidateTestAnswer(
            candidate_test_id=candidate_test.id,
            question_revision_id=revision.id,
            response=[2],
            visited=True,
            time_spent=15,
        )
    )
    db.commit()

    test_payload1 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [revision.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload1,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    test_id2 = response.json()["id"]
    response = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/test/",
        json=[test_id, test_id2],
        headers=get_user_superadmin_token,
    )

    data = response.json()
    assert data["delete_success_count"] == 1
    assert len(data["delete_failure_list"]) == 1

    assert response.status_code == 200


def test_delete_test_with_no_attempted_candidates_should_pass(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    db.refresh(user)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id, is_active=True)
    db.add(district)
    db.commit()
    db.refresh(district)
    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        organization_id=org_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    question = Question(organization_id=org_id)
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
        ],
        correct_answer=[1],
        is_mandatory=True,
        is_active=True,
        is_deleted=False,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 45,
        "marks": 50,
        "start_instructions": random_lower_string(),
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [revision.id],
        "tag_ids": [tag.id],
        "state_ids": [state.id],
        "district_ids": [district.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    test_id = response.json()["id"]
    test_question_link = db.exec(
        select(TestQuestion).where(
            TestQuestion.test_id == test_id,
            TestQuestion.question_revision_id == revision.id,
        )
    ).first()
    assert test_question_link is not None
    test_tag_links = db.exec(
        select(TestTag).where(TestTag.test_id == test_id, TestTag.tag_id == tag.id)
    ).all()
    assert len(test_tag_links) == 1

    test_state_links = db.exec(
        select(TestState).where(
            TestState.test_id == test_id, TestState.state_id == state.id
        )
    ).all()
    assert len(test_state_links) == 1
    test_district_links = db.exec(
        select(TestDistrict).where(
            TestDistrict.test_id == test_id, TestDistrict.district_id == district.id
        )
    ).all()
    assert len(test_district_links) == 1

    response = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Test deleted successfully"
    test_question_links = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == test_id)
    ).all()
    assert len(test_question_links) == 0

    test_tag_links = db.exec(select(TestTag).where(TestTag.test_id == test_id)).all()
    assert len(test_tag_links) == 0

    test_state_links = db.exec(
        select(TestState).where(TestState.test_id == test_id)
    ).all()
    assert len(test_state_links) == 0
    test_district_links = db.exec(
        select(TestDistrict).where(TestDistrict.test_id == test_id)
    ).all()
    assert len(test_district_links) == 0


def test_get_list_of_entities_test_public(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user_organization = user_data["organization_id"]

    entity_type = EntityType(
        name=random_lower_string(),
        created_by_id=user_id,
        organization_id=user_organization,
    )

    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    entity_A = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
    )
    entity_B = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
    )
    entity_C = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
    )
    entity_D = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
    )
    db.add_all([entity_A, entity_B, entity_C, entity_D])
    db.commit()

    db.refresh(entity_A)
    db.refresh(entity_B)
    db.refresh(entity_C)
    db.refresh(entity_D)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=45,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user_id,
        candidate_profile=True,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    test_district = TestDistrict(test_id=test.id, district_id=district.id)
    db.add(test_district)
    db.commit()
    db.refresh(test_district)

    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    profile_list = data["profile_list"]
    returned_ids = {entity["id"] for entity in profile_list}

    expected_ids = {entity_A.id, entity_B.id, entity_C.id, entity_D.id}
    assert expected_ids.issubset(returned_ids)


def test_get_public_test_empty_profile_list(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user_organization = user_data["organization_id"]

    entity_type = EntityType(
        name=random_lower_string(),
        created_by_id=user_id,
        organization_id=user_organization,
    )

    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    entity_A = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
    )
    entity_B = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
    )

    db.add_all([entity_A, entity_B])
    db.commit()

    db.refresh(entity_A)
    db.refresh(entity_B)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=45,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user_id,
        candidate_profile=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    test_district = TestDistrict(test_id=test.id, district_id=district.id)
    db.add(test_district)
    db.commit()
    db.refresh(test_district)

    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    profile_list = data["profile_list"]
    assert profile_list == []


def test_get_public_test_location_details(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    user_organization = user_data["organization_id"]

    entity_type = EntityType(
        name=random_lower_string(),
        created_by_id=user_id,
        organization_id=user_organization,
    )

    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    block = Block(name=random_lower_string(), district_id=district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    entity_A = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        state_id=state.id,
        district_id=district.id,
    )
    entity_B = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        district_id=district.id,
        block_id=block.id,
    )

    entity_C = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        state_id=state.id,
        district_id=district.id,
        block_id=block.id,
    )

    db.add_all([entity_A, entity_B, entity_C])
    db.commit()

    db.refresh(entity_A)
    db.refresh(entity_B)
    db.refresh(entity_C)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=45,
        marks=100,
        start_instructions="Test instructions",
        link=random_lower_string(),
        created_by_id=user_id,
        candidate_profile=True,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    test_district = TestDistrict(test_id=test.id, district_id=district.id)
    db.add(test_district)
    db.commit()
    db.refresh(test_district)

    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test.link}")
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    profile_list = data["profile_list"]
    returned_ids = {entity["id"] for entity in profile_list}

    expected_ids = {
        entity_A.id,
        entity_B.id,
        entity_C.id,
    }
    assert expected_ids.issubset(returned_ids)
    # Check that entities have the correct state and district names

    for entity in data["profile_list"]:
        if entity["name"] == entity_A.name:
            assert entity["state"]["name"] == state.name
            assert entity["state"]["id"] == state.id
            assert entity["district"]["name"] == district.name
            assert entity["district"]["id"] == district.id

        if entity["name"] == entity_B.name:
            assert entity["district"]["name"] == district.name
            assert entity["district"]["id"] == district.id
            assert entity["block"]["name"] == block.name
            assert entity["block"]["id"] == block.id

        if entity["name"] == entity_C.name:
            assert entity["state"]["name"] == state.name
            assert entity["state"]["id"] == state.id
            assert entity["district"]["name"] == district.name
            assert entity["district"]["id"] == district.id
            assert entity["block"]["name"] == block.name
            assert entity["block"]["id"] == block.id
