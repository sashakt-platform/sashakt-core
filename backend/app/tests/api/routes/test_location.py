import base64
import csv
import io
import os
import tempfile

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.location import Block, Country, District, State
from app.models.role import Role
from app.tests.utils.organization import create_random_organization
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import assert_paginated_response

from ...utils.utils import random_email, random_lower_string


def test_create_country(
    client: TestClient,
    db: SessionDep,
    get_user_candidate_token: dict[str, str],
    get_user_superadmin_token: dict[str, str],
) -> None:
    country = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/location/country/",
        json={"name": country},
        headers=get_user_superadmin_token,
    )
    data = response.json()

    china = Country(name=random_lower_string())
    db.add(china)
    db.commit()
    db.refresh(china)
    assert response.status_code == 200
    assert data["name"] == country

    response = client.post(
        f"{settings.API_V1_STR}/location/country/",
        json={"name": country},
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["detail"] == "User Not Permitted"


def test_get_country(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    dubai = Country(name=random_lower_string())
    austria = Country(name=random_lower_string())

    db.add_all([dubai, austria])
    db.commit()
    db.refresh(dubai)

    db.refresh(austria)

    response = client.get(
        f"{settings.API_V1_STR}/location/country/", headers=get_user_superadmin_token
    )
    data = response.json()
    items = data["items"]
    assert response.status_code == 200
    assert any(item["name"] == dubai.name for item in items)
    assert any(item["name"] == austria.name for item in items)

    for _ in range(1, 11):
        country = Country(name=random_lower_string())
        db.add(country)
        db.commit()

    country_1 = Country(name=random_lower_string(), is_active=False)
    country_2 = Country(name=random_lower_string(), is_active=False)
    db.add_all([country_1, country_2])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/country/?page=2",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2

    response = client.get(
        f"{settings.API_V1_STR}/location/country/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert_paginated_response(response, min_expected_total=12, min_expected_pages=1)

    response = client.get(
        f"{settings.API_V1_STR}/location/country/?is_active=False",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert_paginated_response(response, min_expected_total=2, min_expected_pages=1)


def test_get_country_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    srilanka = Country(name=random_lower_string())
    db.add(srilanka)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/country/{srilanka.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == srilanka.name
    assert data["id"] == srilanka.id
    response = client.get(
        f"{settings.API_V1_STR}/location/country/-1", headers=get_user_superadmin_token
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


def test_update_country(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    original_name = random_lower_string()
    updated_name = random_lower_string()
    australia = Country(name=original_name)
    db.add(australia)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/location/country/{australia.id}",
        json={"name": updated_name},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["id"] == australia.id
    assert data["name"] != original_name
    response = client.put(
        f"{settings.API_V1_STR}/location/country/-1",
        json={
            "name": "Australia",
        },
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


# ---- State Routers ----


def test_create_state(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    state_name = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/location/state/",
        json={"name": state_name, "country_id": india.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == state_name
    assert data["country_id"] == india.id


def test_get_state(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/location/state/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    assert len(items) >= 10
    assert_paginated_response(response, min_expected_total=10, min_expected_pages=1)

    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    db.refresh(india)

    goa = State(name=random_lower_string(), country_id=india.id)
    punjab = State(name=random_lower_string(), country_id=india.id)
    db.add(goa)
    db.add(punjab)
    db.commit()
    db.refresh(goa)
    db.refresh(punjab)
    response = client.get(
        f"{settings.API_V1_STR}/location/state/?size=100",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    items = data["items"]
    assert len(items) >= 2

    assert any(item["name"] == goa.name for item in items)
    assert any(item["name"] == punjab.name for item in items)
    assert any(item["country_id"] == india.id for item in items)

    response = client.get(
        f"{settings.API_V1_STR}/location/state/?country={india.id}",
        headers=get_user_superadmin_token,
    )

    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 2

    state_3 = State(name=random_lower_string(), country_id=india.id, is_active=False)
    state_4 = State(name=random_lower_string(), country_id=india.id, is_active=False)
    db.add_all([state_3, state_4])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/state/?is_active=False",
        headers=get_user_superadmin_token,
    )

    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 2


def test_get_state_filter_by_name(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    db.refresh(country)

    state_1 = State(name=" Randomstate", country_id=country.id)
    state_2 = State(name=random_lower_string(), country_id=country.id)
    db.add_all([state_1, state_2])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/state/?name=randomstate",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert any(
        state["name"].strip().lower() == "randomstate" for state in data["items"]
    )

    response = client.get(
        f"{settings.API_V1_STR}/location/state/?name=random",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert any(
        state["name"].strip().lower() == "randomstate" for state in data["items"]
    )

    response = client.get(
        f"{settings.API_V1_STR}/location/state/?name=randomnonmatch",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 0

    state_3 = State(name=" RandomstateAnother", country_id=country.id)
    db.add(state_3)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/state/?name=random",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 2


def test_get_state_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    maharashtra = State(name=random_lower_string(), country_id=india.id)
    db.add(maharashtra)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/location/state/{maharashtra.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maharashtra.name
    assert data["id"] == maharashtra.id
    assert data["country_id"] == india.id
    response = client.get(
        f"{settings.API_V1_STR}/location/state/-1", headers=get_user_superadmin_token
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


def test_update_state(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    original_name = random_lower_string()
    updated_name = random_lower_string()
    india = Country(name=random_lower_string())
    australia = Country(name=random_lower_string())
    db.add_all([india, australia])
    db.commit()
    goa = State(name=original_name, country_id=india.id)
    db.add(goa)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/location/state/{goa.id}",
        json={"name": updated_name, "country_id": india.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["name"] != original_name
    assert data["id"] == goa.id
    assert data["country_id"] == india.id

    response = client.put(
        f"{settings.API_V1_STR}/location/state/{goa.id}",
        json={"name": updated_name, "country_id": australia.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["name"] != original_name
    assert data["id"] == goa.id
    assert data["country_id"] == australia.id
    assert data["country_id"] != india.id

    response = client.put(
        f"{settings.API_V1_STR}/location/state/-1",
        json={"name": "Goa", "country_id": india.id},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


#  ---- District Routes ----


def test_create_district(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    kerala = State(name=random_lower_string(), country_id=india.id)
    db.add(kerala)
    db.commit()
    district_name = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/location/district/",
        json={"name": district_name, "state_id": kerala.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == district_name
    assert data["state"]["id"] == kerala.id
    assert data["state"]["name"] == kerala.name


def test_get_district(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    kerala = State(name=random_lower_string(), country_id=india.id)
    db.add(kerala)
    db.commit()
    db.flush()
    ernakulam = District(name=random_lower_string(), state_id=kerala.id)
    thrissur = District(name=random_lower_string(), state_id=kerala.id)
    db.add(ernakulam)
    db.add(thrissur)
    db.commit()
    db.refresh(ernakulam)
    db.refresh(thrissur)
    response = client.get(
        f"{settings.API_V1_STR}/location/district/?size=100&state_ids={kerala.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    data = response_data["items"]
    assert response.status_code == 200

    assert any(item["name"] == ernakulam.name for item in data)

    assert any(item["name"] == thrissur.name for item in data)
    assert any(item["id"] == ernakulam.id for item in data)
    assert any(item["id"] == thrissur.id for item in data)
    assert any(item["state"]["id"] == kerala.id for item in data)

    response = client.get(
        f"{settings.API_V1_STR}/location/district/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert len(data["items"]) >= 10
    assert_paginated_response(response, min_expected_total=10, min_expected_pages=1)

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?state_ids={kerala.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert len(data["items"]) == 2


def test_get_district_by_state_ids_filter(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()

    kerala = State(name=random_lower_string(), country_id=india.id)
    karnataka = State(name=random_lower_string(), country_id=india.id)
    tamil_nadu = State(name=random_lower_string(), country_id=india.id)
    db.add_all([kerala, karnataka, tamil_nadu])
    db.commit()
    db.flush()

    ernakulam = District(name=random_lower_string(), state_id=kerala.id)
    thrissur = District(name=random_lower_string(), state_id=kerala.id)
    bangalore = District(name=random_lower_string(), state_id=karnataka.id)
    chennai = District(name=random_lower_string(), state_id=tamil_nadu.id)

    db.add_all([ernakulam, thrissur, bangalore, chennai])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?state_ids={kerala.id}&state_ids={karnataka.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["items"]) == 3

    district_names = [item["name"] for item in data["items"]]
    assert ernakulam.name in district_names
    assert thrissur.name in district_names
    assert bangalore.name in district_names
    assert chennai.name not in district_names

    state_ids_in_response = [item["state"]["id"] for item in data["items"]]
    assert kerala.id in state_ids_in_response
    assert karnataka.id in state_ids_in_response
    assert tamil_nadu.id not in state_ids_in_response

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?state_ids={tamil_nadu.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == chennai.name
    assert data["items"][0]["state"]["id"] == tamil_nadu.id


def test_get_district_by_name_filter(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()
    state = State(name=random_lower_string(), country_id=country.id)
    db.add(state)
    db.commit()
    db.flush()

    district_1 = District(name="North Zone", state_id=state.id)
    district_2 = District(name="North Zone Extension", state_id=state.id)
    district_3 = District(name="East Wing", state_id=state.id)
    db.add_all([district_1, district_2, district_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?name=north zone extension",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "North Zone Extension"

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?name=North Zone",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 2
    names = [d["name"] for d in data["items"]]
    assert "North Zone" in names
    assert "North Zone Extension" in names

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?name=Central Zone",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 0

    response = client.get(
        f"{settings.API_V1_STR}/location/district/?name=north zone",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 2
    assert any(d["name"].lower() == "north zone" for d in data["items"])


def test_get_district_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    kerala = State(name=random_lower_string(), country_id=india.id)
    db.add(kerala)
    db.commit()
    ernakulam = District(name=random_lower_string(), state_id=kerala.id)
    db.add(ernakulam)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/location/district/{ernakulam.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == ernakulam.name
    assert data["id"] == ernakulam.id
    assert data["state"]["id"] == ernakulam.state_id
    assert data["state"]["name"] == kerala.name
    response = client.get(
        f"{settings.API_V1_STR}/location/district/-1", headers=get_user_superadmin_token
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


def test_update_district(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    original_name = random_lower_string()
    updated_name = random_lower_string()
    db.add(india)
    db.commit()
    kerala = State(name=random_lower_string(), country_id=india.id)
    db.add(kerala)
    andhra_pradesh = State(name=random_lower_string(), country_id=india.id)
    db.add(andhra_pradesh)
    db.commit()
    ernakulam = District(name=original_name, state_id=kerala.id)
    db.add(ernakulam)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/location/district/{ernakulam.id}",
        json={"name": updated_name, "state_id": kerala.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert "id" in data
    assert data["name"] != original_name

    response = client.put(
        f"{settings.API_V1_STR}/location/district/{ernakulam.id}",
        json={"name": updated_name, "state_id": andhra_pradesh.id},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == updated_name
    assert data["id"] == ernakulam.id
    assert data["state"]["id"] == andhra_pradesh.id
    assert data["state"]["name"] == andhra_pradesh.name
    assert data["state"]["id"] != kerala.id

    response = client.put(
        f"{settings.API_V1_STR}/location/district/-1",
        json={"name": "Thrissur", "state_id": kerala.id},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


#  ------- Block Routes -----


def setup_district(
    db: SessionDep,
) -> tuple[District, District]:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()

    kerala = State(name=random_lower_string(), country_id=india.id)
    db.add(kerala)
    db.commit()

    ernakulam = District(name=random_lower_string(), state_id=kerala.id)
    thrissur = District(name=random_lower_string(), state_id=kerala.id)
    db.add(ernakulam)
    db.add(thrissur)
    db.commit()

    return ernakulam, thrissur


def test_create_block(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    ernakulam, thrissur = setup_district(db)
    block_name = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/location/block/",
        json={"name": block_name, "district_id": ernakulam.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert data["name"] == block_name
    assert data["district_id"] == ernakulam.id


def test_get_block(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    ernakulam, thrissur = setup_district(db)

    for _ in range(1, 11):
        block = Block(name=random_lower_string(), district_id=ernakulam.id)
        db.add(block)
        db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/block/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert len(data["items"]) >= 10

    kovil = Block(name=random_lower_string(), district_id=ernakulam.id)
    mayani = Block(name=random_lower_string(), district_id=ernakulam.id)
    kumuram = Block(name=random_lower_string(), district_id=thrissur.id)
    db.add(kovil)
    db.add(mayani)
    db.add(kumuram)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/block/?size=100&block={kovil.id}&block={mayani.id}&block={kumuram.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()
    data = response_data["items"]
    assert response.status_code == 200

    assert any(item["name"] == kovil.name for item in data)
    assert any(item["name"] == mayani.name for item in data)
    assert any(item["name"] == kumuram.name for item in data)

    assert any(item["district_id"] == kumuram.district_id for item in data)
    assert any(item["district_id"] == mayani.district_id for item in data)
    assert any(item["district_id"] == kovil.district_id for item in data)

    response = client.get(
        f"{settings.API_V1_STR}/location/block/?district_ids={thrissur.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 1

    block_a = Block(
        name=random_lower_string(), district_id=thrissur.id, is_active=False
    )
    block_b = Block(
        name=random_lower_string(), district_id=thrissur.id, is_active=False
    )

    db.add_all([block_a, block_b])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/block/?is_active=False",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 2


def test_get_block_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name=random_lower_string(), district_id=ernakulam.id)
    mayani = Block(name=random_lower_string(), district_id=ernakulam.id)
    kumuram = Block(name=random_lower_string(), district_id=thrissur.id)
    db.add(kovil)
    db.add(mayani)
    db.add(kumuram)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/block/{kovil.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == kovil.name
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id

    response = client.get(
        f"{settings.API_V1_STR}/location/block/{mayani.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == mayani.name
    assert data["id"] == mayani.id
    assert data["district_id"] == mayani.district_id

    response = client.get(
        f"{settings.API_V1_STR}/location/block/{kumuram.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == kumuram.name
    assert data["id"] == kumuram.id
    assert data["district_id"] == kumuram.district_id

    response = client.get(
        f"{settings.API_V1_STR}/location/block/-1", headers=get_user_superadmin_token
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}


def test_update_block(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    original_name = random_lower_string()
    updated_name = random_lower_string()
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name=original_name, district_id=ernakulam.id)
    db.add(kovil)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/location/block/{kovil.id}",
        json={"name": updated_name, "district_id": ernakulam.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id
    assert data["district_id"] == ernakulam.id

    response = client.put(
        f"{settings.API_V1_STR}/location/block/{kovil.id}",
        json={"name": updated_name, "district_id": thrissur.id},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["id"] == kovil.id
    assert data["district_id"] == thrissur.id
    assert data["district_id"] != ernakulam.id

    response = client.put(
        f"{settings.API_V1_STR}/location/block/-1",
        json={"name": "Nonexistent Block", "district_id": kovil.id},
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}


def test_create_inactive_country_not_listed(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    country_name = "InactiveLand"
    response = client.post(
        f"{settings.API_V1_STR}/location/country/",
        json={"name": country_name, "is_active": False},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["is_active"] is False
    country_id = data["id"]
    response = client.get(
        f"{settings.API_V1_STR}/location/country/?is_active=true",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    assert all(item["is_active"] is True for item in items)
    assert all(item["id"] != country_id for item in items)


def test_create_inactive_state_not_listed(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    country = Country(name="ActiveCountry")
    db.add(country)
    db.commit()
    db.refresh(country)
    response = client.post(
        f"{settings.API_V1_STR}/location/state/",
        json={"name": "InactiveState", "country_id": country.id, "is_active": False},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    state_id = data["id"]
    assert data["is_active"] is False
    response = client.get(
        f"{settings.API_V1_STR}/location/state/?is_active=true",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert all(item["id"] != state_id for item in data["items"])
    assert all(item["is_active"] is True for item in data["items"])
    response = client.get(
        f"{settings.API_V1_STR}/location/state/?is_active=false",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert any(item["id"] == state_id for item in data["items"])
    assert all(item["is_active"] is False for item in data["items"])
    response = client.get(
        f"{settings.API_V1_STR}/location/state/?size=100",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert any(item["id"] == state_id for item in data["items"])


def test_create_inactive_district_not_listed(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name="ActiveCountry")
    db.add(india)
    db.commit()
    db.refresh(india)
    state = State(name="ActiveState", country_id=india.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    response = client.post(
        f"{settings.API_V1_STR}/location/district/",
        json={
            "name": "InactiveDistrict",
            "state_id": state.id,
            "is_active": False,
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    district_id = data["id"]
    assert data["is_active"] is False
    response = client.get(
        f"{settings.API_V1_STR}/location/district/?is_active=true",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert all(item["id"] != district_id for item in data["items"])
    response = client.get(
        f"{settings.API_V1_STR}/location/district/?is_active=false",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert any(item["id"] == district_id for item in data["items"])
    assert all(item["is_active"] is False for item in data["items"])


def test_create_inactive_block_not_listed(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    country = Country(name="ActiveCountry")
    db.add(country)
    db.commit()
    db.refresh(country)
    state = State(name="ActiveState", country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name="ActiveDistrict", state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)
    response = client.post(
        f"{settings.API_V1_STR}/location/block/",
        json={
            "name": "InactiveBlock",
            "district_id": district.id,
            "is_active": False,
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    block_id = data["id"]
    assert data["is_active"] is False
    response = client.get(
        f"{settings.API_V1_STR}/location/block/?is_active=true",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert all(item["id"] != block_id for item in data["items"])
    response = client.get(
        f"{settings.API_V1_STR}/location/block/?is_active=false",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert any(item["id"] == block_id for item in data["items"])
    assert all(item["is_active"] is False for item in data["items"])


def test_get_is_active_country(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    dubai = Country(name=random_lower_string())
    austria = Country(name=random_lower_string())

    db.add_all([dubai, austria])
    db.commit()
    db.refresh(dubai)

    db.refresh(austria)

    response = client.get(
        f"{settings.API_V1_STR}/location/country/?size=100",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert any(item["name"] == dubai.name for item in data["items"])
    assert any(item["name"] == austria.name for item in data["items"])

    for _ in range(1, 11):
        country = Country(name=random_lower_string(), is_active=True)
        db.add(country)
        db.commit()

    country_1 = Country(name=random_lower_string(), is_active=False)
    country_2 = Country(name=random_lower_string(), is_active=False)
    db.add_all([country_1, country_2])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/location/country/?is_active=false",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    names = [item["name"] for item in data["items"]]

    assert country_1.name in names
    assert country_2.name in names
    assert all(item["is_active"] is False for item in data["items"])
    data = response.json()
    response = client.get(
        f"{settings.API_V1_STR}/location/country/?is_active=true",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 10
    assert all(item["is_active"] is True for item in data["items"])


def test_get_state_admin_state_list(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    state_2 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_2)
    db.commit()
    db.refresh(state_2)

    state_3 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_3)
    db.commit()
    db.refresh(state_3)

    response = client.get(
        f"{settings.API_V1_STR}/location/state/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) > 1

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state_3.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    response = client.get(
        f"{settings.API_V1_STR}/location/state/",
        headers=token_headers,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == state_3.name
    assert data["items"][0]["id"] == state_3.id

    # ---Check test for test admin

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    test_admin_email = random_email()
    test_admin_payload = {
        "email": test_admin_email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": test_admin_role.id,
        "organization_id": new_organization.id,
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=token_headers,
        json=test_admin_payload,
    )
    assert create_response.status_code == 200

    # Get token for the newly created admin
    new_admin_token = authentication_token_from_email(
        client=client, email=test_admin_email, db=db
    )

    # Check districts available to the new admin
    response = client.get(
        f"{settings.API_V1_STR}/location/state/",
        headers=new_admin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == state_3.name
    assert data["items"][0]["id"] == state_3.id


def test_filter_district_for_state_admin(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    state_2 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state_2)
    db.commit()
    db.refresh(state_2)

    district_1 = District(name=random_lower_string(), is_active=True, state_id=state.id)
    district_2 = District(name=random_lower_string(), is_active=True, state_id=state.id)
    district_3 = District(
        name=random_lower_string(), is_active=True, state_id=state_2.id
    )
    db.add_all([district_1, district_2, district_3])
    db.commit()
    db.refresh(district_1)
    db.refresh(district_2)
    db.refresh(district_3)

    response = client.get(
        f"{settings.API_V1_STR}/location/district/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) > 1

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    response = client.get(
        f"{settings.API_V1_STR}/location/district/",
        headers=token_headers,
    )
    data = response.json()
    assert response.status_code == 200
    assert len(data["items"]) == 2
    items = data["items"]
    assert all(item["state"]["id"] == state.id for item in items)
    district_ids = [item["id"] for item in data["items"]]
    assert district_1.id in district_ids
    assert district_2.id in district_ids
    assert district_3.id not in district_ids

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert test_admin_role is not None

    test_admin_email = random_email()
    test_admin_payload = {
        "email": test_admin_email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": test_admin_role.id,
        "organization_id": new_organization.id,
    }
    create_response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=token_headers,
        json=test_admin_payload,
    )
    assert create_response.status_code == 200
    created_admin = create_response.json()

    # Get token for the newly created admin
    new_admin_token = authentication_token_from_email(
        client=client, email=test_admin_email, db=db
    )

    # Check districts available to the new admin
    response = client.get(
        f"{settings.API_V1_STR}/location/district/",
        headers=new_admin_token,
    )
    data = response.json()

    assert response.status_code == 200
    assert len(data["items"]) == 2
    items = data["items"]

    # Verify all districts belong to the same state
    assert all(item["state"]["id"] == state.id for item in items)

    # Verify correct districts are present
    district_ids = [item["id"] for item in items]
    assert district_1.id in district_ids
    assert district_2.id in district_ids

    # Verify district from other state is NOT accessible
    assert district_3.id not in district_ids

    # Verify state association on created admin
    assert created_admin["states"][0]["id"] == state.id
    assert created_admin["states"][0]["name"] == state.name


def test_import_blocks_csv_all_scenarios(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    state = State(name="state_a", country_id=india.id)
    db.add(state)
    db.commit()
    db.refresh(state)
    district = District(name="district_a", state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    csv_content = """block_name,district_name,state_name
Block A,district_a,state_a
Block B,district_a,state_a
,district_a,state_a
Block D,NonExistentDistrict,state_a
Block A,district_a,state_a
Block E,district_a,state_a
"""

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
        tmp_file.write(csv_content.encode("utf-8"))
        tmp_file_path = tmp_file.name

    try:
        with open(tmp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/location/block/import",
                files={"file": ("blocks_test.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["uploaded_blocks"] == 6
        assert data["success_blocks"] == 3
        assert data["failed_blocks"] == 3
        assert "Missing districts" in data["message"]
        assert "Duplicate blocks skipped" in data["message"]
        assert data["error_log"] is not None
        base64_csv = data["error_log"].split("base64,")[-1]
        csv_bytes = base64.b64decode(base64_csv)
        csv_text = csv_bytes.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        error_rows = list(csv_reader)
        assert len(error_rows) == 3
        expected_errors = {
            4: "Missing required value(s)",
            5: "District 'NonExistentDistrict' in state 'state_a' not found",
            6: "Block already exists",
        }
        for row in error_rows:
            row_num = int(row["row_number"])
            assert expected_errors[row_num] in row["error"]

    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def test_import_blocks_reject_non_csv_file(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    file_content = b"This is not a CSV file"
    non_csv_file = ("not_a_csv.txt", file_content, "text/plain")

    response = client.post(
        f"{settings.API_V1_STR}/location/block/import",
        files={"file": non_csv_file},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Only .csv files are allowed"


def test_import_blocks_invalid_encoding(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    invalid_bytes = b"\xff\xfe\xfd\xfc"
    invalid_file = ("invalid.csv", invalid_bytes, "text/csv")

    response = client.post(
        f"{settings.API_V1_STR}/location/block/import",
        files={"file": invalid_file},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 400
    data = response.json()
    assert data["detail"] == "Invalid file encoding"


def test_import_blocks_csv_missing_headers(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    csv_content = """block_name,district_name
Block A,Anantapur
Block B,Anantapur
"""

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
        tmp_file.write(csv_content.encode("utf-8"))
        tmp_file_path = tmp_file.name

    try:
        with open(tmp_file_path, "rb") as file:
            response = client.post(
                f"{settings.API_V1_STR}/location/block/import",
                files={"file": ("blocks_missing_headers.csv", file, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 400
        data = response.json()
        assert "CSV must contain headers" in data["detail"]
        assert "state_name" in data["detail"]

    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)


def test_import_blocks_csv_multiple_state_combinations(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    country = Country(name=random_lower_string())
    db.add(country)
    db.commit()

    state_andhra = State(name="Andhra Pradesh", country_id=country.id)
    state_telangana = State(name="Telangana", country_id=country.id)
    db.add_all([state_andhra, state_telangana])
    db.commit()
    db.refresh(state_andhra)
    db.refresh(state_telangana)

    district_anantapur = District(name="district_aa", state_id=state_andhra.id)
    district_kurnool = District(name="district_bb", state_id=state_andhra.id)
    district_hyderabad = District(name="district_cc", state_id=state_telangana.id)

    db.add_all([district_anantapur, district_kurnool, district_hyderabad])
    db.commit()
    db.refresh(district_anantapur)
    db.refresh(district_kurnool)
    db.refresh(district_hyderabad)

    csv_content = """block_name,district_name,state_name
Block A,district_aa,Andhra Pradesh
Block B,district_bb,Andhra Pradesh
Block C,district_cc,Telangana
Block D,NonExistentDistrict,Telangana
,district_cc,Telangana
Block A,district_aa,Andhra Pradesh
Block X,district_cc,Andhra Pradesh
"""

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temporary_file:
        temporary_file.write(csv_content.encode("utf-8"))
        temporary_file_path = temporary_file.name

    try:
        with open(temporary_file_path, "rb") as file_object:
            response = client.post(
                f"{settings.API_V1_STR}/location/block/import",
                files={"file": ("blocks_states_test.csv", file_object, "text/csv")},
                headers=get_user_superadmin_token,
            )

        assert response.status_code == 201
        data = response.json()

        assert data["uploaded_blocks"] == 7
        assert data["success_blocks"] == 3
        assert data["failed_blocks"] == 4

        assert "Missing districts" in data["message"]
        assert "Duplicate blocks skipped" in data["message"]
        assert data["error_log"] is not None

        base64_csv = data["error_log"].split("base64,")[-1]
        csv_bytes = base64.b64decode(base64_csv)
        csv_text = csv_bytes.decode("utf-8")

        csv_reader = csv.DictReader(io.StringIO(csv_text))
        error_rows = list(csv_reader)

        assert len(error_rows) == 4

        expected_errors = {
            5: "District 'NonExistentDistrict' in state 'Telangana' not found",
            6: "Missing required value(s)",
            7: "Block already exists",
            8: "District 'district_cc' in state 'Andhra Pradesh' not found",
        }

        for row in error_rows:
            row_number = int(row["row_number"])
            assert expected_errors[row_number] in row["error"]

    finally:
        if os.path.exists(temporary_file_path):
            os.unlink(temporary_file_path)
