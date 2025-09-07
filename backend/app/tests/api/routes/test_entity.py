from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.entity import Entity, EntityType
from app.tests.api.routes.test_tag import setup_user_organization
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import assert_paginated_response, random_lower_string


def test_create_entitytype(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/entitytype/",
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
    assert response_data["is_active"] is True
    assert "created_date" in response_data
    assert "modified_date" in response_data
    data = {
        "name": random_lower_string(),
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/entitytype/",
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
    assert response_data["is_active"] is True
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_prevent_duplicate_entitytype_creation(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)

    name = "school"
    data = {
        "name": name,
        "description": random_lower_string(),
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/entitytype/",
        json=data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == name
    assert response_data["organization_id"] == data["organization_id"]

    # Duplicate name in uppercase should fail
    data_upper = {
        "name": "SCHOOL",
        "organization_id": organization.id,
    }
    response_upper = client.post(
        f"{settings.API_V1_STR}/entitytype/",
        json=data_upper,
        headers=get_user_superadmin_token,
    )
    response_data_upper = response_upper.json()
    assert response_upper.status_code == 400
    assert (
        response_data_upper["detail"]
        == "EntityType with name 'SCHOOL' already exists in this organization."
    )

    # Duplicate name with extra spaces should also fail
    data_spaces = {
        "name": "   school  ",
        "organization_id": organization.id,
    }
    response_spaces = client.post(
        f"{settings.API_V1_STR}/entitytype/",
        json=data_spaces,
        headers=get_user_superadmin_token,
    )
    assert response_spaces.status_code == 400
    assert (
        response_spaces.json()["detail"]
        == "EntityType with name '   school  ' already exists in this organization."
    )

    # Creating a unique name should succeed
    unique_name = "college"
    data_unique = {
        "name": unique_name,
        "organization_id": organization.id,
        "description": random_lower_string(),
    }
    response_unique = client.post(
        f"{settings.API_V1_STR}/entitytype/",
        json=data_unique,
        headers=get_user_superadmin_token,
    )
    assert response_unique.status_code == 200
    response_data_unique = response_unique.json()
    assert response_data_unique["name"] == unique_name
    assert response_data_unique["description"] == data_unique["description"]
    assert response_data_unique["organization_id"] == organization.id
    assert response_data_unique["created_by_id"] == user_id


def test_get_entity_type(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    entity_type = EntityType(
        name="testentity",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(entity_type)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/entitytype/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    response_data = data["items"]
    assert_paginated_response(response)
    assert response.status_code == 200
    assert any(item["name"] == entity_type.name for item in response_data)
    assert any(item["description"] == entity_type.description for item in response_data)
    assert any(
        item["organization_id"] == entity_type.organization_id for item in response_data
    )
    assert any(
        item["created_by_id"] == entity_type.created_by_id for item in response_data
    )
    assert any(item["is_deleted"] == entity_type.is_deleted for item in response_data)
    assert any(item["is_active"] == entity_type.is_active for item in response_data)

    for name_query in ["Testentity", "TESTENTITY", " TeStEnTiTy"]:
        response = client.get(
            f"{settings.API_V1_STR}/entitytype/?name={name_query}",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert any(item["name"].lower() == "testentity" for item in data["items"])

    entity_type = EntityType(
        name="testentityAnother",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(entity_type)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/entitytype/?name=TESTENTITY",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


def test_get_entity_type_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(entity_type)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/entitytype/{entity_type.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == entity_type.name
    assert response_data["description"] == entity_type.description
    assert response_data["organization_id"] == entity_type.organization_id
    assert response_data["created_by_id"] == entity_type.created_by_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is True
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_update_entitytype_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)
    user_b, organization_b = setup_user_organization(db)

    entitytype = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user_id,
    )
    db.add(entitytype)
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

    # First update
    response = client.put(
        f"{settings.API_V1_STR}/entitytype/{entitytype.id}",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["organization_id"] == entitytype.organization_id
    assert response_data["created_by_id"] == user_id
    assert response_data["is_deleted"] is False
    assert response_data["is_active"] is True
    assert "created_date" in response_data
    assert "modified_date" in response_data

    # Second update
    response = client.put(
        f"{settings.API_V1_STR}/entitytype/{entitytype.id}",
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
    assert response_data["is_active"] is True
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_update_entitytype_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "organization_id": 1,
    }

    response = client.put(
        f"{settings.API_V1_STR}/entitytype/-90",
        json=data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 404
    response_data = response.json()
    assert response_data["detail"] == "EntityType not found"


def test_delete_entitytype_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)
    db.commit()

    # delete API call
    response = client.delete(
        f"{settings.API_V1_STR}/entitytype/{entity_type.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "deleted successfully" in response_data["message"]

    # confirm entity_type is deleted (should return 404)
    response = client.get(
        f"{settings.API_V1_STR}/entitytype/{entity_type.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert response_data["detail"] == "EntityType not found"


def test_delete_entitytype_with_associated_entities(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    entity = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    response = client.delete(
        f"{settings.API_V1_STR}/entitytype/{entity_type.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 400
    assert (
        "Cannot delete EntityType as it has associated Entities"
        in response_data["detail"]
    )


def test_delete_entitytype_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/entitytype/-90",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "EntityType not found"


def test_create_entity(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    # Create entity with description
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": entity_type.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["entity_type"]["name"] == entity_type.name
    assert response_data["entity_type"]["id"] == entity_type.id
    assert response_data["entity_type"]["description"] == entity_type.description
    assert (
        response_data["entity_type"]["organization_id"] == entity_type.organization_id
    )
    assert response_data["entity_type"]["created_by_id"] == entity_type.created_by_id
    assert response_data["organization_id"] == entity_type.organization_id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    data = {
        "name": random_lower_string(),
        "entity_type_id": entity_type.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    entity_id = response_data["id"]
    assert response_data["name"] == data["name"]
    assert response_data["description"] is None

    assert response_data["entity_type"]["id"] == entity_type.id
    assert response_data["entity_type"]["description"] == entity_type.description
    assert (
        response_data["entity_type"]["organization_id"] == entity_type.organization_id
    )
    assert response_data["entity_type"]["created_by_id"] == entity_type.created_by_id

    assert response_data["organization_id"] == entity_type.organization_id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    update_payload = {"name": data["name"], "entity_type_id": None}
    response = client.put(
        f"{settings.API_V1_STR}/entity/{entity_id}",
        json=update_payload,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    response_data = response.json()
    assert "EntityType is required for an entity." in response_data["detail"]


def test_create_entity_missing_entitytype(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)
    user_b = create_random_user(db)

    invalid_data = {
        "name": random_lower_string(),
        "created_by_id": user_b.id,
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=invalid_data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 400
    assert "EntityType is required for creating an entity." in response_data["detail"]


def test_create_entity_with_invalid_entitytype(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)
    user_b = create_random_user(db)

    invalid_data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": -90,
        "created_by_id": user_b.id,
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=invalid_data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "EntityType not found"


def test_prevent_duplicate_entity_creation(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    entitytype = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entitytype)
    db.commit()
    db.refresh(entitytype)

    entitytype2 = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entitytype2)
    db.commit()
    db.refresh(entitytype2)

    name = random_lower_string()
    data = {
        "name": name,
        "description": random_lower_string(),
        "entity_type_id": entitytype.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["entity_type"]["name"] == entitytype.name
    assert response_data["entity_type"]["id"] == entitytype.id

    response1 = client.post(
        f"{settings.API_V1_STR}/entity/", json=data, headers=get_user_superadmin_token
    )
    assert response1.status_code == 400
    assert "already exists" in response1.json()["detail"]

    data2 = {
        "name": name,
        "entity_type_id": entitytype2.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=data2,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] is None
    assert response_data["entity_type"]["id"] == entitytype2.id

    response = client.post(
        f"{settings.API_V1_STR}/entity/", json=data2, headers=get_user_superadmin_token
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_entities_base_case(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    entity = Entity(
        name="EntityZ",
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(entity)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/entity/?name=entity", headers=get_user_superadmin_token
    )
    assert response.status_code == 200
    base_response = response.json()

    assert "items" in base_response
    assert base_response["total"] >= 1
    assert base_response["page"] == 1
    assert base_response["size"] > 0

    assert any(
        item["id"] == entity.id
        and item["name"] == "EntityZ"
        and item["organization_id"] == organization_id
        and item["entity_type"]["id"] == entity_type.id
        and item["entity_type"]["name"] == entity_type.name
        and item["entity_type"]["organization_id"] == organization_id
        and item["is_deleted"] is False
        and "created_date" in item
        and "modified_date" in item
        for item in base_response["items"]
    )
    response = client.get(
        f"{settings.API_V1_STR}/entity/?name=entity", headers=get_user_superadmin_token
    )
    assert response.status_code == 200
    filter_response = response.json()

    assert "items" in filter_response
    assert len(filter_response["items"]) == 1


def test_read_entity_with_sort(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    organization_id = user_data["organization_id"]
    user = create_random_user(db, user_data["organization_id"])

    # Create EntityTypes
    entity_type1 = EntityType(
        name="AlphaEntity",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user.id,
    )
    entity_type2 = EntityType(
        name="BetaEntity",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user.id,
    )
    entity_type3 = EntityType(
        name="GammaEntity",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user.id,
    )
    db.add_all([entity_type1, entity_type2, entity_type3])
    db.commit()

    # Create Entities
    entity1 = Entity(
        name="Python",
        description=random_lower_string(),
        entity_type_id=entity_type1.id,
        created_by_id=user.id,
        organization_id=organization_id,
    )
    entity2 = Entity(
        name="Django",
        description=random_lower_string(),
        entity_type_id=entity_type2.id,
        created_by_id=user.id,
        organization_id=organization_id,
    )
    entity3 = Entity(
        name="C++",
        description=random_lower_string(),
        entity_type_id=entity_type1.id,
        created_by_id=user.id,
        organization_id=organization_id,
    )
    entity4 = Entity(
        name="Git",
        description=random_lower_string(),
        entity_type_id=entity_type3.id,
        created_by_id=user.id,
        organization_id=organization_id,
    )
    db.add_all([entity1, entity2, entity3, entity4])
    db.commit()

    expected = ["C++", "Django", "Git", "Python"]
    expected_entity_types = ["AlphaEntity", "BetaEntity", "GammaEntity"]

    # Sort by entity name ASC
    response = client.get(
        f"{settings.API_V1_STR}/entity/?order_by=name",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    response_names = [
        entity["name"] for entity in data["items"] if entity["name"] in expected
    ]
    assert response_names == sorted(expected)

    # Sort by entity name DESC
    response = client.get(
        f"{settings.API_V1_STR}/entity/?order_by=-name",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    response_names = [
        entity["name"] for entity in data["items"] if entity["name"] in expected
    ]
    assert response_names == sorted(expected, reverse=True)

    # Sort by entity_type_name ASC
    response = client.get(
        f"{settings.API_V1_STR}/entity/?order_by=entity_type_name",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    entity_types = [
        entity["entity_type"]["name"]
        for entity in data["items"]
        if entity["entity_type"] is not None
        and entity["entity_type"]["name"] in expected_entity_types
    ]
    assert set(entity_types) == set(expected_entity_types)
    assert entity_types == sorted(entity_types)

    # Sort by entity_type_name DESC
    response = client.get(
        f"{settings.API_V1_STR}/entity/?order_by=-entity_type_name",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    entity_types_desc = [
        entity["entity_type"]["name"]
        for entity in data["items"]
        if entity["entity_type"] is not None
        and entity["entity_type"]["name"] in expected_entity_types
    ]
    assert set(entity_types_desc) == set(expected_entity_types)
    assert entity_types_desc == sorted(entity_types_desc, reverse=True)

    # Sort by both entity_type_name + entity name
    response = client.get(
        f"{settings.API_V1_STR}/entity/?order_by=entity_type_name&order_by=name",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data_both = response.json()
    filtered_both = [
        (entity["entity_type"]["name"], entity["name"])
        for entity in data_both["items"]
        if entity["entity_type"]
        and entity["entity_type"]["name"]
        in ["AlphaEntity", "BetaEntity", "GammaEntity"]
    ]
    assert filtered_both == sorted(filtered_both)


def test_read_entity_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)

    # Create entity type
    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=user_data["organization_id"],
        created_by_id=user_data["id"],
    )
    user_b = create_random_user(db, user_data["organization_id"])
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    # Create entity
    entity = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_b.id,
        organization_id=user_b.organization_id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    # GET entity by id
    response = client.get(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == entity.name
    assert response_data["description"] == entity.description
    assert response_data["entity_type"]["id"] == entity.entity_type.id
    assert response_data["entity_type"]["name"] == entity.entity_type.name
    assert response_data["entity_type"]["description"] == entity.entity_type.description
    assert response_data["organization_id"] == entity_type.organization_id
    assert response_data["created_by_id"] == user_b.id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    # GET entity by non-existent id
    response = client.get(
        f"{settings.API_V1_STR}/entity/-1",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert response_data["detail"] == "Entity not found"


def test_update_entity_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    # Create entity type
    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    user_b = create_random_user(db)
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    # Create entity
    entity = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_b.id,
        organization_id=organization.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    update_data_a = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": entity_type.id,
        "organization_id": organization.id,
    }
    response = client.put(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        json=update_data_a,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == update_data_a["name"]
    assert response_data["description"] == update_data_a["description"]
    assert response_data["entity_type"]["id"] == update_data_a["entity_type_id"]
    assert response_data["entity_type"]["name"] == entity_type.name
    assert response_data["entity_type"]["description"] == entity_type.description
    assert response_data["organization_id"] == organization.id
    assert response_data["is_deleted"] is False
    assert "created_date" in response_data
    assert "modified_date" in response_data

    update_data_b = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": entity_type.id,
        "organization_id": organization.id,
    }
    response = client.put(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        json=update_data_b,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == update_data_b["name"]
    assert response_data["description"] == update_data_b["description"]
    assert response_data["entity_type"]["id"] == update_data_b["entity_type_id"]
    assert response_data["organization_id"] == organization.id


def test_update_entity_with_invalid_entitytype(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    # Create a valid entity type
    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    # Create a valid entity
    entity = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user.id,
        organization_id=organization.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    # Try to update entity with invalid entity_type_id (-90)
    update_data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": -90,  # invalid entity type
        "created_by_id": user.id,
        "organization_id": organization.id,
    }

    response = client.put(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        json=update_data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "EntityType not found"


def test_update_entity_not_found(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    # Prepare payload for update
    update_data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "created_by_id": user.id,
        "organization_id": organization.id,
    }

    # Try updating non-existent entity with id -90
    response = client.put(
        f"{settings.API_V1_STR}/entity/-90",
        json=update_data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "Entity not found"


def test_delete_entity_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    # Create entity type
    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    # Create entity
    entity = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user.id,
        organization_id=organization.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    response = client.get(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["id"] == entity.id

    # Delete entity
    response = client.delete(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert "deleted" in response_data["message"].lower()

    response = client.get(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 404
    assert response_data["detail"] == "Entity not found"


def test_delete_entity_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/entity/-90",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "Entity not found"
