from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Permission, RolePermission
from app.models.role import Role
from app.tests.utils.location import create_random_state
from app.tests.utils.organization import create_random_organization
from app.tests.utils.role import create_random_role
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import random_email, random_lower_string


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


def test_read_roles_super_admin_sees_all(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test that super_admin can see all roles in the hierarchy.
    """
    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    role_names = [role["name"] for role in content["data"]]

    assert "super_admin" in role_names
    assert "system_admin" in role_names
    assert "state_admin" in role_names
    assert "test_admin" in role_names
    assert "candidate" in role_names


def test_read_roles_system_admin_hierarchy_filtering(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test that system_admin can see system-admin and below roles only.
    Should NOT see super-admin.
    """
    system_admin_role = db.exec(select(Role).where(Role.name == "system_admin")).first()
    assert system_admin_role is not None

    org = create_random_organization(db)
    system_admin_email = random_email()

    system_admin_payload = {
        "email": system_admin_email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": system_admin_role.id,
        "organization_id": org.id,
    }

    resp_admin = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json=system_admin_payload,
    )
    assert resp_admin.status_code == 200

    token_headers = authentication_token_from_email(
        client=client, email=system_admin_email, db=db
    )

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    role_names = [role["name"] for role in content["data"]]

    assert "system_admin" in role_names
    assert "state_admin" in role_names
    assert "test_admin" in role_names
    assert "candidate" in role_names
    assert "super_admin" not in role_names


def test_read_roles_state_admin_hierarchy_filtering(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """
    Test that state_admin can see state-admin and below roles only.
    Should NOT see super-admin or system-admin.
    """
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    org = create_random_organization(db)
    state = create_random_state(db)
    state_admin_email = random_email()

    state_admin_payload = {
        "email": state_admin_email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state.id],
    }

    resp_admin = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json=state_admin_payload,
    )
    assert resp_admin.status_code == 200

    token_headers = authentication_token_from_email(
        client=client, email=state_admin_email, db=db
    )

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=token_headers,
    )

    assert response.status_code == 200
    content = response.json()
    role_names = [role["name"] for role in content["data"]]

    assert "state_admin" in role_names
    assert "test_admin" in role_names
    assert "candidate" in role_names
    assert "super_admin" not in role_names
    assert "system_admin" not in role_names


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
