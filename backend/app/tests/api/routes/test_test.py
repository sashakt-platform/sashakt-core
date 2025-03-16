from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.location import Country, State
from app.models.question import Question
from app.models.tag import Tag
from app.models.test import (
    Test,
    TestQuestionStaticLink,
    TestStateLocationLink,
    TestTagLink,
)
from app.models.user import User
from app.tests.utils.utils import random_email, random_lower_string


def test_create_test(client: TestClient, db: SessionDep):
    india = Country(name="India")
    db.add(india)
    db.commit()
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    goa = State(name="Goa", country_id=india.id)
    db.add(goa)
    db.commit()

    tag_hindi = Tag(name="Hindi")
    tag_marathi = Tag(name="Marathi")
    db.add(tag_hindi)
    db.add(tag_marathi)
    db.commit()

    question_one = Question(question="What is the size of Sun")
    question_two = Question(question="What is the speed of light")
    db.add(question_one)
    db.add(question_two)
    db.commit()

    arvind = User(
        full_name="Arvind S",
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(arvind)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": "Hindi Test",
            "description": "fdfdfdf",
            "time_limit": 2,
            "marks": 3,
            "completion_message": "string",
            "start_instructions": "string",
            "marks_level": None,
            "link": "string",
            "no_of_attempts": 1,
            "shuffle": False,
            "random_questions": False,
            "no_of_questions": 4,
            "question_pagination": 1,
            "is_template": False,
            "created_by_id": arvind.id,
            "tags": [tag_hindi.id, tag_marathi.id],
            "test_question_static": [question_one.id, question_two.id],
            "states": [punjab.id],
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Hindi Test"
    assert data["description"] == "fdfdfdf"
    assert data["time_limit"] == 2
    assert data["marks"] == 3
    assert data["completion_message"] == "string"
    assert data["start_instructions"] == "string"
    assert data["marks_level"] is None
    assert data["link"] == "string"
    assert data["no_of_attempts"] == 1
    assert data["shuffle"] is False
    assert data["random_questions"] is False
    assert data["no_of_questions"] == 4
    assert data["question_pagination"] == 1
    assert data["is_template"] is False
    assert data["created_by_id"] == arvind.id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert len(data["tags"]) == 2
    assert data["tags"][0] == tag_hindi.id
    assert data["tags"][1] == tag_marathi.id
    assert data["states"][0] == punjab.id

    test_tag_link = db.exec(
        select(TestTagLink).where(TestTagLink.test_id == data["id"])
    ).all()

    assert test_tag_link[0].tag_id == tag_hindi.id
    assert test_tag_link[1].tag_id == tag_marathi.id

    test_question_link = db.exec(
        select(TestQuestionStaticLink).where(
            TestQuestionStaticLink.test_id == data["id"]
        )
    ).all()

    assert test_question_link[0].question_id == question_one.id
    assert test_question_link[1].question_id == question_two.id

    sample_test = Test(
        name="Sample Test",
        description="Sample description",
        time_limit=5,
        marks=10,
        completion_message="Well done!",
        start_instructions="Follow the instructions carefully.",
        marks_level=None,
        link="sample_link",
        no_of_attempts=1,
        shuffle=False,
        random_questions=False,
        no_of_questions=2,
        question_pagination=1,
        is_template=True,
        created_by_id=arvind.id,
    )
    db.add(sample_test)
    db.commit()

    marathi_test_name = "Marathi Test"
    marathi_test_description = "This is marathi Test"
    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
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
            "created_by_id": arvind.id,
            "tags": [tag_hindi.id, tag_marathi.id],
            "test_question_static": [question_one.id, question_two.id],
            "states": [punjab.id, goa.id],
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == marathi_test_name
    assert data["description"] == marathi_test_description
    assert data["time_limit"] == 10
    assert data["marks"] == 3
    assert data["completion_message"] == "Congratulations!!"
    assert data["start_instructions"] == "Please keep your mobile phones away"
    assert data["marks_level"] is None
    assert data["link"] == "string"
    assert data["no_of_attempts"] == 1
    assert data["shuffle"] is False
    assert data["random_questions"] is False
    assert data["no_of_questions"] == 4
    assert data["question_pagination"] == 1
    assert data["is_template"] is False
    assert data["template_id"] == sample_test.id
    assert data["created_by_id"] == arvind.id
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

    test_tag_link = db.exec(
        select(TestTagLink).where(TestTagLink.test_id == data["id"])
    ).all()

    assert test_tag_link[0].tag_id == tag_hindi.id
    assert test_tag_link[1].tag_id == tag_marathi.id

    test_question_link = db.exec(
        select(TestQuestionStaticLink).where(
            TestQuestionStaticLink.test_id == data["id"]
        )
    ).all()

    assert test_question_link[0].question_id == question_one.id
    assert test_question_link[1].question_id == question_two.id

    response = client.post(
        f"{settings.API_V1_STR}/test/",
        json={
            "name": marathi_test_name + "NN",
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
            "created_by_id": arvind.id,
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["name"] == marathi_test_name + "NN"
    assert data["description"] == marathi_test_description
    assert data["time_limit"] == 10
    assert data["marks"] == 3
    assert data["completion_message"] == "Congratulations!!"
    assert data["start_instructions"] == "Please keep your mobile phones away"
    assert data["marks_level"] is None
    assert data["link"] == "string"
    assert data["no_of_attempts"] == 1
    assert data["shuffle"] is False
    assert data["random_questions"] is False
    assert data["no_of_questions"] == 4
    assert data["question_pagination"] == 1
    assert data["is_template"] is False
    assert data["template_id"] == sample_test.id
    assert data["created_by_id"] == arvind.id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "test_question_static" in data
    assert len(data["tags"]) == 0
    assert len(data["test_question_static"]) == 0
    assert len(data["states"]) == 0

    test_tag_link = db.exec(
        select(TestTagLink).where(TestTagLink.test_id == data["id"])
    ).all()

    assert test_tag_link == []

    test_question_link = db.exec(
        select(TestQuestionStaticLink).where(
            TestQuestionStaticLink.test_id == data["id"]
        )
    ).all()

    assert test_question_link == []


def test_get_tests(client: TestClient, db: SessionDep):
    india = Country(name="India")
    db.add(india)
    db.commit()
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    goa = State(name="Goa", country_id=india.id)
    db.add(goa)
    db.commit()

    tag_english = Tag(name="English")
    db.add(tag_english)
    db.commit()

    question_three = Question(question="What is the capital of France?")
    db.add(question_three)
    db.commit()

    user = User(
        full_name="Test User",
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()

    test = Test(
        name="English Test",
        description="Test description",
        time_limit=30,
        marks=5,
        completion_message="Good job!",
        start_instructions="Read the questions carefully.",
        marks_level=None,
        link="test_link",
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

    test_tag_link = TestTagLink(test_id=test.id, tag_id=tag_english.id)
    db.add(test_tag_link)

    test_question_link = TestQuestionStaticLink(
        test_id=test.id, question_id=question_three.id
    )
    db.add(test_question_link)

    test_state_link = TestStateLocationLink(test_id=test.id, state_id=punjab.id)
    db.add(test_state_link)

    db.commit()

    response = client.get(f"{settings.API_V1_STR}/test/")
    data = response.json()

    assert response.status_code == 200
    assert len(data) > 0

    test_data = data[0]
    assert test_data["name"] == "English Test"
    assert test_data["description"] == "Test description"
    assert test_data["time_limit"] == 30
    assert test_data["marks"] == 5
    assert test_data["completion_message"] == "Good job!"
    assert test_data["start_instructions"] == "Read the questions carefully."
    assert test_data["marks_level"] is None
    assert test_data["link"] == "test_link"
    assert test_data["no_of_attempts"] == 1
    assert test_data["shuffle"] is False
    assert test_data["random_questions"] is False
    assert test_data["no_of_questions"] == 1
    assert test_data["question_pagination"] == 1
    assert test_data["is_template"] is False
    assert test_data["created_by_id"] == user.id
    assert "id" in test_data
    assert "created_date" in test_data
    assert "modified_date" in test_data
    assert "tags" in test_data
    assert "states" in test_data
    assert len(test_data["tags"]) == 1
    assert len(test_data["states"]) == 1
    assert test_data["tags"][0] == tag_english.id


def test_get_test_by_id(client: TestClient, db: SessionDep):
    india = Country(name="India")
    db.add(india)
    db.commit()
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    db.commit()

    tag_english = Tag(name="English")
    db.add(tag_english)
    db.commit()

    question_three = Question(question="What is the capital of France?")
    db.add(question_three)
    db.commit()

    user = User(
        full_name="Test User",
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()

    test = Test(
        name="English Test",
        description="Test description",
        time_limit=30,
        marks=5,
        completion_message="Good job!",
        start_instructions="Read the questions carefully.",
        marks_level=None,
        link="test_link",
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

    test_tag_link = TestTagLink(test_id=test.id, tag_id=tag_english.id)
    db.add(test_tag_link)
    db.commit()

    test_question_link = TestQuestionStaticLink(
        test_id=test.id, question_id=question_three.id
    )
    db.add(test_question_link)
    db.commit()

    test_state_link = TestStateLocationLink(test_id=test.id, state_id=punjab.id)
    db.add(test_state_link)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/test/{test.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "English Test"
    assert data["description"] == "Test description"
    assert data["time_limit"] == 30
    assert data["marks"] == 5
    assert data["completion_message"] == "Good job!"
    assert data["start_instructions"] == "Read the questions carefully."
    assert data["marks_level"] is None
    assert data["link"] == "test_link"
    assert data["no_of_attempts"] == 1
    assert data["shuffle"] is False
    assert data["random_questions"] is False
    assert data["no_of_questions"] == 1
    assert data["question_pagination"] == 1
    assert data["is_template"] is False
    assert data["created_by_id"] == user.id
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert "tags" in data
    assert "states" in data
    assert len(data["tags"]) == 1
    assert len(data["states"]) == 1
    assert data["tags"][0] == tag_english.id
    assert data["states"][0] == punjab.id


def test_update_test(client: TestClient, db: SessionDep):
    india = Country(name="India")
    db.add(india)
    db.commit()
    punjab = State(name="Punjab", country_id=india.id)
    db.add(punjab)
    maharashtra = State(name="Maharashtra", country_id=india.id)
    db.add(maharashtra)
    db.commit()

    tag_english = Tag(name="English")
    db.add(tag_english)
    db.commit()
    tag_hindi = Tag(name="Hindi")
    db.add(tag_hindi)
    db.commit()
    tag_marathi = Tag(name="Marathi")
    db.add(tag_marathi)
    db.commit()
    tag_gujarati = Tag(name="Gujurathi")
    db.add(tag_gujarati)
    db.commit()
    question_three = Question(question="What is the capital of France?")
    db.add(question_three)
    db.commit()

    user = User(
        full_name="Test User",
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()
    test = Test(
        name="English Test",
        description="Test description",
        time_limit=30,
        marks=5,
        completion_message="Good job!",
        start_instructions="Read the questions carefully.",
        marks_level=None,
        link="test_link",
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

    test_tag_link = TestTagLink(test_id=test.id, tag_id=tag_english.id)
    db.add(test_tag_link)
    db.commit()

    test_tag_link = TestTagLink(test_id=test.id, tag_id=tag_marathi.id)
    db.add(test_tag_link)
    db.commit()

    test_question_link = TestQuestionStaticLink(
        test_id=test.id, question_id=question_three.id
    )
    db.add(test_question_link)
    db.commit()

    test_state_link = TestStateLocationLink(test_id=test.id, state_id=punjab.id)
    db.add(test_state_link)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/test/{test.id}",
        json={
            "name": "Updated English Test",
            "description": "Updated description",
            "start_time": None,
            "end_time": None,
            "time_limit": 120,
            "marks_level": "test",
            "marks": 100,
            "completion_message": "Congratulations! You have completed the test.",
            "start_instructions": "Please read all questions carefully",
            "link": "http://example.com/test-link",
            "no_of_attempts": 3,
            "shuffle": True,
            "random_questions": True,
            "no_of_questions": 50,
            "question_pagination": 1,
            "is_template": False,
            "template_id": None,
            "created_by_id": user.id,
            "tags": [tag_hindi.id, tag_gujarati.id],
            "test_question_static": [question_three.id],
            "states": [punjab.id, maharashtra.id],
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == test.id
    assert data["name"] == "Updated English Test"
    assert data["name"] != "English Test"
    assert data["description"] == "Updated description"
    assert data["start_time"] is None
    assert data["end_time"] is None
    assert data["time_limit"] == 120
    assert data["marks_level"] == "test"
    assert data["marks"] == 100
    assert data["completion_message"] == "Congratulations! You have completed the test."
    assert data["start_instructions"] == "Please read all questions carefully"
    assert data["link"] == "http://example.com/test-link"
    assert data["no_of_attempts"] == 3
    assert data["shuffle"] is True
    assert data["random_questions"] is True
    assert data["no_of_questions"] == 50
    assert data["question_pagination"] == 1
    assert data["is_template"] is False
    assert data["template_id"] is None
    assert data["created_by_id"] == user.id
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
    assert data["tags"] == [tag_hindi.id, tag_gujarati.id]

    assert "test_question_static" in data
    assert len(data["test_question_static"]) == 1
    assert data["test_question_static"][0] == question_three.id

    assert "states" in data
    assert len(data["states"]) == 2
    assert data["states"] == [punjab.id, maharashtra.id]
