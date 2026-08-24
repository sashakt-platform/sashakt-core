from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import crud
from app.core.config import settings
from app.core.roles import init_org_roles
from app.models import (
    Organization,
    Permission,
    Role,
    RoleLocationLevel,
    RolePermission,
    UserCreate,
)
from app.tests.utils.organization import create_random_organization
from app.tests.utils.role import create_random_role, get_org_role
from app.tests.utils.user import (
    get_current_user_data,
    get_user_token,
    get_user_token_for_org,
)
from app.tests.utils.utils import random_email, random_lower_string


def _org_id(client: TestClient, token: dict[str, str]) -> int:
    org_id = get_current_user_data(client, token)["organization_id"]
    assert isinstance(org_id, int)
    return org_id


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


def test_create_role_with_duplicate_name_fails(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    """Creating a role whose name already exists in the caller's organization
    should return a clean 400 error, not an unhandled IntegrityError."""
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

    duplicate_data = {
        "name": data["name"],
        "description": random_lower_string(),
        "label": random_lower_string(),
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=get_user_superadmin_token,
        json=duplicate_data,
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "A role with this name already exists in your organization"
    )


def test_create_role_with_location_scope(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
        "location_scope": "state",
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["location_scope"] == "state"

    db_role = db.exec(select(Role).where(Role.id == content["id"])).first()
    assert db_role is not None
    assert db_role.location_scope == "state"

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
        "location_scope": "district",
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["location_scope"] == "district"

    db_role = db.exec(select(Role).where(Role.id == content["id"])).first()
    assert db_role is not None
    assert db_role.location_scope == "district"

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
    assert content["location_scope"] is None

    db_role = db.exec(select(Role).where(Role.id == content["id"])).first()
    assert db_role is not None
    assert db_role.location_scope is None


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

    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )

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
    client: TestClient, get_user_systemadmin_token: dict[str, str], db: Session
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
    org_id = _org_id(client, get_user_systemadmin_token)
    role_a = get_org_role(db, org_id, "system_admin")
    role_b = get_org_role(db, org_id, "state_admin")

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
        headers=get_user_systemadmin_token,
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
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
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

    original_name = role.name

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
    assert content["name"] == original_name
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
    assert content["name"] == original_name
    assert content["description"] == data["description"]
    assert content["label"] == data["label"]
    assert content["id"] == role.id
    assert content["permissions"] == [permission_a.id]
    assert content["permissions"] not in [permission_b.id, permission_c.id]

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
        "permissions": [],
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == original_name
    assert content["description"] == data["description"]
    assert content["label"] == data["label"]
    assert content["id"] == role.id
    assert content["permissions"] == []


def test_update_role_cannot_change_name(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Regression test: a PUT payload with a different name must not rename
    the role - name is immutable once a role is created."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    original_name = role.name

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
    }
    assert data["name"] != original_name

    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == original_name
    assert content["description"] == data["description"]
    assert content["label"] == data["label"]

    db.refresh(role)
    assert role.name == original_name


def test_update_role_partial_put_omits_permissions_unchanged(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Regression test: a PUT payload that omits permissions must leave the
    existing permission assignments untouched, not clear them."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    permission_a = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    permission_b = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add_all([permission_a, permission_b])
    db.commit()
    db.refresh(permission_a)
    db.refresh(permission_b)
    assert permission_a.id is not None
    assert permission_b.id is not None

    role_permission_a = RolePermission(role_id=role.id, permission_id=permission_a.id)
    role_permission_b = RolePermission(role_id=role.id, permission_id=permission_b.id)
    db.add_all([role_permission_a, role_permission_b])
    db.commit()

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "label": random_lower_string(),
    }
    assert "permissions" not in data

    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert sorted(content["permissions"]) == sorted([permission_a.id, permission_b.id])

    stored = db.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    ).all()
    assert sorted(stored) == sorted([permission_a.id, permission_b.id])


def test_update_role_empty_permissions_list_clears_them(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """An explicit permissions: [] in the payload (unlike omitting the key)
    clears all existing permission assignments."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    permission_a = Permission(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add(permission_a)
    db.commit()

    role_permission_a = RolePermission(role_id=role.id, permission_id=permission_a.id)
    db.add(role_permission_a)
    db.commit()

    data: dict[str, Any] = {
        "name": role.name,
        "description": role.description,
        "label": role.label,
        "permissions": [],
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["permissions"] == []

    stored = db.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    ).all()
    assert stored == []


def test_update_role_partial_put_omits_visible_to_roles_unchanged(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Regression test: a PUT payload that omits visible_to_roles must not
    touch the allowed_roles of any other role."""
    org_id = _org_id(client, superuser_token_headers)
    custom_role = create_random_role(db, organization_id=org_id)
    system_admin_role = get_org_role(db, org_id, "system_admin")

    response = client.put(
        f"{settings.API_V1_STR}/roles/{custom_role.id}",
        headers=superuser_token_headers,
        json={
            "name": custom_role.name,
            "label": custom_role.label,
            "visible_to_roles": ["system_admin"],
        },
    )
    assert response.status_code == 200
    db.refresh(system_admin_role)
    granted_allowed_roles = list(system_admin_role.allowed_roles)
    assert custom_role.name in granted_allowed_roles

    data = {
        "name": custom_role.name,
        "description": custom_role.description,
        "label": custom_role.label,
    }
    assert "visible_to_roles" not in data

    response = client.put(
        f"{settings.API_V1_STR}/roles/{custom_role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200

    db.refresh(system_admin_role)
    assert list(system_admin_role.allowed_roles) == granted_allowed_roles


def test_update_role_location_scope(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    assert role.location_scope is None

    data = {
        "name": role.name,
        "description": role.description,
        "label": role.label,
        "location_scope": "state",
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["location_scope"] == "state"

    db.refresh(role)
    assert role.location_scope == "state"

    data = {
        "name": role.name,
        "description": role.description,
        "label": role.label,
        "location_scope": "district",
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["location_scope"] == "district"

    db.refresh(role)
    assert role.location_scope == "district"


def test_update_role_partial_put_omits_location_scope_unchanged(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Regression test: a PUT payload that omits location_scope must leave the
    existing value untouched, since the route relies on exclude_unset=True."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    role.location_scope = RoleLocationLevel.STATE
    db.add(role)
    db.commit()
    db.refresh(role)
    assert role.location_scope == "state"

    data = {
        "name": role.name,
        "description": role.description,
        "label": role.label,
    }
    assert "location_scope" not in data

    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["location_scope"] == "state"

    db.refresh(role)
    assert role.location_scope == "state"


def test_update_role_explicit_null_location_scope_clears_it(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """An explicit location_scope: null in the payload (unlike omitting the
    key) is picked up by exclude_unset=True and clears the existing value."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    role.location_scope = RoleLocationLevel.STATE
    db.add(role)
    db.commit()
    db.refresh(role)
    assert role.location_scope == "state"

    data = {
        "name": role.name,
        "description": role.description,
        "label": role.label,
        "location_scope": None,
    }
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["location_scope"] is None

    db.refresh(role)
    assert role.location_scope is None


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
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
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
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
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


def test_delete_role_revokes_visibility_grants(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Deleting a role must scrub its name out of every other role's
    allowed_roles - otherwise the grant becomes a stale string reference
    that lingers in the hierarchy forever."""
    org_id = _org_id(client, superuser_token_headers)
    system_admin_role = get_org_role(db, org_id, "system_admin")

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    new_role_id = response.json()["id"]
    new_role_name = response.json()["name"]

    db.refresh(system_admin_role)
    assert new_role_name in system_admin_role.allowed_roles

    response = client.delete(
        f"{settings.API_V1_STR}/roles/{new_role_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    db.refresh(system_admin_role)
    assert new_role_name not in system_admin_role.allowed_roles
    assert db.get(Role, new_role_id) is None


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


def test_delete_restricted_role_is_blocked(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Seeded roles have is_restricted=True and can never be deleted."""
    org_id = _org_id(client, superuser_token_headers)
    role = get_org_role(db, org_id, "test_admin")

    response = client.delete(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "This role is restricted and cannot be deleted"
    assert db.get(Role, role.id) is not None


def test_delete_role_still_assigned_to_a_user_is_blocked(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """A custom (non-restricted) role that still has a user assigned to it
    cannot be deleted - the FK constraint should surface as a 400, not a 500."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    org = create_random_organization(db)
    assert role.id is not None
    assert org.id is not None
    crud.create_user(
        session=db,
        user_create=UserCreate(
            email=random_email(),
            password=random_lower_string(),
            full_name=random_lower_string(),
            phone=random_lower_string(),
            role_id=role.id,
            organization_id=org.id,
        ),
    )

    response = client.delete(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Cannot delete a role that is still assigned to users"
    )
    assert db.get(Role, role.id) is not None


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
    """Test that Super Admin only sees roles listed in its own allowed_roles."""

    # get auth headers for super admin user
    headers = get_user_token(db=db, role="super_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()

    # super_admin.allowed_roles is seeded to just ["system_admin"]
    role_names = {role["name"] for role in content["data"]}
    assert role_names == {"system_admin"}


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


def test_create_role_updates_allowed_roles_on_target_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    org_id = _org_id(client, superuser_token_headers)
    system_admin_role = get_org_role(db, org_id, "system_admin")
    original_allowed_roles = set(system_admin_role.allowed_roles)

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    new_role_name = response.json()["name"]

    assert set(system_admin_role.allowed_roles) == original_allowed_roles | {
        new_role_name
    }


def test_get_roles_includes_role_visible_to_system_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    org_id = _org_id(client, superuser_token_headers)
    systemadmin_token = get_user_token_for_org(
        db=db, organization_id=org_id, role="system_admin"
    )
    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    new_role_name = response.json()["name"]

    list_response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=systemadmin_token,
    )
    assert list_response.status_code == 200
    role_names = {role["name"] for role in list_response.json()["data"]}
    assert new_role_name in role_names


def test_create_user_with_new_custom_role(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    org_id = _org_id(client, superuser_token_headers)
    systemadmin_token = get_user_token_for_org(
        db=db, organization_id=org_id, role="system_admin"
    )
    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    new_role_id = response.json()["id"]

    user_response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=systemadmin_token,
        json={
            "email": random_email(),
            "password": random_lower_string(),
            "full_name": random_lower_string(),
            "phone": random_lower_string(),
            "role_id": new_role_id,
            "organization_id": org_id,
        },
    )
    assert user_response.status_code == 200
    assert user_response.json()["role_id"] == new_role_id


def test_create_role_without_visibility_grants_system_admin_by_default(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """A newly created role is visible to system_admin by default, even
    when visible_to_roles is omitted entirely."""
    org_id = _org_id(client, superuser_token_headers)
    system_admin_role = get_org_role(db, org_id, "system_admin")

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["visible_to_roles"] == ["system_admin"]

    db.refresh(system_admin_role)
    assert response.json()["name"] in system_admin_role.allowed_roles


def test_create_role_with_unknown_visible_to_role_fails(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role_name = random_lower_string()
    data = {
        "name": role_name,
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["not_a_real_role"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 400
    assert "not_a_real_role" in response.json()["detail"]
    assert db.exec(select(Role).where(Role.name == role_name)).first() is None


def test_create_role_with_unknown_allowed_role_fails(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role_name = random_lower_string()
    data = {
        "name": role_name,
        "label": random_lower_string(),
        "description": random_lower_string(),
        "allowed_roles": ["not_a_real_role"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 400
    assert "not_a_real_role" in response.json()["detail"]
    assert db.exec(select(Role).where(Role.name == role_name)).first() is None


def test_create_role_allowed_roles_starts_empty(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["allowed_roles"] == []


def test_create_role_accepts_allowed_roles_in_payload(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """allowed_roles says which roles this new role can itself assign/see -
    it's a direct input, independent of visible_to_roles."""
    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "allowed_roles": ["test_admin", "state_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    assert response.json()["allowed_roles"] == ["test_admin", "state_admin"]

    role = db.exec(select(Role).where(Role.name == data["name"])).first()
    assert role is not None
    assert role.allowed_roles == ["test_admin", "state_admin"]


def test_update_role_accepts_allowed_roles_in_payload(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """allowed_roles says which roles this role can itself assign/see - it's
    a direct input, independent of visible_to_roles."""
    role = create_random_role(
        db, organization_id=_org_id(client, superuser_token_headers)
    )
    assert role.allowed_roles == []

    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json={
            "name": role.name,
            "label": role.label,
            "allowed_roles": ["test_admin", "state_admin"],
        },
    )
    assert response.status_code == 200
    assert response.json()["allowed_roles"] == ["test_admin", "state_admin"]

    db.refresh(role)
    assert role.allowed_roles == ["test_admin", "state_admin"]


def test_update_role_updates_allowed_roles_on_target_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    org_id = _org_id(client, superuser_token_headers)
    custom_role = create_random_role(db, organization_id=org_id)
    system_admin_role = get_org_role(db, org_id, "system_admin")
    original_allowed_roles = set(system_admin_role.allowed_roles)

    response = client.put(
        f"{settings.API_V1_STR}/roles/{custom_role.id}",
        headers=superuser_token_headers,
        json={
            "name": custom_role.name,
            "label": custom_role.label,
            "visible_to_roles": ["system_admin"],
        },
    )
    assert response.status_code == 200

    db.refresh(system_admin_role)
    assert set(system_admin_role.allowed_roles) == original_allowed_roles | {
        custom_role.name
    }


def test_create_role_with_allowed_roles_and_visible_to_roles(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """allowed_roles (what this new role can itself assign/see) and
    visible_to_roles (which existing roles should be granted visibility of
    this new role) are independent and can both be set in one request."""
    org_id = _org_id(client, superuser_token_headers)
    system_admin_role = get_org_role(db, org_id, "system_admin")
    original_allowed_roles = set(system_admin_role.allowed_roles)

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "allowed_roles": ["test_admin", "state_admin"],
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    new_role_name = content["name"]
    assert content["allowed_roles"] == ["test_admin", "state_admin"]

    db.refresh(system_admin_role)
    assert set(system_admin_role.allowed_roles) == original_allowed_roles | {
        new_role_name
    }


def test_update_role_with_allowed_roles_and_visible_to_roles(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """allowed_roles (what this role can itself assign/see) and
    visible_to_roles (which existing roles should be granted visibility of
    this role) are independent and can both be set in one request."""
    org_id = _org_id(client, superuser_token_headers)
    custom_role = create_random_role(db, organization_id=org_id)
    system_admin_role = get_org_role(db, org_id, "system_admin")
    original_allowed_roles = set(system_admin_role.allowed_roles)

    response = client.put(
        f"{settings.API_V1_STR}/roles/{custom_role.id}",
        headers=superuser_token_headers,
        json={
            "name": custom_role.name,
            "label": custom_role.label,
            "allowed_roles": ["test_admin", "state_admin"],
            "visible_to_roles": ["system_admin"],
        },
    )
    assert response.status_code == 200
    assert response.json()["allowed_roles"] == ["test_admin", "state_admin"]

    db.refresh(system_admin_role)
    assert set(system_admin_role.allowed_roles) == original_allowed_roles | {
        custom_role.name
    }

    db.refresh(custom_role)
    assert custom_role.allowed_roles == ["test_admin", "state_admin"]


def test_update_role_visible_to_roles_moves_grant_between_roles(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Changing visible_to_roles on an update should revoke visibility from
    roles no longer in the list, not just grant it to the new ones -
    system_admin's own grant is unaffected either way, since it is always
    implicitly included."""
    org_id = _org_id(client, superuser_token_headers)
    system_admin_role = get_org_role(db, org_id, "system_admin")
    state_admin_role = get_org_role(db, org_id, "state_admin")
    test_admin_role = get_org_role(db, org_id, "test_admin")

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["state_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    new_role_id = response.json()["id"]
    new_role_name = response.json()["name"]

    db.refresh(state_admin_role)
    db.refresh(test_admin_role)
    assert new_role_name in state_admin_role.allowed_roles
    assert new_role_name not in test_admin_role.allowed_roles

    response = client.put(
        f"{settings.API_V1_STR}/roles/{new_role_id}",
        headers=superuser_token_headers,
        json={
            "name": new_role_name,
            "label": data["label"],
            "visible_to_roles": ["test_admin"],
        },
    )
    assert response.status_code == 200

    db.refresh(system_admin_role)
    db.refresh(state_admin_role)
    db.refresh(test_admin_role)
    assert new_role_name not in state_admin_role.allowed_roles
    assert new_role_name in test_admin_role.allowed_roles
    assert new_role_name in system_admin_role.allowed_roles


def test_update_role_cannot_revoke_system_admin_visibility(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """Sending visible_to_roles: [] (or any list omitting system_admin)
    never revokes system_admin's own visibility grant - only other roles'
    grants can be revoked this way."""
    org_id = _org_id(client, superuser_token_headers)
    systemadmin_token = get_user_token_for_org(
        db=db, organization_id=org_id, role="system_admin"
    )
    system_admin_role = get_org_role(db, org_id, "system_admin")

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    new_role_id = response.json()["id"]
    new_role_name = response.json()["name"]

    db.refresh(system_admin_role)
    assert new_role_name in system_admin_role.allowed_roles

    list_response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=systemadmin_token,
    )
    assert list_response.status_code == 200
    role_names = {role["name"] for role in list_response.json()["data"]}
    assert new_role_name in role_names

    response = client.put(
        f"{settings.API_V1_STR}/roles/{new_role_id}",
        headers=superuser_token_headers,
        json={
            "name": new_role_name,
            "label": data["label"],
            "visible_to_roles": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["visible_to_roles"] == ["system_admin"]

    db.refresh(system_admin_role)
    assert new_role_name in system_admin_role.allowed_roles

    list_response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=systemadmin_token,
    )
    assert list_response.status_code == 200
    role_names = {role["name"] for role in list_response.json()["data"]}
    assert new_role_name in role_names


def test_cannot_read_role_from_other_organization(
    client: TestClient, db: Session
) -> None:
    """Org A's admin can never read Org B's role by id, even knowing the id."""
    org_a_token = get_user_token(db=db, role="system_admin")
    org_b_token = get_user_token(db=db, role="system_admin")

    org_b_id = _org_id(client, org_b_token)
    org_b_role = get_org_role(db, org_b_id, "system_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/{org_b_role.id}",
        headers=org_a_token,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Role not found"


def test_read_roles_excludes_other_organizations_roles(
    client: TestClient, db: Session
) -> None:
    """GET /roles/ never returns another org's role, even with a matching name."""
    org_a_token = get_user_token(db=db, role="system_admin")
    org_b_token = get_user_token(db=db, role="system_admin")

    org_b_id = _org_id(client, org_b_token)
    org_b_role = get_org_role(db, org_b_id, "system_admin")

    response = client.get(f"{settings.API_V1_STR}/roles/", headers=org_a_token)
    assert response.status_code == 200
    returned_ids = {role["id"] for role in response.json()["data"]}
    assert org_b_role.id not in returned_ids


def test_superadmin_can_filter_roles_by_organization_id(
    client: TestClient, db: Session
) -> None:
    """super_admin can pass organization_id to fetch another org's roles,
    e.g. to look up the correct system_admin role_id when creating a user
    for that org."""
    superuser_token = get_user_token(db=db, role="super_admin")
    organization = create_random_organization(db)
    assert organization.id is not None
    org_role = get_org_role(db, organization.id, "system_admin")

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token,
        params={"organization_id": organization.id},
    )
    assert response.status_code == 200
    returned_ids = {role["id"] for role in response.json()["data"]}
    assert returned_ids == {org_role.id}


def test_non_superadmin_cannot_filter_roles_by_other_organization_id(
    client: TestClient, db: Session
) -> None:
    """A non-super_admin cannot use organization_id to peek at another
    org's roles."""
    org_a_token = get_user_token(db=db, role="system_admin")
    org_b_token = get_user_token(db=db, role="system_admin")
    org_b_id = _org_id(client, org_b_token)

    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=org_a_token,
        params={"organization_id": org_b_id},
    )
    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "You do not have permission to filter roles by another organization."
    )


def test_cannot_modify_role_from_other_organization(
    client: TestClient, db: Session
) -> None:
    """PUT/PATCH/DELETE on another org's role id must 404, not succeed."""
    org_a_token = get_user_token(db=db, role="super_admin")
    org_b_token = get_user_token(db=db, role="super_admin")

    org_b_id = _org_id(client, org_b_token)
    org_b_role = get_org_role(db, org_b_id, "test_admin")

    put_response = client.put(
        f"{settings.API_V1_STR}/roles/{org_b_role.id}",
        headers=org_a_token,
        json={"name": org_b_role.name, "label": "hijacked"},
    )
    assert put_response.status_code == 404
    assert put_response.json()["detail"] == "Role not found"

    patch_response = client.patch(
        f"{settings.API_V1_STR}/roles/{org_b_role.id}",
        headers=org_a_token,
        params={"is_active": False},
    )
    assert patch_response.status_code == 404
    assert patch_response.json()["detail"] == "Role not found"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/roles/{org_b_role.id}",
        headers=org_a_token,
    )
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Role not found"


def test_super_admin_role_cannot_be_modified_by_anyone(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    """Not even a T4D super admin can PUT/PATCH/DELETE the super_admin role."""
    org_id = _org_id(client, superuser_token_headers)
    super_admin_role = get_org_role(db, org_id, "super_admin")

    put_response = client.put(
        f"{settings.API_V1_STR}/roles/{super_admin_role.id}",
        headers=superuser_token_headers,
        json={"name": "super_admin", "label": "renamed"},
    )
    assert put_response.status_code == 403
    assert put_response.json()["detail"] == "The super_admin role cannot be modified"

    patch_response = client.patch(
        f"{settings.API_V1_STR}/roles/{super_admin_role.id}",
        headers=superuser_token_headers,
        params={"is_active": False},
    )
    assert patch_response.status_code == 403
    assert patch_response.json()["detail"] == "The super_admin role cannot be modified"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/roles/{super_admin_role.id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 403
    assert delete_response.json()["detail"] == "The super_admin role cannot be modified"


def test_two_orgs_customize_test_admin_independently(
    client: TestClient, db: Session
) -> None:
    """Turning a permission on for Org A's test_admin (here create_location,
    off by default for test_admin) must not affect Org B's test_admin
    permissions."""
    org_a_token = get_user_token(db=db, role="super_admin")
    org_b_token = get_user_token(db=db, role="super_admin")

    org_a_id = _org_id(client, org_a_token)
    org_b_id = _org_id(client, org_b_token)

    new_permission = db.exec(
        select(Permission).where(Permission.name == "create_location")
    ).first()
    assert new_permission is not None

    org_a_test_admin = get_org_role(db, org_a_id, "test_admin")
    org_b_test_admin = get_org_role(db, org_b_id, "test_admin")
    org_a_permission_ids = {
        permission.id for permission in (org_a_test_admin.permissions or [])
    }
    org_b_permission_ids_before = {
        permission.id for permission in (org_b_test_admin.permissions or [])
    }
    assert new_permission.id not in org_a_permission_ids
    assert new_permission.id not in org_b_permission_ids_before

    response = client.put(
        f"{settings.API_V1_STR}/roles/{org_a_test_admin.id}",
        headers=org_a_token,
        json={
            "name": org_a_test_admin.name,
            "label": org_a_test_admin.label,
            "permissions": [*org_a_permission_ids, new_permission.id],
        },
    )
    assert response.status_code == 200
    assert new_permission.id in response.json()["permissions"]

    db.refresh(org_b_test_admin)
    org_b_permission_ids_after = {
        permission.id for permission in (org_b_test_admin.permissions or [])
    }
    assert new_permission.id not in org_b_permission_ids_after


def test_visible_to_roles_grant_does_not_leak_across_orgs(
    client: TestClient, db: Session
) -> None:
    """Granting visibility to "system_admin" from Org A must only touch Org
    A's own system_admin row, even though Org B has an identically-named one."""
    org_a_token = get_user_token(db=db, role="super_admin")
    org_b_token = get_user_token(db=db, role="super_admin")

    org_a_id = _org_id(client, org_a_token)
    org_b_id = _org_id(client, org_b_token)

    org_a_system_admin = get_org_role(db, org_a_id, "system_admin")
    org_b_system_admin = get_org_role(db, org_b_id, "system_admin")

    data = {
        "name": random_lower_string(),
        "label": random_lower_string(),
        "description": random_lower_string(),
        "visible_to_roles": ["system_admin"],
    }
    response = client.post(
        f"{settings.API_V1_STR}/roles/", headers=org_a_token, json=data
    )
    assert response.status_code == 200
    new_role_name = response.json()["name"]

    db.refresh(org_a_system_admin)
    db.refresh(org_b_system_admin)
    assert new_role_name in org_a_system_admin.allowed_roles
    assert new_role_name not in org_b_system_admin.allowed_roles


def test_deleting_organization_cascades_to_its_roles(db: Session) -> None:
    """Deleting an Organization row must cascade-delete every Role scoped to
    it - the API only ever soft-deletes an org (is_deleted=True), so this
    exercises the FK/relationship cascade directly at the DB level. Uses a
    bare Organization (no OrganizationSettings) so the delete only exercises
    the role cascade, not unrelated relationships."""
    organization = Organization(name=random_lower_string())
    db.add(organization)
    db.commit()
    db.refresh(organization)
    assert organization.id is not None
    init_org_roles(db, organization.id)

    seeded_role_ids = [
        role.id
        for role in db.exec(
            select(Role).where(Role.organization_id == organization.id)
        ).all()
    ]
    assert len(seeded_role_ids) == 4

    db.delete(organization)
    db.commit()

    remaining_roles = db.exec(
        select(Role).where(col(Role.id).in_(seeded_role_ids))
    ).all()
    assert remaining_roles == []
