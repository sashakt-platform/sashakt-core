from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.question import Question
from app.models.tag import Tag
from app.models.test import Test, TestQuestionStaticLink, TestTagLink
from app.models.user import User


def test_create_test(client: TestClient, session: Session):
    tag_hindi = Tag(name="Hindi")
    tag_marathi = Tag(name="Marathi")
    session.add(tag_hindi)
    session.add(tag_marathi)
    session.commit()

    question_one = Question(question="What is the size of Sun")
    question_two = Question(question="What is the speed of light")
    session.add(question_one)
    session.add(question_two)
    session.commit()

    arvind = User(name="Arvind S")
    session.add(arvind)
    session.commit()

    response = client.post(
        "/test/",
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

    test_tag_link = session.exec(
        select(TestTagLink).where(TestTagLink.test_id == data["id"])
    ).all()

    assert test_tag_link[0].tag_id == tag_hindi.id
    assert test_tag_link[1].tag_id == tag_marathi.id

    test_question_link = session.exec(
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
    session.add(sample_test)
    session.commit()

    marathi_test_name = "Marathi Test"
    marathi_test_description = "This is marathi Test"
    response = client.post(
        "/test/",
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
    assert len(data["tags"]) == 2
    assert data["tags"][0] == tag_hindi.id
    assert data["tags"][1] == tag_marathi.id

    test_tag_link = session.exec(
        select(TestTagLink).where(TestTagLink.test_id == data["id"])
    ).all()

    assert test_tag_link[0].tag_id == tag_hindi.id
    assert test_tag_link[1].tag_id == tag_marathi.id

    test_question_link = session.exec(
        select(TestQuestionStaticLink).where(
            TestQuestionStaticLink.test_id == data["id"]
        )
    ).all()

    assert test_question_link[0].question_id == question_one.id
    assert test_question_link[1].question_id == question_two.id

    response = client.post(
        "/test/",
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
    assert len(data["tags"]) == 0
    assert len(data["test_question_static"]) == 0

    test_tag_link = session.exec(
        select(TestTagLink).where(TestTagLink.test_id == data["id"])
    ).all()

    assert test_tag_link == []

    test_question_link = session.exec(
        select(TestQuestionStaticLink).where(
            TestQuestionStaticLink.test_id == data["id"]
        )
    ).all()

    assert test_question_link == []


def test_get_tests(client: TestClient, session: Session):
    tag_english = Tag(name="English")
    session.add(tag_english)
    session.commit()

    question_three = Question(question="What is the capital of France?")
    session.add(question_three)
    session.commit()

    user = User(name="Test User")
    session.add(user)
    session.commit()

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
    session.add(test)
    session.commit()

    test_tag_link = TestTagLink(test_id=test.id, tag_id=tag_english.id)
    session.add(test_tag_link)
    session.commit()

    test_question_link = TestQuestionStaticLink(
        test_id=test.id, question_id=question_three.id
    )
    session.add(test_question_link)
    session.commit()

    response = client.get("/test/")
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
    assert len(test_data["tags"]) == 1
    assert test_data["tags"][0] == tag_english.id


def test_get_test_by_id(client: TestClient, session: Session):
    tag_english = Tag(name="English")
    session.add(tag_english)
    session.commit()

    question_three = Question(question="What is the capital of France?")
    session.add(question_three)
    session.commit()

    user = User(name="Test User")
    session.add(user)
    session.commit()

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
    session.add(test)
    session.commit()

    test_tag_link = TestTagLink(test_id=test.id, tag_id=tag_english.id)
    session.add(test_tag_link)
    session.commit()

    test_question_link = TestQuestionStaticLink(
        test_id=test.id, question_id=question_three.id
    )
    session.add(test_question_link)
    session.commit()

    response = client.get(f"/test/{test.id}")
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
    assert len(data["tags"]) == 1
    assert data["tags"][0] == tag_english.id


# def test_update_test(client: TestClient, session: Session):
#     tag_english = Tag(name="English")
#     session.add(tag_english)
#     session.commit()
#     print("Tag--->1")
#     question_three = Question(question="What is the capital of France?")
#     session.add(question_three)
#     session.commit()

#     user = User(name="Test User")
#     session.add(user)
#     session.commit()
#     print("Tag--->2")
#     test = Test(
#         name="English Test",
#         description="Test description",
#         time_limit=30,
#         marks=5,
#         completion_message="Good job!",
#         start_instructions="Read the questions carefully.",
#         marks_level=None,
#         link="test_link",
#         no_of_attempts=1,
#         shuffle=False,
#         random_questions=False,
#         no_of_questions=1,
#         question_pagination=1,
#         is_template=False,
#         created_by_id=user.id,
#     )
#     session.add(test)
#     session.commit()
#     print("Tag--->3")
#     test_tag_link = TestTagLink(test_id=test.id,
# tag_id=tag_english.id)
#     session.add(test_tag_link)
#     session.commit()
#     print("Tag--->4")
#     test_question_link = TestQuestionStaticLink(
#         test_id=test.id, question_id=question_three.id
#     )
#     session.add(test_question_link)
#     session.commit()
#     print("Tag--->5")
#     response = client.put(f"/test/{test.id}")
#     response = client.put(
#         f"/test/{test.id}",
#         json={
#             "name": "Sample Test",
#             "description": "This is a sample test description.",
#             "start_time": None,
#             "end_time": None,
#             "time_limit": 120,
#             "marks_level": "test",
#             "marks": 100,
#             "completion_message": "Congratulations! You have completed the test.",
#             "start_instructions": "Please read all questions carefully",
#             "link": "http://example.com/test-link",
#             "no_of_attempts": 3,
#             "shuffle": True,
#             "random_questions": True,
#             "no_of_questions": 50,
#             "question_pagination": 1,
#             "is_template": False,
#             "template_id": None,
#             "created_by_id": 1,
#             "tags": [tag_english.id],
#             "test_question_static": [question_three.id],
#         },
#     )
#     print("Tag--->6")
#     data = response.json()
#     print("Tag--->6.5")
#     assert response.status_code == 200
#     assert data["name"] == "Updated English Test"
#     assert data["description"] == "Updated description"
#     assert data["time_limit"] == 45
#     assert data["marks"] == 10
#     assert data["completion_message"] == "Excellent job!"
#     assert data["start_instructions"] == "Please read the questions carefully."
#     assert data["marks_level"] is None
#     assert data["link"] == "updated_test_link"
#     assert data["no_of_attempts"] == 2
#     assert data["shuffle"] is True
#     assert data["random_questions"] is True
#     assert data["no_of_questions"] == 2
#     assert data["question_pagination"] == 1
#     assert data["is_template"] is False
#     assert data["created_by_id"] == user.id
#     assert "id" in data
#     assert "created_date" in data
#     assert "modified_date" in data
#     assert "tags" in data
#     assert len(data["tags"]) == 1
#     assert data["tags"][0] == tag_english.id
#     print("Tag--->7")
