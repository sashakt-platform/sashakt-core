from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import (
    Country,
    District,
    State,
)


def test_create_district(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    kerala = State(name="Kerala", country_id=india.id)
    session.add(kerala)
    session.commit()
    response = client.post(
        "/location/district/", json={"name": "Ernakulam", "state_id": kerala.id}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["state_id"] == kerala.id


def test_get_district(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    kerala = State(name="Kerala", country_id=india.id)
    session.add(kerala)
    session.commit()
    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    thrissur = District(name="Thrissur", state_id=kerala.id)
    session.add(ernakulam)
    session.add(thrissur)
    session.commit()
    response = client.get("/location/district/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == ernakulam.name
    assert data[1]["name"] == thrissur.name
    assert data[0]["state_id"] == kerala.id
    assert data[1]["state_id"] == kerala.id


def test_get_district_by_id(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    kerala = State(name="Kerala", country_id=india.id)
    session.add(kerala)
    session.commit()
    ernakulam = District(name="Ernakulam", state_id=kerala.id)
    session.add(ernakulam)
    session.commit()
    response = client.get(f"/location/district/{ernakulam.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["name"] != "Thrissur"
    assert data["id"] == ernakulam.id
    assert data["state_id"] == ernakulam.state_id
    assert data["state_id"] == kerala.id
    response = client.get("/location/district/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


def test_update_district(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    session.commit()
    kerala = State(name="Kerala", country_id=india.id)
    session.add(kerala)
    andhra_pradesh = State(name="Andhra Pradesh", country_id=india.id)
    session.add(andhra_pradesh)
    session.commit()
    ernakulam = District(name="Ernakulamm", state_id=kerala.id)
    session.add(ernakulam)
    session.commit()
    response = client.put(
        f"/location/district/{ernakulam.id}",
        json={"name": "Ernakulam", "state_id": kerala.id},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["id"] == 1
    assert data["name"] != "Ernakulamm"

    response = client.put(
        f"/location/district/{ernakulam.id}",
        json={"name": ernakulam.name, "state_id": andhra_pradesh.id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ernakulam"
    assert data["id"] == ernakulam.id
    assert data["state_id"] == andhra_pradesh.id
    assert data["state_id"] != kerala.id

    response = client.put(
        "/location/district/2", json={"name": "Thrissur", "state_id": kerala.id}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}
