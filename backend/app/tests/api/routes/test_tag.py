# test_helpers.py
from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import Organization, Tag, TagType, User
from app.tests.utils.user import create_random_user

from ...utils.utils import get_user_data_from_me_route, random_lower_string


def setup_user_organization(
    db: SessionDep,
) -> tuple[User, Organization]:
    user = create_random_user(db)
    organization = Organization(name=random_lower_string())
    db.add(organization)
    db.commit()

    return user, organization


def test_create_tagtype(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_user_data_from_me_route(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json=data,
        headers=get_user_superadmin_token,
    )

    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["organization_id"] == data["organization_id"]
    assert response_data["created_by_id"] == user_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data

    data = {
        "name": random_lower_string(),
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/tagtype/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] is None
    assert response_data["organization_id"] == data["organization_id"]
    assert response_data["created_by_id"] == user_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_get_tagtype(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_user_data_from_me_route(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(tagtype)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/tagtype/",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    total_length = len(response_data) - 1
    assert any(item["name"] == tagtype.name for item in response_data)
    assert any(item["description"] == tagtype.description for item in response_data)
    assert any(
        item["organization_id"] == tagtype.organization_id for item in response_data
    )
    assert any(item["created_by_id"] == tagtype.created_by_id for item in response_data)
    assert any(item["is_deleted"] == tagtype.is_deleted for item in response_data)
    assert any(item["is_active"] == tagtype.is_active for item in response_data)
    assert "created_date" in response_data[total_length]
    assert "modified_date" in response_data[total_length]


def test_get_tagtype_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_user_data_from_me_route(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(tagtype)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        headers=get_user_superadmin_token,
    )
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


def test_update_tagtype_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_user_data_from_me_route(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)
    user_b, organization_b = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user_id,
    )
    db.add(tagtype)
    db.commit()
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization.id,
    }

    data_b = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization_b.id,
    }
    response = client.put(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data

    response = client.put(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        json=data_b,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data_b["name"]
    assert response_data["description"] == data_b["description"]
    assert response_data["organization_id"] == data_b["organization_id"]
    assert response_data["created_by_id"] == user_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is None
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_visibility_tagtype_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        params={"is_active": True},
        headers=get_user_superadmin_token,
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
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        json={"is_active": False},
        headers=get_user_superadmin_token,
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


def test_delete_tagtype_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)
    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(tagtype)
    db.commit()
    response = client.delete(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]
    response = client.get(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404


# Test cases for Tags


# Create a Tag


def test_create_tag(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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
    response = client.post(
        f"{settings.API_V1_STR}/tag/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["tag_type"]["name"] == tagtype.name
    assert response_data["tag_type"]["id"] == tagtype.id
    assert response_data["tag_type"]["description"] == tagtype.description
    assert response_data["tag_type"]["organization_id"] == tagtype.organization_id
    assert response_data["tag_type"]["created_by_id"] == tagtype.created_by_id
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    data = {
        "name": random_lower_string(),
        "tag_type_id": tagtype.id,
        "created_by_id": user_b.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/tag/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] is None

    assert response_data["tag_type"]["id"] == tagtype.id
    assert response_data["tag_type"]["description"] == tagtype.description
    assert response_data["tag_type"]["organization_id"] == tagtype.organization_id
    assert response_data["tag_type"]["created_by_id"] == tagtype.created_by_id

    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    response = client.delete(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        headers=get_user_superadmin_token,
    )

    response_data = response.json()

    assert response.status_code == 200
    assert "delete" in response_data["message"]

    response = client.post(
        f"{settings.API_V1_STR}/tag/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert "not found" in response_data["detail"]


def test_read_tag(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_user_data_from_me_route(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]
    response = client.get(
        f"{settings.API_V1_STR}/tag/",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200

    tagtype = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )

    db.add(tagtype)
    db.commit()

    tag = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype.id,
        created_by_id=user_id,
        organization_id=organization_id,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    db.flush()

    response = client.get(
        f"{settings.API_V1_STR}/tag/",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert any(item["name"] == tag.name for item in response_data)
    assert any(item["description"] == tag.description for item in response_data)
    assert any(item["tag_type"]["id"] == tag.tag_type.id for item in response_data)
    assert any(item["organization_id"] == tag.organization_id for item in response_data)
    assert any(item["created_by_id"] == tag.created_by_id for item in response_data)
    assert any(item["is_deleted"] == tag.is_deleted for item in response_data)

    assert all(item["created_date"] for item in response_data)
    assert all(item["modified_date"] for item in response_data)

    tagtype_2 = TagType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(tagtype_2)
    db.commit()
    tag_2 = Tag(
        name=random_lower_string(),
        description=random_lower_string(),
        tag_type_id=tagtype_2.id,
        created_by_id=user_id,
        organization_id=organization_id,
    )
    db.add(tag_2)
    db.commit()
    db.refresh(tag_2)
    db.flush()

    response = client.delete(
        f"{settings.API_V1_STR}/tagtype/{tagtype_2.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]
    response = client.get(
        f"{settings.API_V1_STR}/tag/",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert all(item["name"] != tag_2.name for item in response_data)
    assert all(item["description"] != tag_2.description for item in response_data)


def test_read_tag_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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

    response = client.get(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == tag.name
    assert response_data["description"] == tag.description
    assert response_data["tag_type"]["id"] == tag.tag_type.id
    assert response_data["tag_type"]["name"] == tag.tag_type.name
    assert response_data["tag_type"]["description"] == tag.tag_type.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    response = client.get(
        f"{settings.API_V1_STR}/tag/-1",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert response_data["detail"] == "Tag not found"

    response = client.delete(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]

    response = client.get(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert "not found" in response_data["detail"]


def test_update_tag_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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
    response = client.put(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        json=data_a,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data_a["name"]
    assert response_data["description"] == data_a["description"]
    assert response_data["tag_type"]["id"] == data_a["tag_type_id"]
    assert response_data["tag_type"]["name"] == tagtype.name
    assert response_data["tag_type"]["description"] == tagtype.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    response = client.put(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        json=data_b,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data_b["name"]
    assert response_data["description"] == data_b["description"]
    assert response_data["tag_type"]["id"] == data_b["tag_type_id"]
    assert response_data["organization_id"] == tagtype.organization_id


def test_visibility_tag_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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
        f"{settings.API_V1_STR}/tag/{tag.id}",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["is_active"] is True
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["name"] == tag.name
    assert response_data["description"] == tag.description
    assert response_data["tag_type"]["id"] == tag.tag_type.id
    assert response_data["tag_type"]["name"] == tag.tag_type.name
    assert response_data["tag_type"]["description"] == tag.tag_type.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id

    response = client.patch(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        json={"is_active": False},
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["is_active"] is False
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["name"] == tag.name
    assert response_data["description"] == tag.description
    assert response_data["tag_type"]["id"] == tag.tag_type.id
    assert response_data["tag_type"]["name"] == tag.tag_type.name
    assert response_data["tag_type"]["description"] == tag.tag_type.description
    assert response_data["organization_id"] == tagtype.organization_id
    assert response_data["created_by_id"] == user_b.id

    response = client.patch(
        f"{settings.API_V1_STR}/tag/-1",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert "not found" in response_data["detail"]

    response = client.delete(
        f"{settings.API_V1_STR}/tagtype/{tagtype.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]

    response = client.patch(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        json={"is_active": False},
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert "not found" in response_data["detail"]


def test_delete_tag_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
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

    response = client.get(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "id" in response_data

    response = client.delete(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "delete" in response_data["message"]
    response = client.get(
        f"{settings.API_V1_STR}/tag/{tag.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert response_data["detail"] == "Tag not found"
