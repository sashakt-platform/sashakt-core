from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import Organization, TagType, User

from ...utils.utils import random_email, random_lower_string


def setup_user_organization(db: SessionDep) -> list[User, Organization]:
    user = User(
        email=random_email(),
        hashed_password=random_lower_string(),
        full_name=random_lower_string(),
    )
    db.add(user)
    db.commit()
    organization = Organization(name=random_lower_string())
    db.add(organization)
    db.commit()

    return user, organization


def test_create_tagtype(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)

    print("User--->", user)
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization.id,
        "created_by_id": user.id,
    }

    response = client.post(f"{settings.API_V1_STR}/tagtype/", json=data)
    response_data = response.json()
    print("response_data--->", response_data)
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["organization_id"] == data["organization_id"]
    assert response_data["created_by_id"] == data["created_by_id"]
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_get_tagtype(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(tagtype)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/tagtype/")
    response_data = response.json()
    print("response_data--->", response_data)
    assert response.status_code == 200
    assert len(response_data) == 2
    assert response_data[1]["name"] == tagtype.name
    assert response_data[1]["description"] == tagtype.description
    assert response_data[1]["organization_id"] == tagtype.organization_id
    assert response_data[1]["created_by_id"] == tagtype.created_by_id
    assert response_data[1]["is_deleted"] is False
    assert response_data[1]["is_active"] is None
    assert "created_date" in response_data[0]
    assert "modified_date" in response_data[0]


def test_get_tagtype_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(tagtype)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/tagtype/{tagtype.id}")
    response_data = response.json()
    print("response_data--->", response_data)
    assert response.status_code == 200
    assert response_data["name"] == tagtype.name
    assert response_data["description"] == tagtype.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == tagtype.created_by_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_update_tagtype_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    user_b, organization_b = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(tagtype)
    db.commit()
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization.id,
        "created_by_id": user.id,
    }

    data_b = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization_b.id,
        "created_by_id": user_b.id,
    }
    response = client.put(f"{settings.API_V1_STR}/tagtype/{tagtype.id}", json=data)
    response_data = response.json()
    print("response_data--->", response_data)
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == tagtype.created_by_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data

    response = client.put(f"{settings.API_V1_STR}/tagtype/{tagtype.id}", json=data_b)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data_b["name"]
    assert response_data["description"] == data_b["description"]
    assert response_data["organization_id"] == data_b["organization_id"]
    assert response_data["created_by_id"] == data_b["created_by_id"]
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_visibility_tagtype_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(tagtype)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}", params={"is_active": True}
    )
    response_data = response.json()
    print("Tag typee--->", response_data)
    assert response.status_code == 200
    assert response_data["is_active"] is True
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["name"] == tagtype.name
    assert response_data["description"] == tagtype.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == tagtype.created_by_id
    response = client.patch(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}", json={"is_active": False}
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["is_active"] is False
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["name"] == tagtype.name
    assert response_data["description"] == tagtype.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == tagtype.created_by_id
