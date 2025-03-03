import re

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.organization import Organization


def test_create_organization(client: TestClient):
    response = client.post("/organization/", json={"name": "Jay Sangh"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Jay Sangh"
    assert data["id"] == 1


def test_read_organization(client: TestClient, session: Session):
    response = client.get("/organization/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0
    jal_vikas = Organization(name="Jal Vikas")
    session.add(jal_vikas)
    session.commit()
    response = client.get("/organization/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["name"] == "Jal Vikas"
    assert data[0]["id"] == 1


def test_read_organization_by_id(client: TestClient, session: Session):
    response = client.get("/organization/1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
    jal_vikas = Organization(name="Jal Vikas")
    session.add(jal_vikas)
    session.commit()
    response = client.get("/organization/1")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Jal Vikas"
    assert data["id"] == 1


def test_update_organization(client: TestClient, session: Session):
    response = client.put("/organization/1", json={"name": "Jal Vikas"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
    jal_vikas = Organization(name="Jal Vikas")
    session.add(jal_vikas)
    session.commit()
    response = client.put("/organization/1", json={"name": "Jal Vikas Sangh"})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Jal Vikas Sangh"
    assert data["id"] == 1
    assert data["name"] != "Jal Vikas"
    response = client.put("/organization/2", json={"name": "Jal Vikas Sangh"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_delete_organization(client: TestClient, session: Session):
    response = client.delete("/organization/1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
    jal_vikas = Organization(name="Jal Vikas")
    session.add(jal_vikas)
    session.commit()
    response = client.delete("/organization/1")
    data = response.json()
    assert response.status_code == 200
    assert re.search(r"\bdeleted\b", data["message"])
    response = client.delete("/organization/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
