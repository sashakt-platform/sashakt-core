from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import Organization, Tag, TagType, User
from app.tests.utils.user import create_random_user

from ...utils.utils import random_lower_string


def setup_user_organization(db: SessionDep) -> tuple[User, Organization]:
    user = create_random_user(db)
    organization = Organization(name=random_lower_string())
    db.add(organization)
    db.commit()

    return user, organization


def test_create_tagtype(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization.id,
        "created_by_id": user.id,
    }

    response = client.post(f"{settings.API_V1_STR}/tagtype/", json=data)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["organization_id"] == data["organization_id"]
    assert response_data["created_by_id"] == data["created_by_id"]
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data

    data = {
        "name": random_lower_string(),
        "organization_id": organization.id,
        "created_by_id": user.id,
    }

    response = client.post(f"{settings.API_V1_STR}/tagtype/", json=data)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] is None
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
    assert response.status_code == 200
    total_length = len(response_data) - 1
    assert response_data[total_length]["name"] == tagtype.name
    assert response_data[total_length]["description"] == tagtype.description
    assert response_data[total_length]["organization_id"] == tagtype.organization_id
    assert response_data[total_length]["created_by_id"] == tagtype.created_by_id
    assert response_data[total_length]["is_deleted"] is False
    assert response_data[total_length]["is_active"] is None
    assert "created_date" in response_data[total_length]
    assert "modified_date" in response_data[total_length]


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


def test_delete_tagtype_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(tagtype)
    db.commit()
    response = client.delete(f"{settings.API_V1_STR}/tagtype/{tagtype.id}")
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]
    response = client.get(f"{settings.API_V1_STR}/tagtype/{tagtype.id}")
    response_data = response.json()
    assert response.status_code == 404


# Test cases for Tags


# Create a Tag


def test_create_tag(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)

    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(tagtype)
    db.commit()
    db.refresh(tagtype)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "tag_type_id": tagtype.id,
        "created_by_id": user_b.id,
    }
    response = client.post(f"{settings.API_V1_STR}/tag/", json=data)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["tag_type_id"] == data["tag_type_id"]
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    data = {
        "name": random_lower_string(),
        "tag_type_id": tagtype.id,
        "created_by_id": user_b.id,
    }
    response = client.post(f"{settings.API_V1_STR}/tag/", json=data)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] is None
    assert response_data["tag_type_id"] == data["tag_type_id"]
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_read_tag(client: TestClient, db: SessionDep) -> None:
    response = client.get(f"{settings.API_V1_STR}/tag/")
    response_data = response.json()
    assert response.status_code == 200

    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(tagtype)
    db.commit()

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype.id,
        created_by_id=user_b.id,
        organization_id=organization.id,
    )
    db.add(tag)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/tag/")
    response_data = response.json()
    assert response.status_code == 200
    total_length = len(response_data) - 1
    assert response_data[total_length]["name"] == tag.name
    assert response_data[total_length]["description"] == tag.description
    assert response_data[total_length]["tag_type_id"] == tag.tag_type_id
    assert response_data[total_length]["organization_id"] == tagtype.organization_id
    assert response_data[total_length]["created_by_id"] == user_b.id
    assert response_data[total_length]["is_deleted"] is False
    assert "created_date" in response_data[1]
    assert "modified_date" in response_data[1]


def test_read_tag_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(tagtype)
    db.commit()

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype.id,
        created_by_id=user_b.id,
        organization_id=organization.id,
    )
    db.add(tag)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/tag/{tag.id}")
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == tag.name
    assert response_data["description"] == tag.description
    assert response_data["tag_type_id"] == tag.tag_type_id
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_update_tag_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(tagtype)
    db.commit()

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype.id,
        created_by_id=user_b.id,
        organization_id=organization.id,
    )
    db.add(tag)
    db.commit()

    data_a = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "tag_type_id": tagtype.id,
        "created_by_id": user_b.id,
        "organization_id": organization.id,
    }

    data_b = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "tag_type_id": tagtype.id,
        "created_by_id": user.id,
        "organization_id": organization.id,
    }
    response = client.put(f"{settings.API_V1_STR}/tag/{tag.id}", json=data_a)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data_a["name"]
    assert response_data["description"] == data_a["description"]
    assert response_data["tag_type_id"] == data_a["tag_type_id"]
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    response = client.put(f"{settings.API_V1_STR}/tag/{tag.id}", json=data_b)
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data_b["name"]
    assert response_data["description"] == data_b["description"]
    assert response_data["tag_type_id"] == data_b["tag_type_id"]
    assert response_data["organization_id"] == tagtype.organization_id


def test_visibility_tag_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(tagtype)
    db.commit()

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype.id,
        created_by_id=user_b.id,
        organization_id=organization.id,
    )
    db.add(tag)
    db.commit()

    assert tag.is_active is None

    response = client.patch(
        f"{settings.API_V1_STR}/tag/{tag.id}", params={"is_active": True}
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["is_active"] is True
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["name"] == tag.name
    assert response_data["description"] == tag.description
    assert response_data["tag_type_id"] == tag.tag_type_id
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id

    response = client.patch(
        f"{settings.API_V1_STR}/tag/{tag.id}", json={"is_active": False}
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["is_active"] is False
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["name"] == tag.name
    assert response_data["description"] == tag.description
    assert response_data["tag_type_id"] == tag.tag_type_id
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id


def test_delete_tag_by_id(client: TestClient, db: SessionDep) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(tagtype)
    db.commit()

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype.id,
        created_by_id=user_b.id,
        organization_id=organization.id,
    )
    db.add(tag)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/tag/{tag.id}")
    response_data = response.json()
    assert response.status_code == 200
    assert "id" in response_data

    response = client.delete(f"{settings.API_V1_STR}/tag/{tag.id}")
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]
    response = client.get(f"{settings.API_V1_STR}/tag/{tag.id}")
    response_data = response.json()
    assert response.status_code == 404
    assert response_data["detail"] == "Tag not found"
