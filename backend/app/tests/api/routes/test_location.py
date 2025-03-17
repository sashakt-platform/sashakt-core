from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.location import Block, Country, District, State


def test_create_country(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/location/country/", json={"name": "China"}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "China"


def test_get_country(client: TestClient, db: SessionDep) -> None:
    dubai = Country(name="Dubai")
    austria = Country(name="Austria")
    db.add(dubai)
    db.add(austria)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/country/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == dubai.name
    assert data[1]["name"] == austria.name


def test_get_country_by_id(client: TestClient, db: SessionDep) -> None:
    srilanka = Country(name="Srilanka")
    db.add(srilanka)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/country/{srilanka.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == srilanka.name
    assert data["id"] == srilanka.id
    response = client.get(f"{settings.API_V1_STR}/location/country/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


def test_update_country(client: TestClient, db: SessionDep) -> None:
    australia = Country(name="Australiaaa")
    db.add(australia)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/location/country/{australia.id}",
        json={"name": "Australia"},
    )
    data = response.json()
    print("data-->", data)
    print("auss->", australia)
    assert response.status_code == 200
    assert data["name"] == "Australia"
    assert data["id"] == australia.id
    assert data["name"] != "Australiaaa"
    response = client.put(
        f"{settings.API_V1_STR}/location/country/2", json={"name": "Australia"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


# ---- State Routers ----


def test_create_state(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/location/state/",
        json={"name": "Kerala", "country_id": india.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kerala"
    assert data["country_id"] == india.id


def test_get_state(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    goa = State(name="Goa", country_id=india.id)
    punjab = State(name="Punjab", country_id=india.id)
    db.add(goa)
    db.add(punjab)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/state/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == goa.name
    assert data[0]["name"] != "goa"
    assert data[0]["name"] == "Goa"
    assert data[1]["name"] == punjab.name
    assert data[0]["country_id"] == india.id
    assert data[1]["country_id"] == india.id


def test_get_state_by_id(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    maharashtra = State(name="Maharashtra", country_id=india.id)
    db.add(maharashtra)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/state/{maharashtra.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maharashtra.name
    assert data["id"] == maharashtra.id
    assert data["country_id"] == india.id
    response = client.get(f"{settings.API_V1_STR}/location/state/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


def test_update_state(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    goa = State(name="Goaaa", country_id=india.id)
    db.add(goa)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/location/state/{goa.id}",
        json={"name": "Goa", "country_id": india.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Goa"
    assert data["id"] == goa.id
    assert data["name"] != "Goaaa"

    response = client.put(
        f"{settings.API_V1_STR}/location/state/2",
        json={"name": "Goa", "country_id": india.id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}

    uk = Country(name="UK")
    db.add(uk)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/location/state/{goa.id}",
        json={"name": goa.name, "country_id": uk.id},
    )

    data = response.json()
    assert response.status_code == 200
    assert data["name"] == goa.name
    assert data["id"] == goa.id
    assert data["name"] != "Goaaa"
    assert data["country_id"] == uk.id
    assert data["country_id"] != india.id


#  ---- District Routes ----


def test_create_district(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()
    response = client.post(
        f"{settings.API_V1_STR}/location/district/",
        json={"name": "Ernakulam", "state_id": kerala.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["state_id"] == kerala.id


def test_get_district(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()
    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    thrissur = District(name="Thrissur", state_id=kerala.id)
    db.add(ernakulam)
    db.add(thrissur)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/district/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == ernakulam.name
    assert data[1]["name"] == thrissur.name
    assert data[0]["state_id"] == kerala.id
    assert data[1]["state_id"] == kerala.id


def test_get_district_by_id(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()
    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    db.add(ernakulam)
    db.commit()
    response = client.get(f"{settings.API_V1_STR}/location/district/{ernakulam.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["name"] != "Thrissur"
    assert data["id"] == ernakulam.id
    assert data["state_id"] == ernakulam.state_id
    assert data["state_id"] == kerala.id
    response = client.get(f"{settings.API_V1_STR}/location/district/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


def test_update_district(client: TestClient, db: SessionDep) -> None:
    india = Country(name="India")
    db.add(india)
    db.commit()
    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    andhra_pradesh = State(name="Andhra Pradesh", country_id=india.id)
    db.add(andhra_pradesh)
    db.commit()
    ernakulam = District(name="Ernakulamm", state_id=kerala.id)
    db.add(ernakulam)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/location/district/{ernakulam.id}",
        json={"name": "Ernakulam", "state_id": kerala.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert "id" in data
    assert data["name"] != "Ernakulamm"

    response = client.put(
        f"{settings.API_V1_STR}/location/district/{ernakulam.id}",
        json={"name": "Ernakulam", "state_id": andhra_pradesh.id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ernakulam"
    assert data["id"] == ernakulam.id
    assert data["state_id"] == andhra_pradesh.id
    assert data["state_id"] != kerala.id

    response = client.put(
        f"{settings.API_V1_STR}/location/district/2",
        json={"name": "Thrissur", "state_id": kerala.id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


#  ------- Block Routes -----


def setup_district(db: SessionDep) -> tuple[District, District]:
    india = Country(name="India")
    db.add(india)
    db.commit()

    kerala = State(name="Kerala", country_id=india.id)
    db.add(kerala)
    db.commit()

    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    thrissur = District(name="Thrissur", state_id=kerala.id)
    db.add(ernakulam)
    db.add(thrissur)
    db.commit()

    return ernakulam, thrissur


def test_create_block(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    response = client.post(
        f"{settings.API_V1_STR}/location/block/",
        json={"name": "Kovil", "district_id": ernakulam.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kovil"
    assert data["district_id"] == ernakulam.id


def test_get_block(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    mayani = Block(name="Mayani", district_id=ernakulam.id)
    kumuram = Block(name="Kumuram", district_id=thrissur.id)
    db.add(kovil)
    db.add(mayani)
    db.add(kumuram)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/location/block/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 3

    block_names = {block["name"] for block in data}
    assert "Kovil" in block_names
    assert "Mayani" in block_names
    assert "Kumuram" in block_names

    for block in data:
        if block["name"] == "Kovil":
            assert block["district_id"] == ernakulam.id
        elif block["name"] == "Mayani":
            assert block["district_id"] == ernakulam.id
        elif block["name"] == "Kumuram":
            assert block["district_id"] == thrissur.id


def test_get_block_by_id(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    mayani = Block(name="Mayani", district_id=ernakulam.id)
    kumuram = Block(name="Kumuram", district_id=thrissur.id)
    db.add(kovil)
    db.add(mayani)
    db.add(kumuram)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/location/block/{kovil.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id

    response = client.get(f"{settings.API_V1_STR}/location/block/{mayani.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Mayani"
    assert data["id"] == mayani.id
    assert data["district_id"] == mayani.district_id

    response = client.get(f"{settings.API_V1_STR}/location/block/{kumuram.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kumuram"
    assert data["id"] == kumuram.id
    assert data["district_id"] == kumuram.district_id

    response = client.get(f"{settings.API_V1_STR}/location/block/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}


def test_update_block(client: TestClient, db: SessionDep) -> None:
    ernakulam, thrissur = setup_district(db)
    kovil = Block(name="Kovil", district_id=ernakulam.id)
    db.add(kovil)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/location/block/{kovil.id}",
        json={"name": "New Kovil", "district_id": ernakulam.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "New Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == kovil.district_id
    assert data["district_id"] == ernakulam.id

    response = client.put(
        f"{settings.API_V1_STR}/location/block/{kovil.id}",
        json={"name": "New Kovil", "district_id": thrissur.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "New Kovil"
    assert data["id"] == kovil.id
    assert data["district_id"] == thrissur.id
    assert data["district_id"] != ernakulam.id

    response = client.put(
        f"{settings.API_V1_STR}/location/block/999",
        json={"name": "Nonexistent Block", "district_id": kovil.id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Block not found"}
