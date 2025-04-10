from typing import Any

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
)
from app.models.question import QuestionType
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string


def setup_data(db: SessionDep) -> Any:
    user = create_random_user(db)

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
        created_by_id=user.id,
    )
    db.add(tag_type)
    db.commit()

    tag_a = Tag(
        name=random_lower_string(),
        created_by_id=user.id,
        tag_type_id=tag_type.id,
        organization_id=organization.id,
    )

    tag_b = Tag(
        name=random_lower_string(),
        created_by_id=user.id,
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
    db.flush()

    # Create question revisions
    question_revision_one = QuestionRevision(
        question_id=question_one.id,
        created_by_id=user.id,
        question_text="What is the size of Sun",
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )

    question_revision_two = QuestionRevision(
        question_id=question_two.id,
        created_by_id=user.id,
        question_text="What is the speed of light",
        question_type=QuestionType.single_choice,
        options=[{"text": "Option 1"}, {"text": "Option 2"}],
        correct_answer=[0],
    )

    db.add(question_revision_one)
    db.add(question_revision_two)
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
    ) = setup_data(db)

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
        "no_of_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "created_by_id": user.id,
        "tags": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question_revision_one.id, question_revision_two.id],
        "states": [punjab.id],
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
    assert data["no_of_questions"] == payload["no_of_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["created_by_id"] == user.id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert len(data["tags"]) == 2
    assert data["tags"][0] == tag_hindi.id
    assert data["tags"][1] == tag_marathi.id
    assert data["states"][0] == punjab.id

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
        no_of_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=user.id,
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
        "no_of_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "template_id": sample_test.id,
        "created_by_id": user.id,
        "tags": [tag_hindi.id, tag_marathi.id],
        "question_revision_ids": [question_revision_one.id, question_revision_two.id],
        "states": [punjab.id, goa.id],
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
    assert data["no_of_questions"] == payload["no_of_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == payload["template_id"]
    assert data["created_by_id"] == payload["created_by_id"]
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "states" in data
    assert len(data["tags"]) == 2
    assert len(data["states"]) == 2
    assert data["tags"][0] == tag_hindi.id
    assert data["tags"][1] == tag_marathi.id
    assert data["states"][1] == goa.id

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
        "no_of_questions": 4,
        "question_pagination": 1,
        "is_template": False,
        "template_id": sample_test.id,
        "created_by_id": user.id,
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
    assert data["no_of_questions"] == payload["no_of_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == sample_test.id
    assert data["created_by_id"] == user.id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "question_revision_ids" in data
    assert len(data["tags"]) == 0
    assert len(data["question_revision_ids"]) == 0
    assert len(data["states"]) == 0

    test_tag_link = db.exec(select(TestTag).where(TestTag.test_id == data["id"])).all()

    assert test_tag_link == []

    test_question_link = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == data["id"])
    ).all()

    assert test_question_link == []


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
    ) = setup_data(db)

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
    assert any(item["no_of_questions"] == test.no_of_questions for item in data)
    assert any(item["question_pagination"] == test.question_pagination for item in data)
    assert any(item["is_template"] == test.is_template for item in data)
    assert any(item["created_by_id"] == test.created_by_id for item in data)

    assert any(len(item["tags"]) == 1 and item["tags"][0] == tag_a.id for item in data)
    assert any(
        len(item["states"]) == 1 and item["states"][0] == state_a.id for item in data
    )


def test_get_test_by_id(
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
    ) = setup_data(db)

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
        no_of_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    test_tag_link = TestTag(test_id=test.id, tag_id=tag_a.id)
    db.add(test_tag_link)
    db.commit()

    test_question_link = TestQuestion(
        test_id=test.id, question_revision_id=question_revision_one.id
    )
    db.add(test_question_link)
    db.commit()

    test_state_link = TestState(test_id=test.id, state_id=state_a.id)
    db.add(test_state_link)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == test.name
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["marks"] == test.marks
    assert data["completion_message"] == test.completion_message
    assert data["start_instructions"] == test.start_instructions
    assert data["marks_level"] is None
    assert data["link"] == test.link
    assert data["no_of_attempts"] == test.no_of_attempts
    assert data["shuffle"] == test.shuffle
    assert data["random_questions"] == test.random_questions
    assert data["no_of_questions"] == test.no_of_questions
    assert data["question_pagination"] == test.question_pagination
    assert data["is_template"] == test.is_template
    assert data["created_by_id"] == test.created_by_id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "states" in data
    assert len(data["tags"]) == 1
    assert len(data["states"]) == 1
    assert data["tags"][0] == tag_a.id
    assert data["states"][0] == state_a.id


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
    ) = setup_data(db)

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
        no_of_questions=1,
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
        "no_of_questions": 50,
        "question_pagination": 1,
        "is_template": False,
        "template_id": None,
        "created_by_id": user.id,
        "tags": [tag_a.id, tag_b.id],
        "question_revision_ids": [question_revision_one.id],
        "states": [stata_a.id, state_b.id],
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
    assert data["no_of_questions"] == payload["no_of_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == payload["template_id"]
    assert data["created_by_id"] == payload["created_by_id"]
    assert "id" in data
    assert "created_date" in data
    from datetime import datetime

    created_date = datetime.fromisoformat(data["created_date"])
    assert created_date == created_date_original
    modified_date = datetime.fromisoformat(data["modified_date"])
    assert modified_date != modified_date_original
    assert "modified_date" in data

    assert "tags" in data
    assert len(data["tags"]) == 2
    assert data["tags"] == [tag_a.id, tag_b.id]

    assert "question_revision_ids" in data
    assert len(data["question_revision_ids"]) == 1
    assert data["question_revision_ids"][0] == question_revision_one.id

    assert "states" in data
    assert len(data["states"]) == 2
    assert data["states"] == [stata_a.id, state_b.id]
    assert state_c.id not in data["states"]

    # Check test_question_link has the correct question_revision_id
    updated_test_questions = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == test.id)
    ).all()
    assert len(updated_test_questions) == 1
    assert updated_test_questions[0].question_revision_id == question_revision_one.id


def test_visibility_test(
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
    ) = setup_data(db)

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
        no_of_questions=1,
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
    ) = setup_data(db)

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
        no_of_questions=1,
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
