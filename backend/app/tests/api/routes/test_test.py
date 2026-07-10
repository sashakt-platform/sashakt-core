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
    Form,
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
from app.models.certificate import Certificate
from app.models.location import District
from app.models.question import QuestionType
from app.models.role import Role
from app.models.test import OMRMode, QuestionSet, TestDistrict
from app.models.user import UserState
from app.tests.utils.location import create_random_state
from app.tests.utils.organization import (
    create_random_organization,
)
from app.tests.utils.organization_settings import make_current_user_org_flexible
from app.tests.utils.question_revisions import create_random_question_revision
from app.tests.utils.tag import create_random_tag
from app.tests.utils.test import get_test_link
from app.tests.utils.user import (
    authentication_token_from_email,
    create_random_user,
    get_current_user_data,
)
from app.tests.utils.utils import (
    assert_paginated_response,
    random_email,
    random_lower_string,
)


def setup_data(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> Any:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
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
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["created_by_id"] == user_id
    assert data["locale"] == "en-US"
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
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "no_of_random_questions": 4,
        "question_pagination": 1,
        "locale": "hi-IN",
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
    assert data["no_of_attempts"] == payload["no_of_attempts"]
    assert data["shuffle"] == payload["shuffle"]
    assert data["random_questions"] == payload["random_questions"]
    assert data["no_of_random_questions"] == payload["no_of_random_questions"]
    assert data["question_pagination"] == payload["question_pagination"]
    assert data["is_template"] == payload["is_template"]
    assert data["template_id"] == payload["template_id"]
    assert data["locale"] == payload["locale"]
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


def test_create_sectioned_test(
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
        "time_limit": 15,
        "marks": 10,
        "link": random_lower_string(),
        "no_of_attempts": 1,
        "shuffle": False,
        "random_questions": False,
        "question_pagination": 1,
        "is_template": False,
        "tag_ids": [tag_hindi.id],
        "state_ids": [punjab.id],
        "district_ids": [],
        "question_sets": [
            {
                "title": "Physics",
                "description": "Section A",
                "display_order": 1,
                "max_questions_allowed_to_attempt": 1,
                "marking_scheme": {"correct": 4, "wrong": -1, "skipped": 0},
                "question_revision_ids": [question_revision_one.id],
            },
            {
                "title": "Chemistry",
                "description": "Section B",
                "display_order": 2,
                "max_questions_allowed_to_attempt": 1,
                "marking_scheme": {"correct": 3, "wrong": -1, "skipped": 0},
                "question_revision_ids": [question_revision_two.id],
            },
        ],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question_sets"] is not None
    assert len(data["question_sets"]) == 2
    assert [question_set["title"] for question_set in data["question_sets"]] == [
        "Physics",
        "Chemistry",
    ]
    assert [
        question_set["display_order"] for question_set in data["question_sets"]
    ] == [
        1,
        2,
    ]
    assert (
        data["question_sets"][0]["question_revisions"][0]["id"]
        == question_revision_one.id
    )
    assert (
        data["question_sets"][1]["question_revisions"][0]["id"]
        == question_revision_two.id
    )
    assert [question["id"] for question in data["question_revisions"]] == [
        question_revision_one.id,
        question_revision_two.id,
    ]

    question_sets = db.exec(
        select(QuestionSet).where(QuestionSet.test_id == data["id"])
    ).all()
    assert len(question_sets) == 2

    test_questions = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == data["id"])
    ).all()
    assert len(test_questions) == 2
    assert all(
        test_question.question_set_id is not None for test_question in test_questions
    )
    assert {test_question.question_set_id for test_question in test_questions} == {
        question_set.id for question_set in question_sets
    }


def test_create_sectioned_test_rejects_empty_question_set(
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
        "link": random_lower_string(),
        "question_sets": [
            {
                "title": "Physics",
                "description": "Section A",
                "display_order": 1,
                "max_questions_allowed_to_attempt": 1,
                "question_revision_ids": [],
            }
        ],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Each question set must include at least one question revision."
    )


def test_create_sectioned_test_rejects_duplicate_questions_across_sets(
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
        "link": random_lower_string(),
        "question_sets": [
            {
                "title": "Physics",
                "description": "Section A",
                "display_order": 1,
                "max_questions_allowed_to_attempt": 1,
                "question_revision_ids": [question_revision_one.id],
            },
            {
                "title": "Chemistry",
                "description": "Section B",
                "display_order": 2,
                "max_questions_allowed_to_attempt": 1,
                "question_revision_ids": [question_revision_one.id],
            },
        ],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question revisions cannot be duplicated across question sets."
    )


def test_create_sectioned_test_rejects_random_tag_count(
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
        "link": random_lower_string(),
        "question_sets": [
            {
                "title": "Physics",
                "description": "Section A",
                "display_order": 1,
                "max_questions_allowed_to_attempt": 1,
                "question_revision_ids": [question_revision_one.id],
            }
        ],
        "random_tag_count": [{"tag_id": tag_hindi.id, "count": 1}],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question-set tests do not support tag-based random question selection in this pass."
    )


def test_create_sectioned_test_rejects_random_questions(
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

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "random_questions": True,
            "no_of_random_questions": 1,
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [question_revision_one.id],
                },
                {
                    "title": "Chemistry",
                    "description": "Section B",
                    "display_order": 2,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [question_revision_two.id],
                },
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question-set tests do not support random question selection in this pass."
    )


def test_create_sectioned_test_rejects_duplicate_questions_within_set(
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

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [
                        question_revision_one.id,
                        question_revision_one.id,
                    ],
                }
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question revisions cannot be duplicated within a question set."
    )


def test_create_sectioned_test_rejects_duplicate_display_order(
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

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [question_revision_one.id],
                },
                {
                    "title": "Chemistry",
                    "description": "Section B",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [question_revision_two.id],
                },
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question set display_order values must be unique within a test."
    )


def test_create_sectioned_test_rejects_attempt_limit_greater_than_section_size(
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

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 2,
                    "question_revision_ids": [question_revision_one.id],
                }
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question set max_questions_allowed_to_attempt cannot exceed the number of questions in that set."
    )


def test_create_sectioned_test_rejects_mandatory_questions_exceeding_attempt_limit(
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

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [
                        question_revision_one.id,
                        question_revision_two.id,
                    ],
                }
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question set 'Physics' has 2 mandatory question(s), but only 1 question(s) can be attempted."
    )


def test_create_test_rejects_duplicate_question_revision_ids(
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

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "question_revision_ids": [
                question_revision_one.id,
                question_revision_one.id,
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question revisions cannot be duplicated within a test."
    )


def test_create_test_rejects_missing_question_revision_ids(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "link": random_lower_string(),
            "question_revision_ids": [999999],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "One or more question revisions were not found."


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
        organization_id=user.organization_id,
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
        len(item["tags"]) == 1
        and item["tags"][0]["id"] == tag_a.id
        and item["tags"][0].get("tag_type", {}).get("name") == tag_type.name
        for item in data
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
        organization_id=user.organization_id,
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
        organization_id=org_id,
    )

    test_2 = Test(
        name=test_name_2,
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string() + test_name_1 + random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
        organization_id=org_id,
    )

    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string() + random_text_1 + random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string(),
        description=random_text_2,
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 27, 12, 30),
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 28, 15, 30),
        organization_id=org_id,
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 7, 28, 19, 30),
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 27, 12, 30),
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 28, 15, 30),
        organization_id=org_id,
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        end_time=datetime(2025, 7, 28, 19, 30),
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 26, 10, 30),
        end_time=datetime(2025, 4, 27, 12, 30),
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 28, 14, 30),
        end_time=datetime(2025, 4, 28, 15, 30),
        organization_id=org_id,
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_time=datetime(2025, 4, 28, 19, 10),
        end_time=datetime(2025, 4, 28, 19, 30),
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        time_limit=40,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        time_limit=45,
        organization_id=org_id,
    )

    test_4 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
        organization_id=org_id,
    )

    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        completion_message=random_lower_string()
        + random_text_1
        + random_lower_string(),
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        completion_message=random_text_2,
        organization_id=org_id,
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
        organization_id=org_id,
    )

    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_instructions=random_lower_string()
        + random_text_1
        + random_lower_string(),
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        start_instructions=random_text_2,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        no_of_attempts=2,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        no_of_attempts=3,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=False,
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=True,
        organization_id=org_id,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        shuffle=False,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=False,
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=True,
        organization_id=org_id,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        random_questions=False,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=10,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=45,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=2,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=0,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        is_template=False,
        organization_id=org_id,
    )

    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        is_template=True,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user_1.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user_2.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
    """Test the generic sorting system with sort_by and sort_order parameters"""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)
    test_1 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    db.add_all([test_1, test_2, test_3])
    db.commit()

    test_names = sorted([test_1.name, test_2.name, test_3.name], key=str.lower)

    response = client.get(
        f"{settings.API_V1_STR}/test/?sort_by=name&sort_order=asc&created_by={user.id}",
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
        f"{settings.API_V1_STR}/test/?sort_by=name&sort_order=desc&created_by={user.id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    data = data["items"]
    assert_paginated_response(response, expected_total=3)
    assert data[0]["name"] == test_names[2]
    assert data[1]["name"] == test_names[1]
    assert data[2]["name"] == test_names[0]

    # Test default sorting, i.e modified_date DESC
    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    data = data["items"]

    test_modified_dates = [item["modified_date"] for item in data]

    sorted_test_modified_dates_desc = sorted(test_modified_dates, reverse=True)
    assert sorted_test_modified_dates_desc == test_modified_dates

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}&sort_by=created_date&sort_order=desc",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    data = data["items"]
    test_created_date = [item["created_date"] for item in data]

    sorted_test_created_date = sorted(test_created_date, reverse=True)
    assert sorted_test_created_date == test_created_date

    response = client.get(
        f"{settings.API_V1_STR}/test/?created_by={user.id}&sort_by=created_date&sort_order=asc",
        headers=get_user_superadmin_token,
    )

    data = response.json()
    data = data["items"]
    test_created_dates = [item["created_date"] for item in data]

    # should be sorted by created_date in ascending order
    sorted_by_created_date = sorted(test_created_dates)
    assert sorted_by_created_date == test_created_dates

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
        organization_id=org_id,
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
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)

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
        organization_id=user.organization_id,
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
        organization_id=user.organization_id,
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
    assert data["no_of_random_questions"] == test_2.no_of_random_questions
    assert data["created_by_id"] == test_2.created_by_id
    assert data["is_template"] == test_2.is_template
    assert data["is_active"] == test_2.is_active
    assert datetime.fromisoformat(data["created_date"]) == test_2.created_date
    assert datetime.fromisoformat(data["modified_date"]) == test_2.modified_date

    assert data["tags"] == []
    assert data["states"] == []
    assert data["question_revisions"] == []


def test_get_test_by_id_organization_restriction(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A user must not be able to fetch a test that belongs to a different organization,
    even if they know the test ID.
    """
    user_data = get_current_user_data(client, get_user_superadmin_token)
    own_org_id = user_data["organization_id"]

    # Test belonging to the requesting user's organization — should be accessible
    own_org_test = Test(
        name=random_lower_string(),
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=1,
        created_by_id=user_data["id"],
        organization_id=own_org_id,
    )
    db.add(own_org_test)

    # Test belonging to a completely different organization — should be blocked
    other_org = create_random_organization(db)
    other_user = create_random_user(db, organization_id=other_org.id)
    other_org_test = Test(
        name=random_lower_string(),
        link=random_lower_string(),
        no_of_random_questions=1,
        question_pagination=1,
        created_by_id=other_user.id,
        organization_id=other_org.id,
    )
    db.add(other_org_test)
    db.commit()

    # Can fetch a test from own organization
    own_response = client.get(
        f"{settings.API_V1_STR}/test/{own_org_test.id}",
        headers=get_user_superadmin_token,
    )
    assert own_response.status_code == 200
    assert own_response.json()["id"] == own_org_test.id

    # Cannot fetch a test from a different organization
    other_response = client.get(
        f"{settings.API_V1_STR}/test/{other_org_test.id}",
        headers=get_user_superadmin_token,
    )
    assert other_response.status_code == 403


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
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
        locale="hi-IN",
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
        "locale": "en-US",
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
    assert data["locale"] == payload["locale"]

    assert data["marks"] == payload["marks"]
    assert data["completion_message"] == payload["completion_message"]
    assert data["start_instructions"] == payload["start_instructions"]
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


def test_update_test_without_name_keeps_existing_name(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    original_name = random_lower_string()
    test = Test(
        name=original_name,
        description=random_lower_string(),
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"description": random_lower_string()},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == original_name

    db.refresh(test)
    assert test.name == original_name


def test_update_test_removes_description_when_explicitly_null(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"description": None},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["description"] is None

    db.refresh(test)
    assert test.description is None


def test_update_test_add_then_remove_tags(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    tag_a = create_random_tag(db)
    tag_b = create_random_tag(db)

    test = Test(name=random_lower_string(), created_by_id=user.id)
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"tag_ids": [tag_a.id, tag_b.id]},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert {tag["id"] for tag in data["tags"]} == {tag_a.id, tag_b.id}
    assert len(db.exec(select(TestTag).where(TestTag.test_id == test.id)).all()) == 2

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"tag_ids": []},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["tags"] == []
    assert db.exec(select(TestTag).where(TestTag.test_id == test.id)).all() == []


def test_update_test_add_then_remove_states(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    state_a = create_random_state(db)
    state_b = create_random_state(db)

    test = Test(name=random_lower_string(), created_by_id=user.id)
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"state_ids": [state_a.id, state_b.id]},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert {state["id"] for state in data["states"]} == {state_a.id, state_b.id}
    assert (
        len(db.exec(select(TestState).where(TestState.test_id == test.id)).all()) == 2
    )

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"state_ids": []},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["states"] == []
    assert db.exec(select(TestState).where(TestState.test_id == test.id)).all() == []


def test_update_test_add_then_remove_districts(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    state = create_random_state(db)
    district_a = District(name=random_lower_string(), state_id=state.id)
    district_b = District(name=random_lower_string(), state_id=state.id)
    db.add(district_a)
    db.add(district_b)
    db.commit()
    db.refresh(district_a)
    db.refresh(district_b)

    test = Test(name=random_lower_string(), created_by_id=user.id)
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"district_ids": [district_a.id, district_b.id]},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert {district["id"] for district in data["districts"]} == {
        district_a.id,
        district_b.id,
    }
    assert (
        len(db.exec(select(TestDistrict).where(TestDistrict.test_id == test.id)).all())
        == 2
    )

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"district_ids": []},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["districts"] == []
    assert (
        db.exec(select(TestDistrict).where(TestDistrict.test_id == test.id)).all() == []
    )


def test_update_test_adds_two_questions(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    question_revision_one = create_random_question_revision(db, user_id=user.id)
    question_revision_two = create_random_question_revision(db, user_id=user.id)

    test = Test(name=random_lower_string(), created_by_id=user.id)
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "question_revision_ids": [
                question_revision_one.id,
                question_revision_two.id,
            ]
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert {qr["id"] for qr in data["question_revisions"]} == {
        question_revision_one.id,
        question_revision_two.id,
    }

    test_questions = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == test.id)
    ).all()
    assert {tq.question_revision_id for tq in test_questions} == {
        question_revision_one.id,
        question_revision_two.id,
    }


def test_update_test_partial_put_keeps_state_tag_district(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """A PUT that omits state_ids/tag_ids/district_ids must not clear them."""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    state = create_random_state(db)
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)
    tag = create_random_tag(db)

    question_revision_one = create_random_question_revision(db, user_id=user.id)
    question_revision_two = create_random_question_revision(db, user_id=user.id)

    test = Test(name=random_lower_string(), created_by_id=user.id)
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "state_ids": [state.id],
            "tag_ids": [tag.id],
            "district_ids": [district.id],
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert {s["id"] for s in data["states"]} == {state.id}
    assert {t["id"] for t in data["tags"]} == {tag.id}
    assert {d["id"] for d in data["districts"]} == {district.id}

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "question_revision_ids": [
                question_revision_one.id,
                question_revision_two.id,
            ]
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert {s["id"] for s in data["states"]} == {state.id}
    assert {t["id"] for t in data["tags"]} == {tag.id}
    assert {d["id"] for d in data["districts"]} == {district.id}
    assert {qr["id"] for qr in data["question_revisions"]} == {
        question_revision_one.id,
        question_revision_two.id,
    }

    assert (
        len(db.exec(select(TestState).where(TestState.test_id == test.id)).all()) == 1
    )
    assert len(db.exec(select(TestTag).where(TestTag.test_id == test.id)).all()) == 1
    assert (
        len(db.exec(select(TestDistrict).where(TestDistrict.test_id == test.id)).all())
        == 1
    )

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={"name": random_lower_string(), "time_limit": 45},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["time_limit"] == 45
    assert {s["id"] for s in data["states"]} == {state.id}
    assert {t["id"] for t in data["tags"]} == {tag.id}
    assert {d["id"] for d in data["districts"]} == {district.id}
    assert {qr["id"] for qr in data["question_revisions"]} == {
        question_revision_one.id,
        question_revision_two.id,
    }

    assert (
        len(db.exec(select(TestState).where(TestState.test_id == test.id)).all()) == 1
    )
    assert len(db.exec(select(TestTag).where(TestTag.test_id == test.id)).all()) == 1
    assert (
        len(db.exec(select(TestDistrict).where(TestDistrict.test_id == test.id)).all())
        == 1
    )
    assert (
        len(db.exec(select(TestQuestion).where(TestQuestion.test_id == test.id)).all())
        == 2
    )


def test_update_test_adds_random_tag_count(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None

    tag_one = create_random_tag(db)
    tag_two = create_random_tag(db)

    test = Test(name=random_lower_string(), created_by_id=user.id)
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "random_tag_count": [
                {"tag_id": tag_one.id, "count": 3},
                {"tag_id": tag_two.id, "count": 2},
            ]
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["random_tag_counts"]) == 2
    assert data["random_tag_counts"][0]["tag"]["id"] == tag_one.id
    assert data["random_tag_counts"][0]["tag"]["name"] == tag_one.name
    assert data["random_tag_counts"][0]["count"] == 3
    assert data["random_tag_counts"][1]["tag"]["id"] == tag_two.id
    assert data["random_tag_counts"][1]["tag"]["name"] == tag_two.name
    assert data["random_tag_counts"][1]["count"] == 2

    db.refresh(test)
    assert test.random_tag_count == [
        {"tag_id": tag_one.id, "count": 3},
        {"tag_id": tag_two.id, "count": 2},
    ]


def test_update_test_full_settings_payload(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = db.get(User, user_data["id"])
    assert user is not None
    assert user.organization_id is not None

    form = Form(
        name=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user.organization_id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        pause_timer_when_inactive=False,
        show_marks=True,
        show_result=True,
        show_question_palette=False,
        bookmark=False,
        show_feedback_on_completion=False,
        show_feedback_immediately=False,
        omr=OMRMode.NEVER,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    payload = {
        "start_time": None,
        "end_time": None,
        "pause_timer_when_inactive": True,
        "time_limit": 12000000,
        "marks_level": "question",
        "marks": None,
        "marking_scheme": {"correct": 2, "wrong": 0, "skipped": 0},
        "completion_message": "<p>hello 2</p>",
        "start_instructions": "<p>heello </p>",
        "no_of_attempts": 1,
        "shuffle": True,
        "random_questions": False,
        "no_of_random_questions": None,
        "question_pagination": 1,
        "is_template": False,
        "template_id": None,
        "show_marks": False,
        "show_result": True,
        "show_question_palette": True,
        "bookmark": True,
        "locale": "en-US",
        "certificate_id": certificate.id,
        "show_feedback_on_completion": True,
        "show_feedback_immediately": True,
        "form_id": form.id,
        "omr": "OPTIONAL",
    }

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200

    for field, expected in payload.items():
        assert data[field] == expected, (
            f"{field}: expected {expected}, got {data[field]}"
        )

    db.refresh(test)
    assert test.pause_timer_when_inactive is True
    assert test.show_marks is False
    assert test.show_question_palette is True
    assert test.bookmark is True
    assert test.show_feedback_on_completion is True
    assert test.show_feedback_immediately is True
    assert test.omr == OMRMode.OPTIONAL
    assert test.form_id == form.id
    assert test.certificate_id == certificate.id


def test_update_test_blocks_membership_changes_after_candidate_test_exists(
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
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision_one.id))
    db.commit()

    candidate = Candidate()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        device="test-device",
        consent=True,
        start_time=get_current_time(),
        question_revision_ids=[question_revision_one.id],
        question_set_ids=[None],
    )
    db.add(candidate_test)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": test.name,
            "is_template": False,
            "question_revision_ids": [question_revision_two.id],
            "locale": "en-US",
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "This test cannot be updated because candidates have already attempted it."
    )


def test_update_test_blocks_pause_timer_changes_after_candidate_test_exists(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user = create_random_user(db)
    test_link = random_lower_string()
    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        link=test_link,
        pause_timer_when_inactive=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    candidate = Candidate()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    assert candidate.id is not None

    candidate_test = CandidateTest(
        admin_id=user.id,
        test_id=test.id,
        candidate_id=candidate.id,
        device="test-device",
        consent=True,
        start_time=get_current_time(),
    )
    db.add(candidate_test)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": test.name,
            "link": test_link,
            "is_template": False,
            "pause_timer_when_inactive": True,
            "locale": "en-US",
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Cannot update pause timer setting after candidate tests have been created."
    )


def test_update_test_can_replace_flat_membership_with_question_sets(
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
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision_one.id))
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": test.name,
            "is_template": False,
            "locale": "en-US",
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [question_revision_one.id],
                },
                {
                    "title": "Chemistry",
                    "description": "Section B",
                    "display_order": 2,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [question_revision_two.id],
                },
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question_sets"] is not None
    assert [question_set["title"] for question_set in data["question_sets"]] == [
        "Physics",
        "Chemistry",
    ]
    assert [question["id"] for question in data["question_revisions"]] == [
        question_revision_one.id,
        question_revision_two.id,
    ]

    test_questions = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == test.id)
    ).all()
    assert len(test_questions) == 2
    assert all(
        test_question.question_set_id is not None for test_question in test_questions
    )

    question_sets = db.exec(
        select(QuestionSet).where(QuestionSet.test_id == test.id)
    ).all()
    assert len(question_sets) == 2


def test_update_test_rejects_mandatory_questions_exceeding_attempt_limit(
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
        created_by_id=user.id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": test.name,
            "is_template": False,
            "locale": "en-US",
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 1,
                    "question_revision_ids": [
                        question_revision_one.id,
                        question_revision_two.id,
                    ],
                }
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question set 'Physics' has 2 mandatory question(s), but only 1 question(s) can be attempted."
    )


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
        f"{settings.API_V1_STR}/test/{test.id}/visibility",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["is_active"] is True

    response = client.patch(
        f"{settings.API_V1_STR}/test/{test.id}/visibility",
        params={"is_active": False},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["is_active"] is False


def test_visibility_test_with_random_tag_count(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    organization_id = get_current_user_data(client, get_user_superadmin_token)[
        "organization_id"
    ]
    user = create_random_user(db, organization_id=organization_id)
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
        organization_id=organization_id,
        random_tag_count=[
            {"tag_id": tag1.id, "count": 3},
            {"tag_id": tag2.id, "count": 2},
        ],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    response = client.patch(
        f"{settings.API_V1_STR}/test/{test.id}/visibility",
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


def test_visibility_test_not_available(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    non_existent_test_id = -9999

    response = client.patch(
        f"{settings.API_V1_STR}/test/{non_existent_test_id}/visibility",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Test is not available"


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
    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
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

    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
    data = response.json()

    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == test.name
    assert data["description"] == test.description
    assert data["time_limit"] == test.time_limit
    assert data["start_instructions"] == test.start_instructions
    assert data["total_questions"] == 7


def test_get_public_test_info_includes_question_set_summaries(
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
        is_active=True,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    physics = QuestionSet(
        test_id=test.id,
        title="Physics",
        description="Section A",
        display_order=1,
        max_questions_allowed_to_attempt=1,
        marking_scheme={"correct": 4, "wrong": -1, "skipped": 0},
    )
    chemistry = QuestionSet(
        test_id=test.id,
        title="Chemistry",
        description="Section B",
        display_order=2,
        max_questions_allowed_to_attempt=1,
        marking_scheme={"correct": 3, "wrong": -1, "skipped": 0},
    )
    db.add(physics)
    db.add(chemistry)
    db.commit()
    db.refresh(physics)
    db.refresh(chemistry)

    db.add(
        TestQuestion(
            test_id=test.id,
            question_revision_id=question_revision_one.id,
            question_set_id=physics.id,
        )
    )
    db.add(
        TestQuestion(
            test_id=test.id,
            question_revision_id=question_revision_two.id,
            question_set_id=chemistry.id,
        )
    )
    db.commit()

    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
    data = response.json()

    assert response.status_code == 200
    assert data["total_questions"] == 2
    assert data["question_sets"] is not None
    assert [question_set["title"] for question_set in data["question_sets"]] == [
        "Physics",
        "Chemistry",
    ]
    assert [
        question_set["question_count"] for question_set in data["question_sets"]
    ] == [
        1,
        1,
    ]


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

    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
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
        random_tag_count=[{"tag_id": 1, "count": 4}, {"tag_id": 2, "count": 3}],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    test_link = get_test_link(db, test.id, test.created_by_id)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
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
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()

    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
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
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    test_link = get_test_link(db, test.id, user.id)
    uuid = test_link.uuid
    db.delete(test)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/test/public/{uuid}")
    assert response.status_code == 404


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
            start_time=future_start_time,
            created_by_id=create_random_user(db).id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        test_link = get_test_link(db, test.id, test.created_by_id)
        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/{test_link.uuid}"
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
            is_active=True,
            start_time=datetime(2024, 5, 24, 9, 0, 0),
            end_time=fake_current_time + timedelta(days=1),
            created_by_id=create_random_user(db).id,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        test_link = get_test_link(db, test.id, test.created_by_id)
        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/{test_link.uuid}"
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
            start_time=fake_current_time + timedelta(minutes=10),
            end_time=fake_current_time + timedelta(hours=2),
            time_limit=60,
            is_active=True,
            created_by_id=user.id,
        )
        db.add(deleted_test)
        db.commit()
        test_link = get_test_link(db, deleted_test.id, deleted_test.created_by_id)
        test_uuid = test_link.uuid

        db.delete(deleted_test)
        db.commit()

        response = client.get(
            f"{settings.API_V1_STR}/test/public/time_left/{test_uuid}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Test not found or not active"


def test_public_timer_returns_zero_if_start_time_none(
    client: TestClient, db: SessionDep
) -> None:
    test = Test(
        name="Test with no start time",
        is_active=True,
        start_time=None,  # This is the key for this test
        created_by_id=create_random_user(db).id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(
        f"{settings.API_V1_STR}/test/public/time_left/{test_link.uuid}"
    )
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


def test_clone_sectioned_test_preserves_question_sets(
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
    creator = create_random_user(db)

    original_test = Test(
        name="Original Sectioned Test",
        description=random_lower_string(),
        link=random_lower_string(),
        created_by_id=creator.id,
        is_active=True,
    )
    db.add(original_test)
    db.commit()
    db.refresh(original_test)

    physics = QuestionSet(
        test_id=original_test.id,
        title="Physics",
        description="Section A",
        display_order=1,
        max_questions_allowed_to_attempt=1,
        marking_scheme={"correct": 4, "wrong": -1, "skipped": 0},
    )
    chemistry = QuestionSet(
        test_id=original_test.id,
        title="Chemistry",
        description="Section B",
        display_order=2,
        max_questions_allowed_to_attempt=1,
        marking_scheme={"correct": 3, "wrong": -1, "skipped": 0},
    )
    db.add(physics)
    db.add(chemistry)
    db.commit()
    db.refresh(physics)
    db.refresh(chemistry)

    db.add(
        TestQuestion(
            test_id=original_test.id,
            question_revision_id=question_revision_one.id,
            question_set_id=physics.id,
        )
    )
    db.add(
        TestQuestion(
            test_id=original_test.id,
            question_revision_id=question_revision_two.id,
            question_set_id=chemistry.id,
        )
    )
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/test/{original_test.id}/clone",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] != original_test.id
    assert data["question_sets"] is not None
    assert [question_set["title"] for question_set in data["question_sets"]] == [
        "Physics",
        "Chemistry",
    ]
    assert (
        data["question_sets"][0]["question_revisions"][0]["id"]
        == question_revision_one.id
    )
    assert (
        data["question_sets"][1]["question_revisions"][0]["id"]
        == question_revision_two.id
    )

    cloned_question_sets = db.exec(
        select(QuestionSet).where(QuestionSet.test_id == data["id"])
    ).all()
    assert len(cloned_question_sets) == 2
    assert {question_set.title for question_set in cloned_question_sets} == {
        "Physics",
        "Chemistry",
    }

    cloned_test_questions = db.exec(
        select(TestQuestion).where(TestQuestion.test_id == data["id"])
    ).all()
    assert len(cloned_test_questions) == 2
    assert all(
        test_question.question_set_id is not None
        for test_question in cloned_test_questions
    )
    assert {
        test_question.question_set_id for test_question in cloned_test_questions
    } == {question_set.id for question_set in cloned_question_sets}


def test_bulk_delete_state_admin_cannot_delete_general_tests(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org_id,
        "state_ids": [state.id],
    }
    resp = client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    # Create 2 general tests (no states)
    test_payload_1 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [],
    }
    test_payload_2 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [],
    }

    create_response_one = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload_1,
        headers=get_user_superadmin_token,
    )
    assert create_response_one.status_code == 200
    created_test_id_one = create_response_one.json()["id"]

    create_response_two = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload_2,
        headers=get_user_superadmin_token,
    )
    assert create_response_two.status_code == 200
    created_test_id_two = create_response_two.json()["id"]

    delete_resp = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/test/",
        json=[created_test_id_one, created_test_id_two],
        headers=token_headers,
    )
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["delete_success_count"] == 0
    assert len(data["delete_failure_list"]) == 2


def test_bulk_delete_state_admin_cannot_delete_tests_outside_location(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_y = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_x, state_y])
    db.commit()
    db.refresh(state_x)
    db.refresh(state_y)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org_id,
        "state_ids": [state_y.id],
    }
    resp = client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    # Create 2 tests in state_x
    test_payload_1 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state_x.id],
    }
    test_payload_2 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state_x.id],
    }

    create_response_one = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload_1,
        headers=get_user_superadmin_token,
    )
    assert create_response_one.status_code == 200
    created_test_id_one = create_response_one.json()["id"]

    create_response_two = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload_2,
        headers=get_user_superadmin_token,
    )
    assert create_response_two.status_code == 200
    created_test_id_two = create_response_two.json()["id"]

    delete_resp = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/test/",
        json=[created_test_id_one, created_test_id_two],
        headers=token_headers,
    )
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["delete_success_count"] == 0
    assert len(data["delete_failure_list"]) == 2


def test_bulk_delete_state_admin_delete_tests_same_location(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org_id,
        "state_ids": [state.id],
    }
    resp = client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    # Create 2 tests in same state
    test_payload_1 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state.id],
    }
    test_payload_2 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state.id],
    }

    create_response_one = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload_1,
        headers=get_user_superadmin_token,
    )
    assert create_response_one.status_code == 200
    created_test_id_one = create_response_one.json()["id"]

    create_response_two = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload_2,
        headers=get_user_superadmin_token,
    )
    assert create_response_two.status_code == 200
    created_test_id_two = create_response_two.json()["id"]

    state_admin_user = get_current_user_data(client, token_headers)
    for test_id in (created_test_id_one, created_test_id_two):
        test_obj = db.get(Test, test_id)
        assert test_obj is not None
        test_obj.created_by_id = state_admin_user["id"]
        db.add(test_obj)
    db.commit()

    delete_resp = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/test/",
        json=[created_test_id_one, created_test_id_two],
        headers=token_headers,
    )
    data = delete_resp.json()
    assert delete_resp.status_code == 200
    data = delete_resp.json()
    assert data["delete_success_count"] == 2
    assert data["delete_failure_list"] is None


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
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    db.delete(test)
    db.commit()
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
        organization_id=org_id,
    )

    test_2 = Test(
        name="PyThon advanced test",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )

    test_3 = Test(
        name=" beginner test PYTHON",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_5 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    db.add_all([test_1, test_2, test_3, test_4, test_5])
    db.commit()
    db.refresh(test_1)
    db.refresh(test_2)
    db.refresh(test_3)
    db.refresh(test_4)
    db.refresh(test_5)

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
    assert_paginated_response(response, expected_total=2)

    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_ids={tag_1.id}&tag_ids={tag_2.id}",
        headers=get_user_superadmin_token,
    )

    assert_paginated_response(response, expected_total=4)

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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_4 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_5 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_6 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
    assert data["total"] == 5
    assert test_6.id not in (test["id"] for test in data["items"])
    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type3.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []

    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type2.id}&tag_ids={tag_3.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2

    response = client.get(
        f"{settings.API_V1_STR}/test/?tag_type_ids={tag_type2.id}&tag_ids={tag_1.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0


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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
    assert data["total"] == 3
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
        organization_id=org_id,
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
        organization_id=org_id,
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
        organization_id=org_id,
    )
    test_2 = Test(
        name=random_lower_string(),
        description="someText" + keyword.upper() + "moreText",  # upper case
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    test_3 = Test(
        name=random_lower_string(),
        description="completely different",
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
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
        created_by_id=user_id,
        organization_id=user_data["organization_id"],
    )
    db.add(active_test)
    inactive_test = Test(
        name="Inactive Test",
        is_active=False,
        created_by_id=user_id,
        organization_id=user_data["organization_id"],
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
    user_data = get_current_user_data(client, get_user_superadmin_token)
    test = Test(
        name=random_lower_string(),
        created_by_id=user_data["id"],
        start_time="2025-07-19T10:00:00Z",
        end_time="2025-07-19T10:30:00Z",
        time_limit=30,
        locale="en-US",
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 60,
        "locale": "en-US",
    }
    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    data = response.json()
    assert "Time limit cannot be more than the duration" in data["detail"]


def test_update_test_not_available(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    non_existent_test_id = -9999

    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 5,
        "locale": "en-US",
    }

    response = client.put(
        f"{settings.API_V1_STR}/test/{non_existent_test_id}",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Test is not available"


def test_update_test_not_created_by_user(
    client: TestClient,
    db: SessionDep,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role
    org = get_current_user_data(client, get_user_systemadmin_token)["organization_id"]

    email_a = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_a,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": org,
        },
        headers=get_user_systemadmin_token,
    )
    token_a = authentication_token_from_email(client=client, email=email_a, db=db)

    email_b = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_b,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": org,
        },
        headers=get_user_systemadmin_token,
    )
    token_b = authentication_token_from_email(client=client, email=email_b, db=db)

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={"name": random_lower_string(), "time_limit": 30, "locale": "en-US"},
        headers=token_a,
    )
    assert response.status_code == 200
    test_id = response.json()["id"]

    response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json={"name": random_lower_string(), "locale": "en-US"},
        headers=token_b,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You can only update tests created by you."


def test_update_test_same_role_different_user_forbidden(
    client: TestClient,
    db: SessionDep,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = get_current_user_data(client, get_user_systemadmin_token)["organization_id"]

    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    district = District(name=random_lower_string(), state_id=state.id, is_active=True)
    db.add(district)
    db.commit()

    shared_location = {
        "state_id": [state.id],
        "district_ids": [district.id],
    }

    email_a = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_a,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": org,
            **shared_location,
        },
        headers=get_user_systemadmin_token,
    )
    token_a = authentication_token_from_email(client=client, email=email_a, db=db)

    email_b = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_b,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": org,
            **shared_location,
        },
        headers=get_user_systemadmin_token,
    )
    token_b = authentication_token_from_email(client=client, email=email_b, db=db)

    # User A creates a test in the shared location
    create_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "locale": "en-US",
            **shared_location,
        },
        headers=token_a,
    )
    assert create_resp.status_code == 200
    test_id = create_resp.json()["id"]

    # User B (same role, same location) tries to update User A's test
    update_resp = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json={"name": random_lower_string(), "locale": "en-US"},
        headers=token_b,
    )

    assert update_resp.status_code == 403
    assert update_resp.json()["detail"] == "You can only update tests created by you."


def test_get_test_by_id_not_available(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test fetching a test that does not exist should return 404."""

    non_existent_test_id = -9999

    response = client.get(
        f"{settings.API_V1_STR}/test/{non_existent_test_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Test is not available"


def test_update_test_end_time_before_start_time(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    test = Test(
        name=random_lower_string(),
        created_by_id=user_data["id"],
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
        "locale": "en-US",
    }
    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert "End time cannot be earlier than start time" in response.json()["detail"]


def test_test_check_unsupported_language(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 5,
        "locale": "xx",
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    data = response.json()

    assert response.status_code == 422
    assert data["detail"][0]["msg"] == "Input should be 'en-US' or 'hi-IN'"

    payload["locale"] = "en-US"
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    data = response.json()

    assert response.status_code == 200
    assert data["locale"] == "en-US"

    payload = {
        "name": random_lower_string(),
        "locale": "xx",
        "start_time": "2025-07-19T10:00:00Z",
        "end_time": "2025-07-19T11:00:00Z",
        "time_limit": 60,
    }

    test_id = data["id"]

    response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 422
    assert data["detail"][0]["msg"] == "Input should be 'en-US' or 'hi-IN'"

    payload["locale"] = "hi-IN"
    response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json=payload,
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["locale"] == "hi-IN"


def test_localization_default_language(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    payload = {
        "name": random_lower_string(),
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["locale"] == "en-US"


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
        created_by_id=user.id,
        is_active=True,
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

    test_link = get_test_link(db, test.id, test.created_by_id)
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
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
        "locale": "en-US",
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
        "locale": "en-US",
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


def test_update_test_rejects_question_sets_when_random_questions_already_enabled(
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
        random_questions=True,
        no_of_random_questions=1,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision_one.id))
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": "Sample Test Updated",
            "locale": "en-US",
            "question_sets": [
                {
                    "title": "Physics",
                    "description": "Section A",
                    "display_order": 1,
                    "max_questions_allowed_to_attempt": 2,
                    "question_revision_ids": [
                        question_revision_one.id,
                        question_revision_two.id,
                    ],
                }
            ],
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Question-set tests do not support random question selection in this pass."
    )


def test_update_test_revalidates_random_questions_against_final_membership(
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
        random_questions=True,
        no_of_random_questions=2,
        question_pagination=1,
        is_template=False,
        created_by_id=user.id,
    )
    db.add(test)
    db.commit()

    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision_one.id))
    db.add(TestQuestion(test_id=test.id, question_revision_id=question_revision_two.id))
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": "Sample Test",
            "question_revision_ids": [question_revision_one.id],
            "locale": "en-US",
        },
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No. of random questions (2) cannot be greater than total questions added (1)"
    )


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
        created_by_id=user.id,
        is_active=True,
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

    test_link = get_test_link(db, test.id, test.created_by_id)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
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
        "locale": "en-US",
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
    assert data["total"] == 3
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
        admin_id=user_data["id"],
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
        admin_id=user_data["id"],
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


def test_bulk_delete_multiple_tenant(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_a_id = create_random_user(db, organization_id=org_id).id
    user_b_id = create_random_user(db).id

    test_a = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        is_active=True,
        created_by_id=user_a_id,
    )
    test_b = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=30,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        is_active=True,
        created_by_id=user_b_id,
    )
    db.add_all([test_a, test_b])
    db.commit()
    db.refresh(test_a)
    db.refresh(test_b)

    response = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/test/",
        json=[test_a.id, test_b.id],
        headers=get_user_superadmin_token,
    )

    data = response.json()

    assert "invalid" in data["detail"].lower()

    assert response.status_code == 404


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


def test_create_test_with_organization_id(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/test",
        headers=get_user_superadmin_token,
        json={
            "name": random_lower_string(),
            "description": random_lower_string(),
            "time_limit": 30,
            "marks": 100,
            "start_instructions": random_lower_string(),
            "link": random_lower_string(),
            "is_active": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_by_id"] is not None
    assert data["organization_id"] is not None
    user_data = get_current_user_data(client, get_user_superadmin_token)
    assert data["organization_id"] == user_data["organization_id"]
    assert data["created_by_id"] == user_data["id"]


def test_clone_test_with_organization_id(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
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

    response = client.post(
        f"{settings.API_V1_STR}/test/{test_id}/clone",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_by_id"] is not None
    assert data["organization_id"] is not None
    assert data["id"] != test_id
    assert data["name"] == f"Copy of {test_payload['name']}"
    assert data["description"] == test_payload["description"]
    assert data["time_limit"] == test_payload["time_limit"]
    assert data["marks"] == test_payload["marks"]
    assert data["start_instructions"] == test_payload["start_instructions"]
    assert data["is_active"] == test_payload["is_active"]
    user_data = get_current_user_data(client, get_user_superadmin_token)
    assert data["organization_id"] == user_data["organization_id"]
    assert data["created_by_id"] == user_data["id"]


def test_test_list_state_user(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_y = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_x, state_y])
    db.commit()
    db.refresh(state_x)
    db.refresh(state_y)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state_x.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    user_state_x = create_random_user(db, new_organization.id)
    db.add(user_state_x)
    db.commit()
    db.refresh(user_state_x)
    db.add(UserState(user_id=user_state_x.id, state_id=state_x.id))

    user_state_y = create_random_user(db, new_organization.id)
    db.add(user_state_y)
    db.commit()
    db.refresh(user_state_y)
    db.add(UserState(user_id=user_state_y.id, state_id=state_y.id))

    another_user = create_random_user(db, new_organization.id)
    db.add(another_user)
    db.commit()
    db.refresh(another_user)

    db.commit()

    for i in range(3):
        t = Test(
            name=f"Test X {i + 1}",
            created_by_id=user_state_x.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_x.id))

    for i in range(2):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_y.id))
        db.add(TestState(test_id=t.id, state_id=state_x.id))

    for i in range(3):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_y.id))

    db.commit()

    for i in range(2):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test",
        headers=token_headers,
    )
    data = response.json()
    assert response.status_code == 200
    # state admin sees only tests explicitly mapped to their state (no general/unassigned tests)
    # - tests assigned to state_x only (3) + tests assigned to state_x AND state_y (2) = 5
    assert data["total"] == 5
    assert len(data["items"]) == 5


def test_state_admin_can_see_test_created_by_another_state_admin_same_state(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_x)
    db.commit()
    db.refresh(state_x)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email_a = random_email()
    response_a = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_a,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [state_x.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_a.status_code == 200
    token_headers_a = authentication_token_from_email(
        client=client, email=email_a, db=db
    )

    email_b = random_email()
    response_b = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_b,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [state_x.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_b.status_code == 200
    creator_id = response_b.json()["id"]

    test = Test(
        name=random_lower_string(),
        created_by_id=creator_id,
        organization_id=new_organization.id,
    )
    db.add(test)
    db.flush()
    db.refresh(test)
    db.add(TestState(test_id=test.id, state_id=state_x.id))
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test",
        headers=token_headers_a,
    )
    assert response.status_code == 200
    data = response.json()
    item_ids = [item["id"] for item in data["items"]]
    assert test.id in item_ids


def test_state_admin_cannot_see_general_test_no_location(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_x)
    db.commit()
    db.refresh(state_x)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [state_x.id],
        },
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    other_user = create_random_user(db, new_organization.id)
    db.commit()

    # General test — no state, no district — created by another user in the same org
    general_test = Test(
        name=random_lower_string(),
        created_by_id=other_user.id,
        organization_id=new_organization.id,
    )
    db.add(general_test)

    # State-mapped test — should still be visible
    state_test = Test(
        name=random_lower_string(),
        created_by_id=other_user.id,
        organization_id=new_organization.id,
    )
    db.add(state_test)
    db.flush()
    db.refresh(state_test)
    db.add(TestState(test_id=state_test.id, state_id=state_x.id))
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test", headers=token_headers)
    assert response.status_code == 200
    data = response.json()
    item_ids = [item["id"] for item in data["items"]]
    assert general_test.id not in item_ids
    assert state_test.id in item_ids


def test_state_admin_cannot_see_district_only_test(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_x)
    db.commit()
    db.refresh(state_x)

    district_x = District(
        name=random_lower_string(), is_active=True, state_id=state_x.id
    )
    db.add(district_x)
    db.commit()
    db.refresh(district_x)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state_x.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    creator = create_random_user(db, new_organization.id)
    db.commit()

    district_only_test = Test(
        name=random_lower_string(),
        created_by_id=creator.id,
        organization_id=new_organization.id,
    )
    db.add(district_only_test)
    db.flush()
    db.refresh(district_only_test)
    db.add(TestDistrict(test_id=district_only_test.id, district_id=district_x.id))

    state_only_test = Test(
        name=random_lower_string(),
        created_by_id=creator.id,
        organization_id=new_organization.id,
    )
    db.add(state_only_test)
    db.flush()
    db.refresh(state_only_test)
    db.add(TestState(test_id=state_only_test.id, state_id=state_x.id))

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test",
        headers=token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    item_ids = [item["id"] for item in data["items"]]
    assert state_only_test.id in item_ids
    assert district_only_test.id not in item_ids


def test_state_admin_cannot_see_state_and_district_test(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: SessionDep
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_x)
    db.commit()
    db.refresh(state_x)

    district_x = District(
        name=random_lower_string(), is_active=True, state_id=state_x.id
    )
    db.add(district_x)
    db.commit()
    db.refresh(district_x)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state_x.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    creator = create_random_user(db, new_organization.id)
    db.commit()

    state_and_district_test = Test(
        name=random_lower_string(),
        created_by_id=creator.id,
        organization_id=new_organization.id,
    )
    db.add(state_and_district_test)
    db.flush()
    db.refresh(state_and_district_test)
    db.add(TestState(test_id=state_and_district_test.id, state_id=state_x.id))
    db.add(TestDistrict(test_id=state_and_district_test.id, district_id=district_x.id))

    state_only_test = Test(
        name=random_lower_string(),
        created_by_id=creator.id,
        organization_id=new_organization.id,
    )
    db.add(state_only_test)
    db.flush()
    db.refresh(state_only_test)
    db.add(TestState(test_id=state_only_test.id, state_id=state_x.id))

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/test",
        headers=token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    item_ids = [item["id"] for item in data["items"]]
    assert state_only_test.id in item_ids
    assert state_and_district_test.id not in item_ids


def test_state_admin_can_delete_test_created_by_them(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = create_random_organization(db)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state.id],
    }
    resp = client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    assert resp.status_code == 200
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    test_id = response.json()["id"]

    state_admin_id = client.get(
        f"{settings.API_V1_STR}/users/me", headers=token_headers
    ).json()["id"]
    test_obj = db.get(Test, test_id)
    assert test_obj is not None
    test_obj.created_by_id = state_admin_id
    db.add(test_obj)
    db.commit()

    delete_resp = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )
    assert delete_resp.status_code == 200


def test_state_admin_can_delete_test_in_their_state(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = create_random_organization(db)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    test_id = response.json()["id"]

    state_admin_id = client.get(
        f"{settings.API_V1_STR}/users/me", headers=token_headers
    ).json()["id"]
    test_obj = db.get(Test, test_id)
    assert test_obj is not None
    test_obj.created_by_id = state_admin_id
    db.add(test_obj)
    db.commit()

    delete_resp = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )
    assert delete_resp.status_code == 200
    assert "deleted successfully" in delete_resp.json()["message"].lower()


def test_state_admin_cannot_delete_test_outside_their_state(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = create_random_organization(db)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_y = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_x, state_y])
    db.commit()
    db.refresh(state_x)
    db.refresh(state_y)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state_y.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state_x.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    test_id = response.json()["id"]

    delete_resp = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )
    assert delete_resp.status_code == 403
    assert delete_resp.json()["detail"] == "You can only delete tests created by you."


def test_state_admin_cannot_delete_multi_state_test_without_full_access(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = create_random_organization(db)
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_a = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_b = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_a, state_b])
    db.commit()
    db.refresh(state_a)
    db.refresh(state_b)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state_a.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "question_revision_ids": [],
        "tag_ids": [],
        "state_ids": [state_a.id, state_b.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    test_id = response.json()["id"]
    delete_resp = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )
    assert delete_resp.status_code == 403
    assert delete_resp.json()["detail"] == "You can only delete tests created by you."


def test_state_admin_can_delete_test_connected_via_district(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = create_random_organization(db)
    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district = District(
        name=random_lower_string(),
        state_id=state.id,
    )
    db.add(district)
    db.commit()
    db.refresh(district)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "district_ids": [district.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    test_id = response.json()["id"]

    state_admin_user = get_current_user_data(client, token_headers)
    test_obj = db.get(Test, test_id)
    assert test_obj is not None
    test_obj.created_by_id = state_admin_user["id"]
    db.add(test_obj)
    db.commit()

    delete_resp = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )

    assert delete_resp.status_code == 200
    assert "deleted successfully" in delete_resp.json()["message"].lower()


def test_state_admin_cannot_delete_multi_district_test_unless_self_created(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = create_random_organization(db)

    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    db.refresh(country)

    state_a = State(name=random_lower_string(), country_id=country.id)
    state_b = State(name=random_lower_string(), country_id=country.id)
    db.add_all([state_a, state_b])
    db.commit()
    db.refresh(state_a)
    db.refresh(state_b)

    district_a = District(
        name=random_lower_string(),
        is_active=True,
        state_id=state_a.id,
    )
    district_b = District(
        name=random_lower_string(),
        is_active=True,
        state_id=state_b.id,
    )
    db.add_all([district_a, district_b])
    db.commit()
    db.refresh(district_a)
    db.refresh(district_b)

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state_a.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "district_ids": [district_a.id, district_b.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test",
        json=test_payload,
        headers=get_user_superadmin_token,
    )
    test_id = response.json()["id"]

    delete_resp = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )

    assert delete_resp.status_code == 403
    assert delete_resp.json()["detail"] == "You can only delete tests created by you."


def test_localization_list(
    client: TestClient, get_user_testadmin_token: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/languages/",
        headers=get_user_testadmin_token,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), dict)
    data = response.json()
    assert len(data) == 2

    # Check if the expected dictionaries exist in the response
    expected_items = [
        {"en-US": "English"},
        {"hi-IN": "Hindi"},
    ]

    for expected_item in expected_items:
        # Check if expected_item is a subset of data
        assert expected_item.items() <= data.items(), (
            f"Expected items {expected_item} not found in response data {data}"
        )


def test_create_test_with_show_question_palette_true(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test creating a test with show_question_palette set to True."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "show_question_palette": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["show_question_palette"] is True


def test_create_test_with_show_question_palette_false(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test creating a test with show_question_palette set to False."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "show_question_palette": False,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["show_question_palette"] is False


def test_create_test_show_question_palette_defaults_to_false(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test that show_question_palette defaults to False when not specified."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["show_question_palette"] is False


def test_update_test_show_question_palette(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test updating show_question_palette from False to True."""
    # Create test with show_question_palette=False
    test_name = random_lower_string()
    test_description = random_lower_string()
    test_link = random_lower_string()
    create_payload = {
        "name": test_name,
        "description": test_description,
        "time_limit": 30,
        "marks": 10,
        "link": test_link,
        "is_active": True,
        "show_question_palette": False,
    }

    create_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=create_payload,
        headers=get_user_superadmin_token,
    )
    assert create_response.status_code == 200
    test_id = create_response.json()["id"]

    # Update to show_question_palette=True using PUT
    update_payload = {
        "name": test_name,
        "description": test_description,
        "time_limit": 30,
        "marks": 10,
        "link": test_link,
        "is_active": True,
        "show_question_palette": True,
        "locale": "en-US",
    }

    update_response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json=update_payload,
        headers=get_user_superadmin_token,
    )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["show_question_palette"] is True


def test_get_test_returns_show_question_palette(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test that getting a test returns the show_question_palette field."""
    # Create test with show_question_palette=True
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "show_question_palette": True,
    }

    create_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert create_response.status_code == 200
    test_id = create_response.json()["id"]

    # Get test by ID
    get_response = client.get(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=get_user_superadmin_token,
    )

    assert get_response.status_code == 200
    data = get_response.json()
    assert "show_question_palette" in data
    assert data["show_question_palette"] is True


def test_create_test_with_certificate(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    organization = create_random_organization(db)
    db.add(organization)
    db.commit()
    user = create_random_user(db, organization.id)
    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "certificate_id": certificate.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["certificate_id"] == certificate.id


def test_update_test_with_certificate(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    organization = create_random_organization(db)
    db.add(organization)
    db.commit()
    user = create_random_user(db, organization.id)

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
    }

    create_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_payload,
        headers=get_user_superadmin_token,
    )

    assert create_resp.status_code == 200
    test_id = create_resp.json()["id"]
    assert create_resp.json()["certificate_id"] is None

    update_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "certificate_id": certificate.id,
    }

    update_resp = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json=update_payload,
        headers=get_user_superadmin_token,
    )

    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["certificate_id"] == certificate.id

    update_payload["certificate_id"] = None
    remove_resp = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json=update_payload,
        headers=get_user_superadmin_token,
    )

    assert remove_resp.status_code == 200
    data_remove = remove_resp.json()
    assert data_remove["certificate_id"] is None


def test_district_user_cannot_modify_out_of_scope_test(
    client: TestClient,
    db: SessionDep,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role

    org = get_current_user_data(client, get_user_systemadmin_token)["organization_id"]

    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()

    district_1 = District(name=random_lower_string(), state_id=state.id, is_active=True)
    db.add(district_1)
    db.commit()

    district_2 = District(name=random_lower_string(), state_id=state.id, is_active=True)
    db.add(district_2)
    db.commit()

    email = random_email()

    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org,
        "state_id": [state.id],
        "district_ids": [district_1.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_systemadmin_token,
    )

    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    assert response.status_code == 200

    test_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "state_ids": [state.id],
        "district_ids": [district_1.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_payload,
        headers=token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["districts"] is not None
    test_id = data["id"]

    response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
        json=test_payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["districts"] is not None

    test_payload_district_2 = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "state_ids": [state.id],
        "district_ids": [district_2.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_payload_district_2,
        headers=get_user_systemadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["districts"] is not None
    test_id = data["id"]

    response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
        json=test_payload_district_2,
    )

    assert response.status_code == 403
    data = response.json()
    assert data["detail"] == "You can only update tests created by you."

    response = client.delete(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=token_headers,
    )

    assert response.status_code == 403
    data = response.json()
    assert data["detail"] == "You can only delete tests created by you."


def test_get_tests_by_district_user(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]

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

    district_1 = District(
        name=random_lower_string(), is_active=True, state_id=state_1.id
    )
    district_11 = District(
        name=random_lower_string(), is_active=True, state_id=state_1.id
    )
    district_2 = District(
        name=random_lower_string(), is_active=True, state_id=state_2.id
    )
    db.add_all([district_1, district_11, district_2])
    db.commit()
    db.refresh(district_1)
    db.refresh(district_11)
    db.refresh(district_2)

    email = random_email()

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role
    state_admin_user_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org_id,
        "state_id": state_1.id,
        "district_ids": [district_1.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_user_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()

    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    test_1_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "state_ids": [state_1.id],
        "district_ids": [district_1.id],
    }

    test_11_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "state_ids": [state_1.id],
        "district_ids": [district_11.id],
    }

    test_2_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "state_ids": [state_2.id],
        "district_ids": [district_2.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_1_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    test_1_name = response.json()["name"]

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_11_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    test_11_name = response.json()["name"]

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_2_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    test_2_name = response.json()["name"]

    # test assigned to state_1 only (no district) — should be visible to user in district_1
    test_state_only_payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "locale": "en-US",
        "state_ids": [state_1.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=test_state_only_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    test_state_only_name = response.json()["name"]

    response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    returned_names = {item["name"] for item in items}
    # district user sees: test_1 (own district) + test_state_only (state, no district)
    # test_11 (same state but different district) and test_2 (different state) are excluded
    assert len(items) == 2
    assert test_1_name in returned_names
    assert test_state_only_name in returned_names
    assert test_11_name not in returned_names
    assert test_2_name not in returned_names


def test_test_admin_with_district_can_see_state_level_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A test_admin scoped to Ambala district should see tests created by a
    state_admin for Haryana (state-level, no district), but NOT tests created
    specifically for a different district (e.g. Rohtak).
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    haryana = State(name="Haryana", is_active=True, country_id=country.id)
    db.add(haryana)
    db.commit()
    db.refresh(haryana)

    ambala = District(name="Ambala", is_active=True, state_id=haryana.id)
    rohtak = District(name="Rohtak", is_active=True, state_id=haryana.id)
    db.add_all([ambala, rohtak])
    db.commit()
    db.refresh(ambala)
    db.refresh(rohtak)

    # Create state_admin scoped to Haryana
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None
    state_admin_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": state_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [haryana.id],
        },
        headers=get_user_superadmin_token,
    )
    state_admin_token = authentication_token_from_email(
        client=client, email=state_admin_email, db=db
    )

    # Create test_admin scoped to Ambala district
    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None
    test_admin_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": test_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [ambala.id],
        },
        headers=get_user_superadmin_token,
    )
    test_admin_token = authentication_token_from_email(
        client=client, email=test_admin_email, db=db
    )

    # State-admin creates a test for Haryana (state-level, no district)
    haryana_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "state_ids": [haryana.id],
        },
        headers=state_admin_token,
    )
    assert haryana_test_response.status_code == 200
    haryana_test_id = haryana_test_response.json()["id"]

    # State-admin creates a test scoped specifically to Rohtak (different district)
    rohtak_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "district_ids": [rohtak.id],
        },
        headers=state_admin_token,
    )
    assert rohtak_test_response.status_code == 200
    rohtak_test_id = rohtak_test_response.json()["id"]

    response = client.get(f"{settings.API_V1_STR}/test/", headers=test_admin_token)
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()["items"]]

    assert haryana_test_id in item_ids
    assert rohtak_test_id not in item_ids


def test_state_admin_cannot_see_district_level_test(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A state_admin scoped to Haryana should NOT see tests created specifically
    for a district (e.g. Ambala) even though Ambala belongs to Haryana.
    State-level tests for Haryana must remain visible.
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    haryana = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(haryana)
    db.commit()
    db.refresh(haryana)

    ambala = District(name=random_lower_string(), is_active=True, state_id=haryana.id)
    db.add(ambala)
    db.commit()
    db.refresh(ambala)

    # Create state_admin scoped to Haryana
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None
    state_admin_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": state_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [haryana.id],
        },
        headers=get_user_superadmin_token,
    )
    state_admin_token = authentication_token_from_email(
        client=client, email=state_admin_email, db=db
    )

    # Create test_admin scoped to Ambala district
    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None
    test_admin_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": test_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [ambala.id],
        },
        headers=get_user_superadmin_token,
    )
    test_admin_token = authentication_token_from_email(
        client=client, email=test_admin_email, db=db
    )

    # test_admin creates a test scoped to Ambala district
    ambala_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "district_ids": [ambala.id],
        },
        headers=test_admin_token,
    )
    assert ambala_test_response.status_code == 200
    ambala_test_id = ambala_test_response.json()["id"]

    # state_admin creates a state-level test for Haryana
    haryana_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "state_ids": [haryana.id],
        },
        headers=state_admin_token,
    )
    assert haryana_test_response.status_code == 200
    haryana_test_id = haryana_test_response.json()["id"]

    response = client.get(f"{settings.API_V1_STR}/test/", headers=state_admin_token)
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()["items"]]

    assert haryana_test_id in item_ids
    assert ambala_test_id not in item_ids


def test_district_user_can_see_test_created_by_peer_in_same_district(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A test_admin scoped to district A should be able to see a test created by
    another test_admin who is also scoped to district A.
    Tests created for a different district must remain invisible.
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district_a = District(name=random_lower_string(), is_active=True, state_id=state.id)
    district_b = District(name=random_lower_string(), is_active=True, state_id=state.id)
    db.add_all([district_a, district_b])
    db.commit()
    db.refresh(district_a)
    db.refresh(district_b)

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    # First test_admin — scoped to district_a (creator)
    creator_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": creator_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [district_a.id],
        },
        headers=get_user_superadmin_token,
    )
    creator_token = authentication_token_from_email(
        client=client, email=creator_email, db=db
    )

    # Second test_admin — scoped to the same district_a (viewer)
    viewer_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": viewer_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [district_a.id],
        },
        headers=get_user_superadmin_token,
    )
    viewer_token = authentication_token_from_email(
        client=client, email=viewer_email, db=db
    )

    # Third test_admin — scoped to district_b (different district, same state)
    other_district_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": other_district_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [district_b.id],
        },
        headers=get_user_superadmin_token,
    )
    other_district_token = authentication_token_from_email(
        client=client, email=other_district_email, db=db
    )

    # Creator creates a test for district_a
    district_a_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "district_ids": [district_a.id],
        },
        headers=creator_token,
    )
    assert district_a_test_response.status_code == 200
    district_a_test_id = district_a_test_response.json()["id"]

    # Other-district user creates a test for district_b
    district_b_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "district_ids": [district_b.id],
        },
        headers=other_district_token,
    )
    assert district_b_test_response.status_code == 200
    district_b_test_id = district_b_test_response.json()["id"]

    response = client.get(f"{settings.API_V1_STR}/test/", headers=viewer_token)
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()["items"]]

    # Viewer (district_a) can see the test created by their peer in district_a
    assert district_a_test_id in item_ids
    # Viewer (district_a) cannot see the test scoped to district_b
    assert district_b_test_id not in item_ids


def test_district_user_cannot_see_general_test_no_location(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A test_admin scoped to a district must NOT see General Tests (tests with no
    state or district mapping) created by other users.
    Tests explicitly mapped to their district must still be visible.
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district = District(name=random_lower_string(), is_active=True, state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    district_user_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": district_user_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [district.id],
        },
        headers=get_user_superadmin_token,
    )
    district_user_token = authentication_token_from_email(
        client=client, email=district_user_email, db=db
    )

    other_user = create_random_user(db, new_organization.id)
    db.commit()

    # General test — no state, no district — created by another user in the same org
    general_test = Test(
        name=random_lower_string(),
        created_by_id=other_user.id,
        organization_id=new_organization.id,
    )
    db.add(general_test)

    # District-mapped test — should still be visible to the district user
    district_test = Test(
        name=random_lower_string(),
        created_by_id=other_user.id,
        organization_id=new_organization.id,
    )
    db.add(district_test)
    db.flush()
    db.refresh(district_test)
    db.add(TestDistrict(test_id=district_test.id, district_id=district.id))
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/", headers=district_user_token)
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()["items"]]

    assert general_test.id not in item_ids
    assert district_test.id in item_ids


def test_district_user_cannot_see_test_from_state_admin_of_different_state(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A test_admin scoped to a district in state X must NOT see tests created by
    a state_admin scoped to state B (a different state), even when both users
    belong to the same organization.
    State-level tests for state X must still be visible to the district user.
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_b = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_x, state_b])
    db.commit()
    db.refresh(state_x)
    db.refresh(state_b)

    district_x = District(
        name=random_lower_string(), is_active=True, state_id=state_x.id
    )
    db.add(district_x)
    db.commit()
    db.refresh(district_x)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None
    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    # state_admin scoped to state X
    state_admin_x_email = random_email()
    response_x = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": state_admin_x_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [state_x.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_x.status_code == 200
    state_admin_x_token = authentication_token_from_email(
        client=client, email=state_admin_x_email, db=db
    )

    # state_admin scoped to state B (different state, same org)
    state_admin_b_email = random_email()
    response_b = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": state_admin_b_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [state_b.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_b.status_code == 200
    state_admin_b_token = authentication_token_from_email(
        client=client, email=state_admin_b_email, db=db
    )

    # test_admin scoped to district in state X
    test_admin_email = random_email()
    response_ta = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": test_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [district_x.id],
        },
        headers=get_user_superadmin_token,
    )
    assert response_ta.status_code == 200
    test_admin_token = authentication_token_from_email(
        client=client, email=test_admin_email, db=db
    )

    # state_admin B creates a state-level test for state B
    state_b_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "state_ids": [state_b.id],
        },
        headers=state_admin_b_token,
    )
    assert state_b_test_response.status_code == 200
    state_b_test_id = state_b_test_response.json()["id"]

    # state_admin X creates a state-level test for state X (positive control)
    state_x_test_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "locale": "en-US",
            "state_ids": [state_x.id],
        },
        headers=state_admin_x_token,
    )
    assert state_x_test_response.status_code == 200
    state_x_test_id = state_x_test_response.json()["id"]

    response = client.get(f"{settings.API_V1_STR}/test/", headers=test_admin_token)
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()["items"]]

    assert state_x_test_id in item_ids
    assert state_b_test_id not in item_ids


def test_unscoped_test_admin_can_see_all_org_tests(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A test_admin with no district or state assigned is not location-restricted
    and must be able to see all tests in their organization.
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    # test_admin with no district or state assigned
    unscoped_email = random_email()
    response_unscoped = client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": unscoped_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
        },
        headers=get_user_superadmin_token,
    )
    assert response_unscoped.status_code == 200
    unscoped_token = authentication_token_from_email(
        client=client, email=unscoped_email, db=db
    )

    other_user = create_random_user(db, new_organization.id)
    db.commit()

    # State-mapped test created by another user in the same org
    org_test = Test(
        name=random_lower_string(),
        created_by_id=other_user.id,
        organization_id=new_organization.id,
    )
    db.add(org_test)
    db.flush()
    db.refresh(org_test)
    db.add(TestState(test_id=org_test.id, state_id=state.id))
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/", headers=unscoped_token)
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()["items"]]

    assert org_test.id in item_ids


def test_create_test_show_mark_for_review_true(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test creating a test with show_mark_for_review set to True."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "bookmark": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bookmark"] is True


def test_create_test_show_mark_for_review_false(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test creating a test with show_mark_for_review set to False."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "bookmark": False,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bookmark"] is False


def test_create_test_show_mark_for_review_defaults_to_true(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test that show_mark_for_review defaults to True when not specified."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["bookmark"] is True


def test_update_test_show_mark_for_review(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test updating show_mark_for_review from True to False."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    test_name = random_lower_string()
    test_link = random_lower_string()
    create_payload = {
        "name": test_name,
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": test_link,
        "is_active": True,
        "bookmark": True,
    }

    create_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=create_payload,
        headers=get_user_superadmin_token,
    )
    assert create_response.status_code == 200
    test_id = create_response.json()["id"]

    update_payload = {
        "name": test_name,
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": test_link,
        "is_active": True,
        "bookmark": False,
        "locale": "en-US",
    }

    update_response = client.put(
        f"{settings.API_V1_STR}/test/{test_id}",
        json=update_payload,
        headers=get_user_superadmin_token,
    )

    assert update_response.status_code == 200
    data = update_response.json()
    assert data["bookmark"] is False


def test_get_test_by_id_returns_show_mark_for_review(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test that GET /test/{id} returns the show_mark_for_review field."""
    make_current_user_org_flexible(
        client=client, session=db, auth_header=get_user_superadmin_token
    )
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "bookmark": False,
    }

    create_response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert create_response.status_code == 200
    test_id = create_response.json()["id"]

    get_response = client.get(
        f"{settings.API_V1_STR}/test/{test_id}",
        headers=get_user_superadmin_token,
    )

    assert get_response.status_code == 200
    data = get_response.json()
    assert "bookmark" in data
    assert data["bookmark"] is False


def test_get_tests_list_returns_show_mark_for_review(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test that GET /test/ list endpoint returns show_mark_for_review field."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "bookmark": True,
    }

    client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    list_response = client.get(
        f"{settings.API_V1_STR}/test/",
        headers=get_user_superadmin_token,
    )

    assert list_response.status_code == 200
    data = list_response.json()
    assert "items" in data
    assert len(data["items"]) > 0
    assert "bookmark" in data["items"][0]


def test_get_test_status(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user = create_random_user(db, organization_id=org_id)

    now = get_current_time()

    # No start/end times → In Progress
    test_always_in_progress = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
    )
    # Both start/end times → In Progress
    test_current_in_progress = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=1),
    )
    # start_time in the future → Scheduled
    test_scheduled = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
        start_time=now + timedelta(days=1),
    )
    # end_time in the past → Completed
    test_completed = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
        end_time=now - timedelta(days=1),
    )
    test_is_template = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        created_by_id=user.id,
        link=random_lower_string(),
        no_of_random_questions=1,
        organization_id=org_id,
        is_template=True,
    )
    db.add_all(
        [
            test_always_in_progress,
            test_current_in_progress,
            test_scheduled,
            test_completed,
            test_is_template,
        ]
    )
    db.commit()

    for test, expected_status in [
        (test_always_in_progress, "In Progress"),
        (test_current_in_progress, "In Progress"),
        (test_scheduled, "Scheduled"),
        (test_completed, "Completed"),
        (test_is_template, None),
    ]:
        response = client.get(
            f"{settings.API_V1_STR}/test/{test.id}",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == expected_status


def test_get_test_status_changes_with_time(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """A single test transitions Scheduled → In Progress → Completed as time advances."""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user = create_random_user(db, organization_id=user_data["organization_id"])

    start = datetime(2025, 6, 1, 10, 0, 0)
    end = datetime(2025, 6, 1, 12, 0, 0)

    test = Test(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user_data["organization_id"],
        start_time=start,
        end_time=end,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    def get_status(mocked_now: datetime) -> str:
        with patch("app.api.routes.test.get_current_time", return_value=mocked_now):
            response = client.get(
                f"{settings.API_V1_STR}/test/{test.id}",
                headers=get_user_superadmin_token,
            )
        assert response.status_code == status.HTTP_200_OK
        return str(response.json()["status"])

    # Before start_time → Scheduled
    assert get_status(datetime(2025, 5, 31, 9, 0, 0)) == "Scheduled"

    # After start_time, before end_time → In Progress
    assert get_status(datetime(2025, 6, 1, 11, 0, 0)) == "In Progress"

    # After end_time → Completed
    assert get_status(datetime(2025, 6, 1, 13, 0, 0)) == "Completed"


def test_create_test_with_show_marks_true(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test creating a test with show_marks set to True."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "show_marks": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["show_marks"] is True


def test_create_test_with_show_marks_false(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Test creating a test with show_marks set to False."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "time_limit": 30,
        "marks": 10,
        "link": random_lower_string(),
        "is_active": True,
        "show_marks": False,
    }

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["show_marks"] is False
    assert "bookmark" in data


# ---------------------------------------------------------------------------
# GET /{test_id}/link
# ---------------------------------------------------------------------------


def test_get_or_create_test_link_creates_new(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """GET /{test_id}/link creates and returns a UUID for a new test."""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    test = Test(name=random_lower_string(), created_by_id=user_id, is_active=True)
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    response = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/link",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert "uuid" in data
    assert data["uuid"] != ""


def test_get_or_create_test_link_is_idempotent(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """Calling GET /{test_id}/link twice returns the same UUID."""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    test = Test(name=random_lower_string(), created_by_id=user_id, is_active=True)
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    response1 = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/link",
        headers=get_user_superadmin_token,
    )
    response2 = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/link",
        headers=get_user_superadmin_token,
    )
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["uuid"] == response2.json()["uuid"]


def test_get_or_create_test_link_different_admins_get_different_uuids(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
    get_user_testadmin_token: dict[str, str],
) -> None:
    """Two different admins calling GET /{test_id}/link receive different UUIDs."""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    test = Test(name=random_lower_string(), created_by_id=user_id, is_active=True)
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    response1 = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/link",
        headers=get_user_superadmin_token,
    )
    response2 = client.get(
        f"{settings.API_V1_STR}/test/{test.id}/link",
        headers=get_user_testadmin_token,
    )
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["uuid"] != response2.json()["uuid"]


def test_get_or_create_test_link_test_not_found(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """GET /{test_id}/link returns 404 when the test does not exist."""
    response = client.get(
        f"{settings.API_V1_STR}/test/999999/link",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Test not found"


def test_get_or_create_test_link_template_rejected(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """GET /{test_id}/link returns 400 for template tests."""
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    template = Test(
        name=random_lower_string(),
        created_by_id=user_id,
        is_template=True,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    assert template.id is not None

    response = client.get(
        f"{settings.API_V1_STR}/test/{template.id}/link",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Templates do not have shareable links."


# ---------------------------------------------------------------------------
# GET /test/public/{uuid} — link field in response
# ---------------------------------------------------------------------------


def test_public_endpoint_response_includes_link(
    client: TestClient, db: SessionDep
) -> None:
    """GET /test/public/{uuid} response body includes a link equal to the UUID."""
    user = create_random_user(db)
    assert user.id is not None

    test = Test(name=random_lower_string(), created_by_id=user.id, is_active=True)
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    test_link = get_test_link(db, test_id=test.id, admin_id=user.id)

    response = client.get(f"{settings.API_V1_STR}/test/public/{test_link.uuid}")
    assert response.status_code == 200
    assert response.json()["link"] == test_link.uuid


# ---------------------------------------------------------------------------
# TestLink cascade — deleting a User removes their TestLink rows
# ---------------------------------------------------------------------------


def test_test_link_cascade_deleted_when_user_deleted(db: SessionDep) -> None:
    """Deleting a User cascades to their TestLink rows (ORM + DB level)."""
    # Use a separate admin to own the test so deleting user_to_delete
    # doesn't violate the Test.created_by_id FK.
    test_owner = create_random_user(db)
    assert test_owner.id is not None

    user_to_delete = create_random_user(db)
    assert user_to_delete.id is not None

    test = Test(name=random_lower_string(), created_by_id=test_owner.id, is_active=True)
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    test_link = get_test_link(db, test_id=test.id, admin_id=user_to_delete.id)
    test_link_id = test_link.id

    db.delete(user_to_delete)
    db.commit()

    from app.models.test import TestLink

    remaining = db.get(TestLink, test_link_id)
    assert remaining is None


# ---------------------------------------------------------------------------
# Test creation / clone — link field removed
# ---------------------------------------------------------------------------


def test_create_test_response_has_no_link_field(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Creating a test no longer returns a link field in the response."""
    payload = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "is_active": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json=payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    assert "link" not in response.json()


def test_clone_test_does_not_generate_test_link(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """Cloning a test does not auto-create a TestLink for the cloning admin."""
    from sqlmodel import select

    from app.models.test import TestLink

    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    test = Test(name=random_lower_string(), created_by_id=user_id, is_active=True)
    db.add(test)
    db.commit()
    db.refresh(test)
    assert test.id is not None

    response = client.post(
        f"{settings.API_V1_STR}/test/{test.id}/clone",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    cloned_id = response.json()["id"]

    links = db.exec(select(TestLink).where(TestLink.test_id == cloned_id)).all()
    assert links == []


def test_get_tests_my_tests_filter(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """my_tests=True returns only tests created by the current user;
    my_tests=False excludes them — regardless of location assignment."""
    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    # --- district-level user ---

    org_district = create_random_organization(db)
    db.add(org_district)
    db.commit()
    db.refresh(org_district)

    state_d = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_d)
    db.commit()
    db.refresh(state_d)

    district = District(name=random_lower_string(), is_active=True, state_id=state_d.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    email_district = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_district,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": org_district.id,
            "district_ids": [district.id],
        },
        headers=get_user_superadmin_token,
    )
    district_user_headers = authentication_token_from_email(
        client=client, email=email_district, db=db
    )
    district_user_id = get_current_user_data(client, district_user_headers)["id"]

    # another user in the same org to own the "other" tests
    d_other_user = create_random_user(db, org_district.id)
    assert d_other_user.id is not None

    # tests created by the district admin — assigned to the same district
    d_my_test_1 = Test(
        name=random_lower_string(),
        created_by_id=district_user_id,
        organization_id=org_district.id,
    )
    d_my_test_2 = Test(
        name=random_lower_string(),
        created_by_id=district_user_id,
        organization_id=org_district.id,
    )
    # tests created by another user — assigned to the same district
    d_other_test_1 = Test(
        name=random_lower_string(),
        created_by_id=d_other_user.id,
        organization_id=org_district.id,
    )
    d_other_test_2 = Test(
        name=random_lower_string(),
        created_by_id=d_other_user.id,
        organization_id=org_district.id,
    )
    db.add_all([d_my_test_1, d_my_test_2, d_other_test_1, d_other_test_2])
    db.commit()
    db.refresh(d_my_test_1)
    db.refresh(d_my_test_2)
    db.refresh(d_other_test_1)
    db.refresh(d_other_test_2)

    db.add_all(
        [
            TestDistrict(test_id=d_my_test_1.id, district_id=district.id),
            TestDistrict(test_id=d_my_test_2.id, district_id=district.id),
            TestDistrict(test_id=d_other_test_1.id, district_id=district.id),
            TestDistrict(test_id=d_other_test_2.id, district_id=district.id),
        ]
    )
    db.commit()

    assert d_my_test_1.id is not None
    assert d_my_test_2.id is not None
    assert d_other_test_1.id is not None
    assert d_other_test_2.id is not None

    response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=true",
        headers=district_user_headers,
    )
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert d_my_test_1.id in returned_ids
    assert d_my_test_2.id in returned_ids
    assert d_other_test_1.id not in returned_ids
    assert d_other_test_2.id not in returned_ids

    response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=false",
        headers=district_user_headers,
    )
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert d_my_test_1.id not in returned_ids
    assert d_my_test_2.id not in returned_ids
    assert d_other_test_1.id in returned_ids
    assert d_other_test_2.id in returned_ids

    # --- state-level user ---

    org_state = create_random_organization(db)
    db.add(org_state)
    db.commit()
    db.refresh(org_state)

    state_s = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_s)
    db.commit()
    db.refresh(state_s)

    email_state = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email_state,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": org_state.id,
            "state_ids": [state_s.id],
        },
        headers=get_user_superadmin_token,
    )
    state_user_headers = authentication_token_from_email(
        client=client, email=email_state, db=db
    )
    state_user_id = get_current_user_data(client, state_user_headers)["id"]

    # another user in the same org to own the "other" tests
    s_other_user = create_random_user(db, org_state.id)
    assert s_other_user.id is not None

    # tests created by the state admin - assigned to the same state
    s_my_test_1 = Test(
        name=random_lower_string(),
        created_by_id=state_user_id,
        organization_id=org_state.id,
    )
    s_my_test_2 = Test(
        name=random_lower_string(),
        created_by_id=state_user_id,
        organization_id=org_state.id,
    )
    # tests created by another user — assigned to the same state
    s_other_test_1 = Test(
        name=random_lower_string(),
        created_by_id=s_other_user.id,
        organization_id=org_state.id,
    )
    s_other_test_2 = Test(
        name=random_lower_string(),
        created_by_id=s_other_user.id,
        organization_id=org_state.id,
    )
    db.add_all([s_my_test_1, s_my_test_2, s_other_test_1, s_other_test_2])
    db.commit()
    db.refresh(s_my_test_1)
    db.refresh(s_my_test_2)
    db.refresh(s_other_test_1)
    db.refresh(s_other_test_2)

    db.add_all(
        [
            TestState(test_id=s_my_test_1.id, state_id=state_s.id),
            TestState(test_id=s_my_test_2.id, state_id=state_s.id),
            TestState(test_id=s_other_test_1.id, state_id=state_s.id),
            TestState(test_id=s_other_test_2.id, state_id=state_s.id),
        ]
    )
    db.commit()

    assert s_my_test_1.id is not None
    assert s_my_test_2.id is not None
    assert s_other_test_1.id is not None
    assert s_other_test_2.id is not None

    response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=true",
        headers=state_user_headers,
    )
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert s_my_test_1.id in returned_ids
    assert s_my_test_2.id in returned_ids
    assert s_other_test_1.id not in returned_ids
    assert s_other_test_2.id not in returned_ids

    response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=false",
        headers=state_user_headers,
    )
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert s_my_test_1.id not in returned_ids
    assert s_my_test_2.id not in returned_ids
    assert s_other_test_1.id in returned_ids
    assert s_other_test_2.id in returned_ids


def test_get_tests_my_tests_filter_no_location_user(
    client: TestClient,
    db: SessionDep,
    get_user_systemadmin_token: dict[str, str],
) -> None:
    """When a user has no location assigned, my_tests=True returns only tests
    created by that user; my_tests=False excludes them."""
    user_data = get_current_user_data(client, get_user_systemadmin_token)
    user_id = user_data["id"]
    org_id = user_data["organization_id"]

    other_user = create_random_user(db, org_id)
    assert other_user.id is not None

    my_test_1 = Test(
        name=random_lower_string(), created_by_id=user_id, organization_id=org_id
    )
    my_test_2 = Test(
        name=random_lower_string(), created_by_id=user_id, organization_id=org_id
    )
    other_test_1 = Test(
        name=random_lower_string(), created_by_id=other_user.id, organization_id=org_id
    )
    other_test_2 = Test(
        name=random_lower_string(), created_by_id=other_user.id, organization_id=org_id
    )
    db.add_all([my_test_1, my_test_2, other_test_1, other_test_2])
    db.commit()
    db.refresh(my_test_1)
    db.refresh(my_test_2)
    db.refresh(other_test_1)
    db.refresh(other_test_2)

    assert my_test_1.id is not None
    assert my_test_2.id is not None
    assert other_test_1.id is not None
    assert other_test_2.id is not None

    # my_tests=True: only tests created by the current user
    response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=true",
        headers=get_user_systemadmin_token,
    )
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert my_test_1.id in returned_ids
    assert my_test_2.id in returned_ids
    assert other_test_1.id not in returned_ids
    assert other_test_2.id not in returned_ids

    # my_tests=False: tests NOT created by the current user
    response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=false",
        headers=get_user_systemadmin_token,
    )
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert my_test_1.id not in returned_ids
    assert my_test_2.id not in returned_ids
    assert other_test_1.id in returned_ids
    assert other_test_2.id in returned_ids


def test_state_admin_can_see_tests_they_created_outside_their_location(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A state_admin scoped to state_A should see tests they personally created
    even if those tests are mapped to state_B (outside their location scope).
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_a = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_b = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_a, state_b])
    db.commit()
    db.refresh(state_a)
    db.refresh(state_b)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None
    state_admin_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": state_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": state_admin_role.id,
            "organization_id": new_organization.id,
            "state_ids": [state_a.id],
        },
        headers=get_user_superadmin_token,
    )
    state_admin_token = authentication_token_from_email(
        client=client, email=state_admin_email, db=db
    )

    # state_admin creates a test mapped to state_B (outside their own state_A scope)
    outside_test_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "state_ids": [state_b.id],
        },
        headers=state_admin_token,
    )
    assert outside_test_resp.status_code == 200
    outside_test_id = outside_test_resp.json()["id"]

    # state_admin creates a test mapped to their own state_A (within scope)
    in_scope_test_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "state_ids": [state_a.id],
        },
        headers=state_admin_token,
    )
    assert in_scope_test_resp.status_code == 200
    in_scope_test_id = in_scope_test_resp.json()["id"]

    response = client.get(f"{settings.API_V1_STR}/test/", headers=state_admin_token)
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}

    # Both tests must be visible: in-scope by location, out-of-scope because created by them
    assert in_scope_test_id in returned_ids
    assert outside_test_id in returned_ids

    # my_tests=true: both tests are visible because the state_admin created them
    my_tests_response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=true", headers=state_admin_token
    )
    assert my_tests_response.status_code == 200
    my_tests_ids = {item["id"] for item in my_tests_response.json()["items"]}
    assert in_scope_test_id in my_tests_ids
    assert outside_test_id in my_tests_ids

    # my_tests=false: neither test is visible because both were created by the state_admin
    not_my_tests_response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=false", headers=state_admin_token
    )
    assert not_my_tests_response.status_code == 200
    not_my_tests_ids = {item["id"] for item in not_my_tests_response.json()["items"]}
    assert in_scope_test_id not in not_my_tests_ids
    assert outside_test_id not in not_my_tests_ids


def test_test_admin_can_see_tests_they_created_outside_their_district(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    """
    A test_admin scoped to district_A should see tests they personally created
    even if those tests are mapped to district_B (outside their location scope).
    """
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district_a = District(name=random_lower_string(), is_active=True, state_id=state.id)
    district_b = District(name=random_lower_string(), is_active=True, state_id=state.id)
    db.add_all([district_a, district_b])
    db.commit()
    db.refresh(district_a)
    db.refresh(district_b)

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None
    test_admin_email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": test_admin_email,
            "password": random_lower_string(),
            "phone": random_lower_string(),
            "full_name": random_lower_string(),
            "role_id": test_admin_role.id,
            "organization_id": new_organization.id,
            "district_ids": [district_a.id],
        },
        headers=get_user_superadmin_token,
    )
    test_admin_token = authentication_token_from_email(
        client=client, email=test_admin_email, db=db
    )

    # test_admin creates a test mapped to district_B (outside their district_A scope)
    outside_test_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "district_ids": [district_b.id],
        },
        headers=test_admin_token,
    )
    assert outside_test_resp.status_code == 200
    outside_test_id = outside_test_resp.json()["id"]

    # test_admin creates a test mapped to their own district_A (within scope)
    in_scope_test_resp = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": random_lower_string(),
            "time_limit": 30,
            "marks": 10,
            "link": random_lower_string(),
            "district_ids": [district_a.id],
        },
        headers=test_admin_token,
    )
    assert in_scope_test_resp.status_code == 200
    in_scope_test_id = in_scope_test_resp.json()["id"]

    response = client.get(f"{settings.API_V1_STR}/test/", headers=test_admin_token)
    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}

    # Both tests must be visible: in-scope by location, out-of-scope because created by them
    assert in_scope_test_id in returned_ids
    assert outside_test_id in returned_ids

    # my_tests=true: both tests are visible because the test_admin created them
    my_tests_response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=true", headers=test_admin_token
    )
    assert my_tests_response.status_code == 200
    my_tests_ids = {item["id"] for item in my_tests_response.json()["items"]}
    assert in_scope_test_id in my_tests_ids
    assert outside_test_id in my_tests_ids

    # my_tests=false: neither test is visible because both were created by the test_admin
    not_my_tests_response = client.get(
        f"{settings.API_V1_STR}/test/?my_tests=false", headers=test_admin_token
    )
    assert not_my_tests_response.status_code == 200
    not_my_tests_ids = {item["id"] for item in not_my_tests_response.json()["items"]}
    assert in_scope_test_id not in not_my_tests_ids
    assert outside_test_id not in not_my_tests_ids
