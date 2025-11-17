import base64
import csv
import io
import os
import tempfile

from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.candidate import Candidate, CandidateTest
from app.models.entity import Entity, EntityType
from app.models.location import Block, Country, District, State
from app.models.test import Test
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


def test_create_entity_with_full_location(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user, organization = setup_user_organization(db)

    # Create EntityType
    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)

    # Create Country
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    db.refresh(india)

    # Create State
    state = State(name=random_lower_string(), country_id=india.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    # Create District
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    # Create Block
    block = Block(name=random_lower_string(), district_id=district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    db.refresh(entity_type)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": entity_type.id,
        "state_id": state.id,
        "district_id": district.id,
        "block_id": block.id,
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
    assert response_data["entity_type"]["id"] == entity_type.id
    assert response_data["entity_type"]["name"] == entity_type.name
    assert response_data["state"]["id"] == state.id
    assert response_data["state"]["name"] == state.name
    assert response_data["district"]["id"] == district.id
    assert response_data["district"]["name"] == district.name
    assert response_data["block"]["id"] == block.id
    assert response_data["block"]["name"] == block.name


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


def test_prevent_duplicate_entity_creation_with_location(
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

    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    db.refresh(india)

    state = State(name=random_lower_string(), country_id=india.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    block = Block(name=random_lower_string(), district_id=district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    name = random_lower_string()
    data = {
        "name": name,
        "description": random_lower_string(),
        "entity_type_id": entitytype.id,
        "state_id": state.id,
        "district_id": district.id,
        "block_id": block.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["entity_type"]["id"] == entitytype.id

    response1 = client.post(
        f"{settings.API_V1_STR}/entity/", json=data, headers=get_user_superadmin_token
    )
    assert response1.status_code == 400
    assert "already exists" in response1.json()["detail"]

    data2 = {
        "name": name,
        "entity_type_id": entitytype2.id,
        "state_id": state.id,
        "district_id": district.id,
        "block_id": block.id,
    }
    response2 = client.post(
        f"{settings.API_V1_STR}/entity/",
        json=data2,
        headers=get_user_superadmin_token,
    )
    response_data2 = response2.json()
    assert response2.status_code == 200
    assert response_data2["name"] == data2["name"]
    assert response_data2["entity_type"]["id"] == entitytype2.id

    response3 = client.post(
        f"{settings.API_V1_STR}/entity/", json=data2, headers=get_user_superadmin_token
    )
    assert response3.status_code == 400
    assert "already exists" in response3.json()["detail"]


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
        and item["entity_type"]["id"] == entity_type.id
        and item["entity_type"]["name"] == entity_type.name
        and item["entity_type"]["organization_id"] == organization_id
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


def test_get_entities(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    # Country
    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    db.refresh(country)

    # State
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    # District
    district = District(name=random_lower_string(), state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    # Block
    block = Block(name=random_lower_string(), district_id=district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    # EntityType
    entity_type = EntityType(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    # Entity with state, district, block
    entity = Entity(
        name="TestEntity",
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user_id,
        state_id=state.id,
        district_id=district.id,
        block_id=block.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    response = client.get(
        f"{settings.API_V1_STR}/entity/?name=test", headers=get_user_superadmin_token
    )
    assert response.status_code == 200
    data = response.json()

    items = data["items"]
    entity_resp = next((i for i in items if i["id"] == entity.id), None)
    assert entity_resp is not None
    assert entity_resp["name"] == "TestEntity"
    assert entity_resp["entity_type"]["id"] == entity_type.id
    assert entity_resp["district"]["id"] == district.id
    assert entity_resp["state"]["id"] == state.id
    assert entity_resp["block"]["id"] == block.id
    assert "created_date" in entity_resp
    assert "modified_date" in entity_resp


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
    )
    entity2 = Entity(
        name="Django",
        description=random_lower_string(),
        entity_type_id=entity_type2.id,
        created_by_id=user.id,
    )
    entity3 = Entity(
        name="C++",
        description=random_lower_string(),
        entity_type_id=entity_type1.id,
        created_by_id=user.id,
    )
    entity4 = Entity(
        name="Git",
        description=random_lower_string(),
        entity_type_id=entity_type3.id,
        created_by_id=user.id,
    )
    db.add_all([entity1, entity2, entity3, entity4])
    db.commit()

    expected = ["C++", "Django", "Git", "Python"]
    expected_entity_types = ["AlphaEntity", "BetaEntity", "GammaEntity"]

    # Sort by entity name ASC
    response = client.get(
        f"{settings.API_V1_STR}/entity/?sort_by=name&sort_order=asc",
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
        f"{settings.API_V1_STR}/entity/?sort_by=name&sort_order=desc",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    response_names = [
        entity["name"] for entity in data["items"] if entity["name"] in expected
    ]
    assert response_names == sorted(expected, reverse=True)

    # Sort by entity_type_name ASC
    response = client.get(
        f"{settings.API_V1_STR}/entity/?sort_by=entity_type_name&sort_order=asc",
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
        f"{settings.API_V1_STR}/entity/?sort_by=entity_type_name&sort_order=desc",
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
    assert response_data["created_by_id"] == user_b.id
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
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    update_data_a = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": entity_type.id,
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
    assert "created_date" in response_data
    assert "modified_date" in response_data

    update_data_b = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "entity_type_id": entity_type.id,
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


def test_delete_linked_entity_should_fail(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user = create_random_user(db)

    entity_type = EntityType(
        name=random_lower_string(),
        created_by_id=user.id,
        organization_id=user.organization_id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    entity = Entity(
        name=random_lower_string(),
        description=random_lower_string(),
        entity_type_id=entity_type.id,
        created_by_id=user.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    test = Test(
        name=random_lower_string(),
        description=random_lower_string(),
        time_limit=60,
        marks=100,
        link=random_lower_string(),
        created_by_id=user.id,
        is_active=True,
        is_deleted=False,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    payload = {
        "test_id": test.id,
        "device_info": "example",
        "candidate_profile": {"entity_id": entity.id},
    }

    response = client.post(f"{settings.API_V1_STR}/candidate/start_test", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert "candidate_uuid" in data
    assert "candidate_test_id" in data

    candidate_test_id = data["candidate_test_id"]

    candidate_test = db.get(CandidateTest, candidate_test_id)
    assert candidate_test is not None
    assert candidate_test.test_id == test.id
    assert candidate_test.device == "example"
    assert candidate_test.consent is True

    candidate = db.get(Candidate, candidate_test.candidate_id)
    assert candidate is not None
    assert candidate.identity is not None
    assert candidate.user_id is None
    response = client.delete(
        f"{settings.API_V1_STR}/entity/{entity.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    assert response.status_code == 400
    assert "Cannot delete " in response_data["detail"]


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


def test_import_entities_reject_non_csv_file(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test that non-CSV files are rejected"""
    file_content = b"This is not a CSV file"
    non_csv_file = ("not_a_csv.txt", file_content, "text/plain")

    response = client.post(
        f"{settings.API_V1_STR}/entity/import",
        files={"file": non_csv_file},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Only .csv files are allowed"


def test_import_entities_invalid_encoding(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test that invalid file encoding is rejected"""
    invalid_bytes = b"\xff\xfe\xfd\xfc"
    invalid_file = ("invalid.csv", invalid_bytes, "text/csv")

    response = client.post(
        f"{settings.API_V1_STR}/entity/import",
        files={"file": invalid_file},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Invalid file encoding"


def test_import_entities_empty_csv(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test that empty CSV file is rejected"""
    empty_csv = ("empty.csv", b"", "text/csv")

    response = client.post(
        f"{settings.API_V1_STR}/entity/import",
        files={"file": empty_csv},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Invalid file encoding"


def test_import_entities_missing_headers(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test that CSV with missing required headers is rejected"""
    csv_content = """entity_name,block_name
Test Entity,Pa
"""

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
        tmp_file.write(csv_content.encode("utf-8"))
        tmp_file_path = tmp_file.name

    try:
        with open(tmp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/entity/import",
                files={"file": ("missing_headers.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 400
        data = response.json()
        assert "CSV must contain headers" in data["detail"]

    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def test_bulk_upload_entities_unsuccessful_scenarios(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]

    india = Country(name="India")
    db.add(india)
    db.commit()
    db.refresh(india)

    himachal = State(name="Himachal Pradesh", country_id=india.id)
    db.add(himachal)
    db.commit()
    db.refresh(himachal)

    district = District(name="Solan", state_id=himachal.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    block = Block(name="Kasauli", district_id=district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    entity_type = EntityType(
        name="CLF",
        description="Cluster Level Federation",
        organization_id=org_id,
        created_by_id=user_data["id"],
        is_active=True,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    existing_entity = Entity(
        name="Existing Entity",
        created_by_id=user_data["id"],
        entity_type_id=entity_type.id,
        organization_id=org_id,
        state_id=himachal.id,
        district_id=district.id,
        block_id=block.id,
        is_active=True,
    )
    db.add(existing_entity)
    db.commit()

    csv_content = """entity_name,entity_type_name,block_name,district_name,state_name
Existing Entity,CLF,Kasauli,Solan,Himachal Pradesh
Invalid Reference Entity,CLF,Kasauli,UnknownDistrict,Himachal Pradesh
Missing Field Entity,,Kasauli,Solan,Himachal Pradesh
MissingEntityTypeEntity,UnknownType,Kasauli,Solan,Himachal Pradesh
"""

    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/entity/import",
                files={"file": ("unsuccessful_entities.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["uploaded_entities"] == 4
        assert data["success_entities"] == 0
        assert data["failed_entities"] == 4
        assert "Missing references" in data["message"]
        assert "error_log" in data
        expected_errors = {
            1: "Entity already exists",
            2: "District 'UnknownDistrict' not found",
            3: "Missing required value(s)",
            4: "Entity type 'UnknownType' not found",
        }

        assert "data:text/csv;base64," in data["error_log"]
        base64_csv = data["error_log"].split("base64,")[-1]

        csv_bytes = base64.b64decode(base64_csv)
        csv_text = csv_bytes.decode("utf-8")

        csv_reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(csv_reader)

        assert len(rows) == 4

        for row in rows:
            assert "row_number" in row
            assert "entity_name" in row
            assert "error" in row
            assert row["error"]

            row_number = int(row["row_number"])
            expected_error = expected_errors.get(row_number)
            assert expected_error is not None
            assert expected_error.lower() in row["error"].lower()

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_bulk_upload_entities_reference_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]

    country = Country(name="India")
    db.add(country)
    db.commit()
    db.refresh(country)

    valid_state = State(name="Maharashtra", country_id=country.id)
    db.add(valid_state)
    db.commit()
    db.refresh(valid_state)

    valid_district = District(name="Pune", state_id=valid_state.id)
    db.add(valid_district)
    db.commit()
    db.refresh(valid_district)

    valid_block = Block(name="Haveli", district_id=valid_district.id)
    db.add(valid_block)
    db.commit()
    db.refresh(valid_block)

    valid_entity_type = EntityType(
        name="CLF",
        description="Cluster Level Federation",
        organization_id=org_id,
        created_by_id=user_data["id"],
        is_active=True,
    )
    db.add(valid_entity_type)
    db.commit()
    db.refresh(valid_entity_type)

    csv_content = """entity_name,entity_type_name,block_name,district_name,state_name
MissingStateEntity,CLF,Haveli,Pune,UnknownState
MissingDistrictEntity,CLF,Haveli,UnknownDistrict,Maharashtra
MissingBlockEntity,CLF,UnknownBlock,Pune,Maharashtra
MissingEntityTypeEntity,UnknownType,Haveli,Pune,Maharashtra
"""

    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/entity/import",
                files={"file": ("missing_refs.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["uploaded_entities"] == 4
        assert data["success_entities"] == 0
        assert data["failed_entities"] == 4
        assert "Missing references" in data["message"]
        assert "UnknownState" in data["message"]
        assert "UnknownDistrict" in data["message"]
        assert "UnknownBlock" in data["message"]

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_bulk_upload_entities_successful_scenarios(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]

    existing_district = db.exec(select(District)).first()
    assert existing_district is not None

    state = db.exec(select(State).where(State.id == existing_district.state_id)).first()
    assert state is not None

    block = Block(name="Kasauli", district_id=existing_district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    entity_type = EntityType(
        name="CLF",
        description="Cluster Level Federation",
        organization_id=org_id,
        created_by_id=user_data["id"],
        is_active=True,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    csv_content = f"""entity_name,entity_type_name,block_name,district_name,state_name
Clf Kasauli 1,CLF,Kasauli,{existing_district.name},{state.name}
Clf Kasauli 2,CLF,Kasauli,{existing_district.name},{state.name}
Clf Kasauli 3,CLF,Kasauli,{existing_district.name},{state.name}
"""

    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content.encode("utf-8"))
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/entity/import",
                files={"file": ("successful_entities.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["uploaded_entities"] == 3
        assert data["success_entities"] == 3
        assert data["failed_entities"] == 0
        assert "Created 3 entities successfully" in data["message"]

    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
