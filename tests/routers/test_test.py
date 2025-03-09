from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.tag import Tag
from app.models.user import User


def test_create_test(client: TestClient, session: Session):
    tag_hindi = Tag(name="Hindi")
    tag_marathi = Tag(name="Marathi")
    session.add(tag_hindi)
    session.add(tag_marathi)
    session.commit()

    arvind = User(name="Arvind S")
    session.add(arvind)
    session.commit()

    print("tag_hindi-->", tag_hindi.id)
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
        },
    )
    data = response.json()
    print("Data is --->", data)
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
