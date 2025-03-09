from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.question import Question
from app.models.tag import Tag
from app.models.test import TestQuestionStaticLink, TestTagLink
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
            "test_create": {
                "name": "ABCC",
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
            },
            "tag_ids": [tag_hindi.id, tag_marathi.id],
            "question_ids": [question_one.id, question_two.id],
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "ABCC"
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
