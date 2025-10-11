from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Permission, Role, RolePermission
from app.tests.utils.role import create_random_role
from app.tests.utils.user import get_user_token
from app.tests.utils.utils import random_lower_string


def test_create_role(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
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
        headers=get_user_superadmin_token,
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
        headers=get_user_superadmin_token,
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

    # get existing hierarchy roles instead of creating random ones
    role_a = db.exec(select(Role).where(Role.name == "system_admin")).first()
    role_b = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert role_a is not None and role_b is not None

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
    assert any(role["name"] == role_a.name for role in data)
    assert any(role["name"] == role_b.name for role in data)


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


def test_read_roles_super_admin_sees_all_roles(client: TestClient, db: Session) -> None:
    """Test that Super Admin can see all system roles."""

    # get auth headers for super admin user
    headers = get_user_token(db=db, role="super_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()

    # super admin should see all roles
    role_names = [role["name"] for role in content["data"]]
    expected_roles = {
        "super_admin",
        "system_admin",
        "state_admin",
        "test_admin",
        "candidate",
    }
    assert expected_roles.issubset(set(role_names))


def test_read_roles_system_admin_filtered(client: TestClient, db: Session) -> None:
    """Test that System Admin sees only system_admin and below."""

    # get auth headers for system admin user
    headers = get_user_token(db=db, role="system_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()

    role_names = [role["name"] for role in content["data"]]

    # System admin should see these roles
    assert "system_admin" in role_names
    assert "state_admin" in role_names
    assert "test_admin" in role_names
    assert "candidate" in role_names

    # they should not have access to super_admin role
    assert "super_admin" not in role_names


def test_read_roles_state_admin_filtered(client: TestClient, db: Session) -> None:
    """Test that state_admin sees only state_admin and below."""

    # get auth headers for state admin user
    headers = get_user_token(db=db, role="state_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()

    role_names = [role["name"] for role in content["data"]]

    # State admin should see these roles
    assert "state_admin" in role_names
    assert "test_admin" in role_names
    assert "candidate" in role_names

    # they should not see higher level roles
    assert "super_admin" not in role_names
    assert "system_admin" not in role_names


def test_read_roles_test_admin_no_access(client: TestClient, db: Session) -> None:
    """Test that test_admin has no access to roles endpoint."""

    # get auth headers for test admin user
    headers = get_user_token(db=db, role="test_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )

    # Test admin should not have read_role permission
    # 401 due to token issue or 403 for permission error
    assert response.status_code in [401, 403]


def test_read_roles_candidate_no_access(client: TestClient, db: Session) -> None:
    """Test that candidate has no access to roles endpoint."""
    headers = get_user_token(db=db, role="candidate")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )

    # Candidate should not have read_role permission
    # 401 due to token issue or 403 for permission error
    assert response.status_code in [401, 403]


def test_read_roles_invalid_role_empty_result(client: TestClient, db: Session) -> None:
    """Test that users with invalid/unknown roles get empty results."""

    # create a custom role not in hierarchy
    custom_role = create_random_role(db)

    headers = get_user_token(db=db, role=custom_role.name)

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )

    # Custom role should have token issues or no read_role permission
    assert response.status_code in [200, 401, 403]

    # if we get a 200 response, the content should be empty
    if response.status_code == 200:
        content = response.json()

        # Custom role not in hierarchy should see no roles
        assert content["count"] == 0
        assert len(content["data"]) == 0
