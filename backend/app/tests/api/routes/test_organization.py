from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.organization import Organization


def test_create_organization(client: TestClient) -> None:
    name = "Jay Sangh"
    description = "It is a non profit organization"
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={"name": name, "description": description},
    )
    print("This is link->", f"{settings.API_V1_STR}/organization/")
    print("response-->", response)
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == name
    assert data["description"] == description
    assert "id" in data
    assert data["is_active"] is None


def test_read_organization(client: TestClient, db: SessionDep) -> None:
    response = client.get(f"{settings.API_V1_STR}/organization/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    jal_vikas = Organization(name="Jal Vikas")
    maha_vikas = Organization(name="Maha Vikas", description="Lets Work for Humanity")
    db.add(jal_vikas)
    db.add(maha_vikas)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/organization/")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["name"] == jal_vikas.name
    assert data[0]["description"] is None
    assert data[0]["id"] == jal_vikas.id
    assert data[0]["is_active"] is None

    assert data[1]["name"] == maha_vikas.name
    assert data[1]["description"] == maha_vikas.description
    assert data[1]["id"] == maha_vikas.id


def test_read_organization_by_id(client: TestClient, db: SessionDep) -> None:
    response = client.get(f"{settings.API_V1_STR}/organization/1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}

    jal_vikas = Organization(name="Jal Vikas")
    maha_vikas = Organization(name="Maha Vikas", description="Lets Work for Humanity")
    db.add(jal_vikas)
    db.add(maha_vikas)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/organization/{jal_vikas.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] is None

    response = client.get(f"{settings.API_V1_STR}/organization/{maha_vikas.id}")
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maha_vikas.name
    assert data["id"] == maha_vikas.id
    assert data["description"] == maha_vikas.description
    assert data["is_active"] is None


def test_update_organization(client: TestClient, db: Session) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/organization/1",
        json={"name": "Jal Vikas", "description": None},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}

    jal_vikas = Organization(name="Jal Vikas")
    db.add(jal_vikas)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": "Jal Vikas Sangh", "description": None},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Jal Vikas Sangh"
    assert data["id"] == jal_vikas.id
    assert data["name"] != "Jal Vikas"
    assert data["description"] is None

    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": jal_vikas.name, "description": "Humanity First!!"},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] == "Humanity First!!"

    response = client.put(
        f"{settings.API_V1_STR}/organization/2",
        json={"name": "Jal Vikas Sangh", "description": "Serve the Poor"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_visibility_organization(client: TestClient, db: Session) -> None:
    jal_vikas = Organization(name="Jal Vikas")
    db.add(jal_vikas)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}", params={"is_active": True}
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["is_active"] is True
    assert data["is_active"] is not False and not None

    response = client.patch(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        params={"is_active": False},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == jal_vikas.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None


def test_delete_organization(client: TestClient, db: Session) -> None:
    response = client.delete(f"{settings.API_V1_STR}/organization/1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
    jal_vikas = Organization(name="Jal Vikas")
    db.add(jal_vikas)
    db.commit()
    assert jal_vikas.is_deleted is False
    response = client.delete(f"{settings.API_V1_STR}/organization/{jal_vikas.id}")
    data = response.json()
    assert response.status_code == 200

    print("is_deleted->>", data["is_deleted"])
    assert data["is_deleted"] is True

    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    response = client.delete(f"{settings.API_V1_STR}/organization/2")
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
