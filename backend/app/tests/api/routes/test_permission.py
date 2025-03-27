from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.tests.utils.permission import create_random_permission


def test_create_permission(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Foo", "description": "Fighters"}
    response = client.post(
        f"{settings.API_V1_STR}/permissions/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content


def test_read_permission(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    permission = create_random_permission(db)
    response = client.get(
        f"{settings.API_V1_STR}/permissions/{permission.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == permission.name
    assert content["description"] == permission.description
    assert content["id"] == permission.id


def test_read_permission_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/permissions/0",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Permission not found"


# TODO: Fix this once we have permisions in place
# def test_read_permission_not_enough_permissions(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     permission = create_random_permission(db)
#     response = client.get(
#         f"{settings.API_V1_STR}/permissions/{permission.id}",
#         headers=normal_user_token_headers,
#     )
#     assert response.status_code == 400
#     content = response.json()
#     assert content["detail"] == "Not enough permissions"
#


def test_read_permissions(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_permission(db)
    create_random_permission(db)
    response = client.get(
        f"{settings.API_V1_STR}/permissions/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


def test_update_permission(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    permission = create_random_permission(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/permissions/{permission.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["id"] == permission.id


def test_update_permission_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/permissions/0",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Permission not found"


# TODO: Fix this once we have permisions in place
# def test_update_permission_not_enough_permissions(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     permission = create_random_permission(db)
#     data = {"name": "Updated name", "description": "Updated description"}
#     response = client.put(
#         f"{settings.API_V1_STR}/permissions/{permission.id}",
#         headers=normal_user_token_headers,
#         json=data,
#     )
#     assert response.status_code == 400
#     content = response.json()
#     assert content["detail"] == "Not enough permissions"


def test_delete_permission(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    permission = create_random_permission(db)
    response = client.delete(
        f"{settings.API_V1_STR}/permissions/{permission.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Permission deleted successfully"


def test_delete_permission_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/permissions/0",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Permission not found"


# TODO: Fix this once we have permisions in place
# def test_delete_permission_not_enough_permissions(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     permission = create_random_permission(db)
#     response = client.delete(
#         f"{settings.API_V1_STR}/permissions/{permission.id}",
#         headers=normal_user_token_headers,
#     )
#     assert response.status_code == 400
#     content = response.json()
#     assert content["detail"] == "Not enough permissions"
