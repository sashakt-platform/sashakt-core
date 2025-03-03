from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import Country, State


def test_create_state(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    response = client.post("/location/state/", json={"name": "Kerala", "country_id": 1})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Kerala"


def test_get_state(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    goa = State(name="Goa", country_id=1)
    punjab = State(name="Punjab", country_id=1)
    session.add(goa)
    session.add(punjab)
    session.commit()
    response = client.get("/location/state/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == "Goa"
    assert data[1]["name"] == "Punjab"
    assert data[0]["country_id"] == 1
    assert data[1]["country_id"] == 1


def test_get_state_by_id(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    maharashtra = State(name="Maharashtra", country_id=1)
    session.add(maharashtra)
    session.commit()
    response = client.get("/location/state/1")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Maharashtra"
    assert data["id"] == 1
    assert data["country_id"] == 1
    response = client.get("/location/state/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}


def test_update_state(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    goa = State(name="Goaaa", country_id=1)
    session.add(goa)
    session.commit()
    response = client.put("/location/state/1", json={"name": "Goa"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Goa"
    assert data["id"] == 1
    assert data["name"] != "Goaaa"
    response = client.put("/location/state/2", json={"name": "Goa"})
    assert response.status_code == 404
    assert response.json() == {"detail": "State not found"}
