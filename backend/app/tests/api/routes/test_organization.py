from fastapi import status
from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.organization import Organization
from app.tests.utils.utils import random_lower_string


def test_create_organization(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    get_user_candidate_token: dict[str, str],
) -> None:
    name = random_lower_string()
    description = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={
            "name": name,
            "description": description,
        },
        headers=get_user_superadmin_token,
    )
    print("This is link->", f"{settings.API_V1_STR}/organization/")
    print("response-->", response)
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == name
    assert data["description"] == description
    assert "id" in data
    assert data["is_active"] is None
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={
            "name": name,
            "description": description,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["detail"] == "User Not Permitted"


def test_read_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
    get_user_candidate_token: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200

    jal_vikas = Organization(name=random_lower_string())
    maha_vikas = Organization(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add(jal_vikas)
    db.add(maha_vikas)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    jal_vikas_index = len(data) - 2
    maha_vikas_index = len(data) - 1
    assert data[jal_vikas_index]["name"] == jal_vikas.name
    assert data[jal_vikas_index]["description"] is None
    assert data[jal_vikas_index]["id"] == jal_vikas.id
    assert data[jal_vikas_index]["is_active"] is None

    assert data[maha_vikas_index]["name"] == maha_vikas.name
    assert data[maha_vikas_index]["description"] == maha_vikas.description
    assert data[maha_vikas_index]["id"] == maha_vikas.id
    assert data[maha_vikas_index]["is_active"] is None
    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == 200


def test_read_organization_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    jal_vikas = Organization(name=random_lower_string())
    maha_vikas = Organization(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add(jal_vikas)
    db.add(maha_vikas)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] is None

    response = client.get(
        f"{settings.API_V1_STR}/organization/{maha_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maha_vikas.name
    assert data["id"] == maha_vikas.id
    assert data["description"] == maha_vikas.description
    assert data["is_active"] is None


def test_update_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    initial_name = random_lower_string()
    updated_name = random_lower_string()
    inital_description = random_lower_string()
    updated_description = random_lower_string()
    jal_vikas = Organization(name=initial_name)
    db.add(jal_vikas)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": updated_name, "description": None},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["id"] == jal_vikas.id
    assert data["name"] != initial_name
    assert data["description"] is None

    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": jal_vikas.name, "description": inital_description},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] == inital_description

    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": jal_vikas.name, "description": updated_description},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] == updated_description


def test_visibility_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    jal_vikas = Organization(name=random_lower_string())
    db.add(jal_vikas)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["is_active"] is True
    assert data["is_active"] is not False and not None

    response = client.patch(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        params={"is_active": False},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == jal_vikas.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None


def test_delete_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/organization/0",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
    jal_vikas = Organization(name=random_lower_string())
    db.add(jal_vikas)
    db.commit()
    assert jal_vikas.is_deleted is False
    response = client.delete(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert "delete" in data["message"]

    response = client.get(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 404
    assert "id" not in data
