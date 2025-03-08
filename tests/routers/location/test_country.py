from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import Country


def test_create_country(client: TestClient):
    response = client.post("/location/country/", json={"name": "China"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "China"


def test_get_country(client: TestClient, session: Session):
    dubai = Country(name="Dubai")
    austria = Country(name="Austria")
    session.add(dubai)
    session.add(austria)
    session.commit()
    response = client.get("/location/country/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == dubai.name
    assert data[1]["name"] == austria.name


def test_get_country_by_id(client: TestClient, session: Session):
    srilanka = Country(name="Srilanka")
    session.add(srilanka)
    session.commit()
    response = client.get(f"/location/country/{srilanka.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == srilanka.name
    assert data["id"] == srilanka.id
    response = client.get("/location/country/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}


def test_update_country(client: TestClient, session: Session):
    australia = Country(name="Australiaaa")
    session.add(australia)
    session.commit()
    response = client.put(
        f"/location/country/{australia.id}", json={"name": "Australia"}
    )
    data = response.json()
    print("data-->", data)
    print("auss->", australia)
    assert response.status_code == 200
    assert data["name"] == "Australia"
    assert data["id"] == australia.id
    assert data["name"] != "Australiaaa"
    response = client.put("/location/country/2", json={"name": "Australia"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Country not found"}
