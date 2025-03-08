from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import Country, State


def test_create_state(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()

    response = client.post(
        "/location/state/", json={"name": "Kerala", "country_id": india.id}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kerala"
    assert data["country_id"] == india.id


def test_get_state(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    goa = State(name="Goa", country_id=india.id)
    punjab = State(name="Punjab", country_id=india.id)
    session.add(goa)
    session.add(punjab)
    session.commit()
    response = client.get("/location/state/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == goa.name
    assert data[0]["name"] != "goa"
    assert data[0]["name"] == "Goa"
    assert data[1]["name"] == punjab.name
    assert data[0]["country_id"] == india.id
    assert data[1]["country_id"] == india.id


def test_get_state_by_id(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    maharashtra = State(name="Maharashtra", country_id=india.id)
    session.add(maharashtra)
    session.commit()
    response = client.get(f"/location/state/{maharashtra.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maharashtra.name
    assert data["id"] == maharashtra.id
    assert data["country_id"] == india.id
    response = client.get("/location/state/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


def test_update_state(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    goa = State(name="Goaaa", country_id=india.id)
    session.add(goa)
    session.commit()

    response = client.put(
        f"/location/state/{goa.id}", json={"name": "Goa", "country_id": india.id}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Goa"
    assert data["id"] == goa.id
    assert data["name"] != "Goaaa"

    response = client.put(
        "/location/state/2", json={"name": "Goa", "country_id": india.id}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}

    uk = Country(name="UK")
    session.add(uk)
    session.commit()

    response = client.put(
        f"/location/state/{goa.id}", json={"name": goa.name, "country_id": uk.id}
    )

    data = response.json()
    assert response.status_code == 200
    assert data["name"] == goa.name
    assert data["id"] == goa.id
    assert data["name"] != "Goaaa"
    assert data["country_id"] == uk.id
    assert data["country_id"] != india.id
