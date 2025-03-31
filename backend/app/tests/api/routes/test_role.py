from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Permission, RolePermission
from app.tests.utils.role import create_random_role
from app.tests.utils.utils import random_lower_string


def test_create_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    permission = Permission(
        name=random_lower_string(), description=random_lower_string()
    )

    db.add(permission)
    db.commit()
    db.refresh(permission)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
        "permissions": [permission.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert content["permissions"] == [permission.id]

    role_permission_link = db.exec(
        select(RolePermission).where(RolePermission.role_id == content["id"])
    ).all()

    assert role_permission_link[0].permission_id == permission.id
    assert role_permission_link[0].role_id == content["id"]
    assert hasattr(role_permission_link[0], "id")

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert content["permissions"] == []


def test_read_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    permission_a = Permission(
        name=random_lower_string(), description=random_lower_string()
    )

    permission_b = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add_all([permission_a, permission_b])

    db.commit()

    role = create_random_role(db)

    role_permission_a = RolePermission(role_id=role.id, permission_id=permission_a.id)
    role_permission_b = RolePermission(role_id=role.id, permission_id=permission_b.id)
    db.add_all([role_permission_a, role_permission_b])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content_get = response.json()
    assert content_get["name"] == role.name
    assert content_get["description"] == role.description
    assert content_get["label"] == role.label
    assert content_get["id"] == role.id
    assert content_get["permissions"] == [permission_a.id, permission_b.id]


def test_read_role_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/roles/-1",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Role not found"


# TODO: Fix this once we have permisions in place
# def test_read_role_not_enough_permissions(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     role = create_random_role(db)
#     response = client.get(
#         f"{settings.API_V1_STR}/roles/{role.id}",
#         headers=normal_user_token_headers,
#     )
#     assert response.status_code == 400
#     content = response.json()
#     assert content["detail"] == "Not enough permissions"
#


def test_read_roles(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    permission_a = Permission(
        name=random_lower_string(), description=random_lower_string()
    )

    permission_b = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add_all([permission_a, permission_b])

    db.commit()

    role_a = create_random_role(db)
    role_b = create_random_role(db)

    role_permission_aa = RolePermission(
        role_id=role_a.id, permission_id=permission_a.id
    )
    role_permission_ab = RolePermission(
        role_id=role_a.id, permission_id=permission_b.id
    )
    role_permission_ba = RolePermission(
        role_id=role_b.id, permission_id=permission_a.id
    )
    role_permission_bb = RolePermission(
        role_id=role_b.id, permission_id=permission_b.id
    )
    db.add_all(
        [role_permission_aa, role_permission_ab, role_permission_ba, role_permission_bb]
    )
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2

    data = content["data"]

    role_a_data = data[len(data) - 2]
    role_b_data = data[len(data) - 1]

    assert role_a_data["name"] == role_a.name
    assert role_a_data["description"] == role_a.description
    assert role_a_data["label"] == role_a.label
    assert role_a_data["permissions"] == [permission_a.id, permission_b.id]

    assert role_b_data["name"] == role_b.name
    assert role_b_data["description"] == role_b.description
    assert role_b_data["label"] == role_b.label
    assert role_b_data["permissions"] == [permission_a.id, permission_b.id]


def test_update_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(db)
    permission_a = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    permission_b = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    permission_c = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add_all([permission_a, permission_b, permission_c])
    db.commit()

    role_permission_a = RolePermission(role_id=role.id, permission_id=permission_a.id)
    role_permission_b = RolePermission(role_id=role.id, permission_id=permission_b.id)
    db.add_all([role_permission_a, role_permission_b])
    db.commit()

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
        "permissions": [permission_b.id, permission_c.id],
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["label"] == data["label"]
    assert content["id"] == role.id
    assert content["permissions"] == [permission_b.id, permission_c.id]

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
        "permissions": [permission_a.id],
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["label"] == data["label"]
    assert content["id"] == role.id
    assert content["permissions"] == [permission_a.id]
    assert content["permissions"] not in [permission_b.id, permission_c.id]

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["label"] == data["label"]
    assert content["id"] == role.id
    assert content["permissions"] == []
    assert content["permissions"] not in [
        permission_a.id,
        permission_b.id,
        permission_c.id,
    ]


def test_update_role_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/-1",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Role not found"


def test_visibility_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(db)
    data = {"is_active": False}
    response = client.patch(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        params=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["is_active"] is False
    assert content["name"] == role.name
    assert content["description"] == role.description
    assert content["label"] == role.label
    assert content["permissions"] == []
    response = client.patch(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        params={"is_active": True},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["is_active"] is True

    response = client.patch(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["is_active"] is True


# TODO: Fix this once we have permisions in place
# def test_update_role_not_enough_permissions(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     role = create_random_role(db)
#     data = {"name": "Updated name", "description": "Updated description"}
#     response = client.put(
#         f"{settings.API_V1_STR}/roles/{role.id}",
#         headers=normal_user_token_headers,
#         json=data,
#     )
#     assert response.status_code == 400
#     content = response.json()
#     assert content["detail"] == "Not enough permissions"


def test_delete_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(db)
    response = client.delete(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Role deleted successfully"

    response = client.delete(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Role not found"


def test_delete_role_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/roles/0",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Role not found"


# TODO: Fix this once we have permisions in place
# def test_delete_role_not_enough_permissions(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     role = create_random_role(db)
#     response = client.delete(
#         f"{settings.API_V1_STR}/roles/{role.id}",
#         headers=normal_user_token_headers,
#     )
#     assert response.status_code == 400
#     content = response.json()
#     assert content["detail"] == "Not enough permissions"
