from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.location import Country, District, State


def test_create_district(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    kerala = State(name="Kerala", country_id=1)
    session.add(kerala)
    session.commit()
    response = client.post(
        "/location/district/", json={"name": "Ernakulam", "state_id": 1}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["state_id"] == 1


def test_get_district(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    kerala = State(name="Kerala", country_id=1)
    session.add(kerala)
    ernakulam = District(name="Ernakulam", state_id=1)
    thrissur = District(name="Thrissur", state_id=1)
    session.add(ernakulam)
    session.add(thrissur)
    session.commit()
    response = client.get("/location/district/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == "Ernakulam"
    assert data[1]["name"] == "Thrissur"
    assert data[0]["state_id"] == 1
    assert data[1]["state_id"] == 1


def test_get_district_by_id(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    kerala = State(name="Kerala", country_id=1)
    session.add(kerala)
    ernakulam = District(name="Ernakulam", state_id=1)
    session.add(ernakulam)
    session.commit()
    response = client.get("/location/district/1")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["name"] != "Thrissur"
    assert data["id"] == 1
    assert data["state_id"] == 1
    response = client.get("/location/district/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}


def test_update_district(client: TestClient, session: Session):
    india = Country(name="India")
    session.add(india)
    kerala = State(name="Kerala", country_id=1)
    session.add(kerala)
    session.commit()
    ernakulam = District(name="Ernakulamm", state_id=1)
    session.add(ernakulam)
    session.commit()
    response = client.put("/location/district/1", json={"name": "Ernakulam"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Ernakulam"
    assert data["id"] == 1
    assert data["name"] != "Ernakulamm"
    response = client.put("/location/district/2", json={"name": "Thrissur"})
    assert response.status_code == 404
    assert response.json() == {"detail": "District not found"}
