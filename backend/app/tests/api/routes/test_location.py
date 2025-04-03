from fastapi import status
from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.location import Block, Country, District, State

from ...utils.utils import random_lower_string


def test_create_country(
    client: TestClient,
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


def test_get_country(client: TestClient, db: SessionDep) -> None:
    dubai = Country(name=random_lower_string())
    austria = Country(name=random_lower_string())
    db.add(dubai)
    db.add(austria)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/country/")
    data = response.json()
    last_index = len(data) - 1
    assert response.status_code == 200
    assert data[last_index - 1]["name"] == dubai.name
    assert data[last_index]["name"] == austria.name


def test_get_country_by_id(client: TestClient, db: SessionDep) -> None:
    srilanka = Country(name=random_lower_string())
    db.add(srilanka)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/country/{srilanka.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == srilanka.name
    assert data["id"] == srilanka.id
    response = client.get(f"{settings.API_V1_STR}/location/country/-1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


def test_update_country(client: TestClient, db: SessionDep) -> None:
    original_name = random_lower_string()
    updated_name = random_lower_string()
    australia = Country(name=original_name)
    db.add(australia)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/location/country/{australia.id}",
        json={"name": updated_name},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["id"] == australia.id
    assert data["name"] != original_name
    response = client.put(
        f"{settings.API_V1_STR}/location/country/-1", json={"name": "Australia"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


# ---- State Routers ----


def test_create_state(client: TestClient, db: SessionDep) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    state_name = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/location/state/",
        json={"name": state_name, "country_id": india.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == state_name
    assert data["country_id"] == india.id


def test_get_state(client: TestClient, db: SessionDep) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    goa = State(name=random_lower_string(), country_id=india.id)
    punjab = State(name=random_lower_string(), country_id=india.id)
    db.add(goa)
    db.add(punjab)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/state/")
    data = response.json()
    assert response.status_code == 200
    goa_index = len(data) - 2
    punjab_index = len(data) - 1
    assert data[goa_index]["name"] == goa.name
    assert data[punjab_index]["name"] == punjab.name
    assert data[goa_index]["country_id"] == india.id
    assert data[punjab_index]["country_id"] == india.id


def test_get_state_by_id(client: TestClient, db: SessionDep) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    maharashtra = State(name=random_lower_string(), country_id=india.id)
    db.add(maharashtra)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/state/{maharashtra.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maharashtra.name
    assert data["id"] == maharashtra.id
    assert data["country_id"] == india.id
    response = client.get(f"{settings.API_V1_STR}/location/state/-1")
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


def test_update_state(client: TestClient, db: SessionDep) -> None:
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
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


#  ---- District Routes ----


def test_create_district(client: TestClient, db: SessionDep) -> None:
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
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == district_name
    assert data["state_id"] == kerala.id


def test_get_district(client: TestClient, db: SessionDep) -> None:
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
    response = client.get(f"{settings.API_V1_STR}/location/district/")
    data = response.json()
    assert response.status_code == 200
    ernakulam_index = len(data) - 2
    thrissur_index = len(data) - 1
    assert data[ernakulam_index]["name"] == ernakulam.name
    assert data[ernakulam_index]["id"] == ernakulam.id
    assert data[thrissur_index]["id"] == thrissur.id
    assert data[thrissur_index]["name"] == thrissur.name
    assert data[ernakulam_index]["state_id"] == kerala.id
    assert data[thrissur_index]["state_id"] == kerala.id


def test_get_district_by_id(client: TestClient, db: SessionDep) -> None:
    india = Country(name=random_lower_string())
    db.add(india)
    db.commit()
    kerala = State(name=random_lower_string(), country_id=india.id)
    db.add(kerala)
    db.commit()
    ernakulam = District(name=random_lower_string(), state_id=kerala.id)
    db.add(ernakulam)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/district/{ernakulam.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == ernakulam.name
    assert data["id"] == ernakulam.id
    assert data["state_id"] == ernakulam.state_id
    assert data["state_id"] == kerala.id
    response = client.get(f"{settings.API_V1_STR}/location/district/-1")
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


def test_update_district(client: TestClient, db: SessionDep) -> None:
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
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert "id" in data
    assert data["name"] != original_name

    response = client.put(
        f"{settings.API_V1_STR}/location/district/{ernakulam.id}",
        json={"name": updated_name, "state_id": andhra_pradesh.id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == updated_name
    assert data["id"] == ernakulam.id
    assert data["state_id"] == andhra_pradesh.id
    assert data["state_id"] != kerala.id

    response = client.put(
        f"{settings.API_V1_STR}/location/district/-1",
        json={"name": "Thrissur", "state_id": kerala.id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


#  ------- Block Routes -----


def setup_district(db: SessionDep) -> tuple[District, District]:
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


def test_create_block(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    block_name = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/location/block/",
        json={"name": block_name, "district_id": ernakulam.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert "id" in data
    assert "created_date" in data
    assert "modified_date" in data
    assert data["name"] == block_name
    assert data["district_id"] == ernakulam.id


def test_get_block(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name=random_lower_string(), district_id=ernakulam.id)
    mayani = Block(name=random_lower_string(), district_id=ernakulam.id)
    kumuram = Block(name=random_lower_string(), district_id=thrissur.id)
    db.add(kovil)
    db.add(mayani)
    db.add(kumuram)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/location/block/")
    data = response.json()
    assert response.status_code == 200
    kovil_index = len(data) - 3
    mayani_index = len(data) - 2
    kumuram_index = len(data) - 1
    assert data[kovil_index]["name"] == kovil.name
    assert data[mayani_index]["name"] == mayani.name
    assert data[kumuram_index]["name"] == kumuram.name
    assert data[kovil_index]["district_id"] == ernakulam.id
    assert data[mayani_index]["district_id"] == ernakulam.id
    assert data[kumuram_index]["district_id"] == thrissur.id


def test_get_block_by_id(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name=random_lower_string(), district_id=ernakulam.id)
    mayani = Block(name=random_lower_string(), district_id=ernakulam.id)
    kumuram = Block(name=random_lower_string(), district_id=thrissur.id)
    db.add(kovil)
    db.add(mayani)
    db.add(kumuram)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/location/block/{kovil.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == kovil.name
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id

    response = client.get(f"{settings.API_V1_STR}/location/block/{mayani.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == mayani.name
    assert data["id"] == mayani.id
    assert data["district_id"] == mayani.district_id

    response = client.get(f"{settings.API_V1_STR}/location/block/{kumuram.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == kumuram.name
    assert data["id"] == kumuram.id
    assert data["district_id"] == kumuram.district_id

    response = client.get(f"{settings.API_V1_STR}/location/block/-1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}


def test_update_block(client: TestClient, db: SessionDep) -> None:
    original_name = random_lower_string()
    updated_name = random_lower_string()
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name=original_name, district_id=ernakulam.id)
    db.add(kovil)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/location/block/{kovil.id}",
        json={"name": updated_name, "district_id": ernakulam.id},
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
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}
