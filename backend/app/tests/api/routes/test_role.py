from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Permission, Role, RolePermission
from app.tests.utils.role import create_random_role
from app.tests.utils.user import get_current_user_data, get_user_token
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

    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
    role = create_random_role(db, organization_id=caller_org_id)

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
    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
    role = create_random_role(db, organization_id=caller_org_id)
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
    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
    role = create_random_role(db, organization_id=caller_org_id)
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
    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
    role = create_random_role(db, organization_id=caller_org_id)
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


def test_read_roles_super_admin_sees_all_roles(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test that Super Admin can see all system roles."""
    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()

    # super admin should see all roles except candidate
    role_names = [role["name"] for role in content["data"]]
    expected_roles = {
        "super_admin",
        "system_admin",
        "state_admin",
        "test_admin",
    }
    assert expected_roles.issubset(set(role_names))
    assert "candidate" not in role_names


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

    # they should not have access to super_admin or candidate roles
    assert "super_admin" not in role_names
    assert "candidate" not in role_names


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

    # they should not see higher level or candidate roles
    assert "super_admin" not in role_names
    assert "system_admin" not in role_names
    assert "candidate" not in role_names


def test_read_roles_test_admin_filtered(client: TestClient, db: Session) -> None:
    """Test that test_admin sees only Test Admin and below."""

    # get auth headers for test admin user
    headers = get_user_token(db=db, role="test_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()

    role_names = [role["name"] for role in content["data"]]

    # Test admin should see only their own role
    assert "test_admin" in role_names

    # they should not see higher level or candidate roles
    assert "super_admin" not in role_names
    assert "system_admin" not in role_names
    assert "state_admin" not in role_names
    assert "candidate" not in role_names


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


def test_create_role_stamps_callers_own_org(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """POST /roles/ always attaches the caller's own organization, never
    something the client could smuggle in."""
    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
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
    assert response.json()["organization_id"] == caller_org_id


def test_role_actions_scoped_to_callers_own_org(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """A caller (even one with role-management permission) cannot see, edit,
    hide, or delete a role that belongs to a different organization."""
    other_org_headers = get_user_token(db=db, role="test_admin")
    other_org_role_id = get_current_user_data(client, other_org_headers)["role_id"]

    read_response = client.get(
        f"{settings.API_V1_STR}/roles/{other_org_role_id}",
        headers=superuser_token_headers,
    )
    assert read_response.status_code == 404

    update_response = client.put(
        f"{settings.API_V1_STR}/roles/{other_org_role_id}",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "description": random_lower_string(),
            "label": random_lower_string(),
        },
    )
    assert update_response.status_code == 404

    patch_response = client.patch(
        f"{settings.API_V1_STR}/roles/{other_org_role_id}",
        headers=superuser_token_headers,
        params={"is_active": False},
    )
    assert patch_response.status_code == 404

    delete_response = client.delete(
        f"{settings.API_V1_STR}/roles/{other_org_role_id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 404


def test_super_admin_role_is_protected_from_modification(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
    super_admin_role = db.exec(
        select(Role).where(
            Role.name == "super_admin", Role.organization_id == caller_org_id
        )
    ).first()
    assert super_admin_role is not None

    update_response = client.put(
        f"{settings.API_V1_STR}/roles/{super_admin_role.id}",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "description": random_lower_string(),
            "label": random_lower_string(),
        },
    )
    assert update_response.status_code == 403

    patch_response = client.patch(
        f"{settings.API_V1_STR}/roles/{super_admin_role.id}",
        headers=superuser_token_headers,
        params={"is_active": False},
    )
    assert patch_response.status_code == 403

    delete_response = client.delete(
        f"{settings.API_V1_STR}/roles/{super_admin_role.id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 403


def test_toggle_permission_scoped_to_one_org(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """The worked example from the issue: removing read_test from one org's
    test_admin must not affect another org's test_admin."""
    read_test_permission = db.exec(
        select(Permission).where(Permission.name == "read_test")
    ).first()
    assert read_test_permission is not None

    caller_org_id = get_current_user_data(client, superuser_token_headers)[
        "organization_id"
    ]
    org_a_test_admin = db.exec(
        select(Role).where(
            Role.name == "test_admin", Role.organization_id == caller_org_id
        )
    ).first()
    assert org_a_test_admin is not None

    other_org_headers = get_user_token(db=db, role="test_admin")
    other_org_user = get_current_user_data(client, other_org_headers)
    org_b_test_admin_id = other_org_user["role_id"]

    other_permission_ids = list(
        db.exec(
            select(RolePermission.permission_id).where(
                RolePermission.role_id == org_a_test_admin.id,
                RolePermission.permission_id != read_test_permission.id,
            )
        ).all()
    )

    response = client.put(
        f"{settings.API_V1_STR}/roles/{org_a_test_admin.id}",
        headers=superuser_token_headers,
        json={
            "name": org_a_test_admin.name,
            "description": org_a_test_admin.description,
            "label": org_a_test_admin.label,
            "permissions": other_permission_ids,
        },
    )
    assert response.status_code == 200
    assert read_test_permission.id not in response.json()["permissions"]

    org_b_permission_ids = db.exec(
        select(RolePermission.permission_id).where(
            RolePermission.role_id == org_b_test_admin_id
        )
    ).all()
    assert read_test_permission.id in org_b_permission_ids
