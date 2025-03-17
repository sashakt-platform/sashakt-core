from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.candidate import Candidate
from app.models.user import User

from ...utils.utils import random_email, random_lower_string


def test_create_candidate(client: TestClient, db: SessionDep) -> None:
    user = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/candidate/",
        json={"user_id": user.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data
    assert data["is_active"] is None
    assert data["user_id"] == user.id

    response = client.post(
        f"{settings.API_V1_STR}/candidate/",
        json={},
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data


def test_read_candidate(client: TestClient, db: SessionDep) -> None:
    response = client.get(f"{settings.API_V1_STR}/candidate/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    user = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add(user)
    db.commit()

    candidate = Candidate(user_id=user.id)
    db.add(candidate)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/candidate")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    data[0]["user_id"] = user.id

    candidate = Candidate()
    db.add(candidate)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/candidate")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[1]["user_id"] is None


def test_read_candidate_by_id(client: TestClient, db: SessionDep) -> None:
    user_a = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    user_b = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add_all([user_a, user_b])
    db.commit()

    candidate_a = Candidate(user_id=user_a.id)
    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_a, candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/candidate/{candidate_aa.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["user_id"] == user_a.id
    assert data["id"] == candidate_aa.id
    assert data["created_date"] == candidate_aa.created_date.isoformat()
    assert data["modified_date"] == candidate_aa.modified_date.isoformat()
    assert data["is_active"] is None
    assert data["is_deleted"] is False

    response = client.get(f"{settings.API_V1_STR}/candidate/{candidate_b.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["user_id"] == user_b.id
    assert data["id"] == candidate_b.id
    assert data["created_date"] == candidate_b.created_date.isoformat()
    assert data["modified_date"] == candidate_b.modified_date.isoformat()
    assert data["is_active"] is None
    assert data["is_deleted"] is False

    response = client.get(f"{settings.API_V1_STR}/candidate/{candidate_c.id}")
    data = response.json()

    assert response.status_code == 200
    assert data["user_id"] is None
    assert data["id"] == candidate_c.id
    assert data["created_date"] == candidate_c.created_date.isoformat()
    assert data["modified_date"] == candidate_c.modified_date.isoformat()
    assert data["is_active"] is None
    assert data["is_deleted"] is False


def test_update_candidate(client: TestClient, db: SessionDep) -> None:
    user_a = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    user_b = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add_all([user_a, user_b])
    db.commit()

    candidate_a = Candidate(user_id=user_a.id)
    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_a, candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        json={"user_id": user_b.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["user_id"] == user_b.id

    response = client.put(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        json={"user_id": None},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["user_id"] is None

    response = client.put(
        f"{settings.API_V1_STR}/candidate/{candidate_c.id}",
        json={"user_id": user_a.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_c.id
    assert data["user_id"] == user_a.id


def test_visibility_candidate(client: TestClient, db: SessionDep) -> None:
    user_a = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    user_b = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add_all([user_a, user_b])
    db.commit()

    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.patch(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}", params={"is_active": True}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["is_active"] is True
    assert data["is_active"] is not False and not None

    response = client.patch(
        f"{settings.API_V1_STR}/candidate/{candidate_aa.id}",
        params={"is_active": False},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_aa.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None

    response = client.patch(
        f"{settings.API_V1_STR}/candidate/{candidate_c.id}",
        params={"is_active": False},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == candidate_c.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None


def test_delete_candidate(client: TestClient, db: SessionDep) -> None:
    user_a = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    user_b = User(
        full_name=random_lower_string(),
        email=random_email(),
        hashed_password=random_lower_string(),
    )
    db.add_all([user_a, user_b])
    db.commit()

    candidate_aa = Candidate(user_id=user_a.id)
    candidate_b = Candidate(user_id=user_b.id)
    candidate_c = Candidate()

    db.add_all([candidate_aa, candidate_b, candidate_c])
    db.commit()

    response = client.delete(f"{settings.API_V1_STR}/candidate/{candidate_aa.id}")
    data = response.json()
    assert response.status_code == 200

    assert data["is_deleted"] is True
    assert data["id"] == candidate_aa.id

    response = client.get(f"{settings.API_V1_STR}/candidate/{candidate_aa.id}")
    data = response.json()

    assert response.status_code == 404
    assert "id" not in data
