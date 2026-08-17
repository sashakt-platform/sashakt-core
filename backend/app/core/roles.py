import json

from sqlmodel import Session, select

from app.models import (
    Permission,
    Role,
    RoleCreate,
    RoleLocationLevel,
    RolePermission,
    RolePublic,
)

super_admin = RoleCreate(
    name="super_admin",
    label="Super Admin",
    description="A super-admin has overall access to the system",
    allowed_roles=["system_admin"],
)

system_admin = RoleCreate(
    name="system_admin",
    label="System Admin",
    description="System-level admin who can handle organization-level tasks",
    allowed_roles=["system_admin", "state_admin", "test_admin"],
)


state_admin = RoleCreate(
    name="state_admin",
    label="State Admin",
    description="State-level admin of a organization",
    location_scope=RoleLocationLevel.STATE,
    allowed_roles=["state_admin", "test_admin"],
)


test_admin = RoleCreate(
    name="test_admin",
    label="Test Admin",
    description="Test Admin who creates and conducts test",
    location_scope=RoleLocationLevel.DISTRICT,
    allowed_roles=["test_admin"],
)


candidate = RoleCreate(
    name="candidate",
    label="Candidate",
    description="Candidate who attempts Test",
    allowed_roles=[],
)

with open("app/core/permission_data.json") as file:
    permission_data = json.load(file)


def get_role_permissions(role: RoleCreate, session: Session) -> list[int]:
    """
    Function to get the permissions of a role.
    It fetches the permission IDs from permission table if that permission is assigned to the role.
    """
    role_name = role.name
    permission_list = []
    for permission in permission_data:
        if permission[role_name]:
            current_permission = session.exec(
                select(Permission.id).where(Permission.name == permission["name"])
            ).first()
            if current_permission is not None:
                permission_list.append(current_permission)
    return permission_list


def create_role(
    session: Session,
    role_create: RoleCreate,
    permissions: list[int],
    organization_id: int,
) -> RolePublic:
    current_role = session.exec(
        select(Role).where(
            Role.name == role_create.name,
            Role.organization_id == organization_id,
        )
    ).first()

    if not current_role:
        current_role = Role(
            **role_create.model_dump(),
            is_restricted=True,
            organization_id=organization_id,
        )
        session.add(current_role)
        session.commit()
        session.refresh(current_role)
        if len(permissions) > 0:
            for permission in permissions:
                role_permission = RolePermission(
                    role_id=current_role.id, permission_id=permission
                )
                session.add(role_permission)
                session.commit()
                session.refresh(role_permission)

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(
            RolePermission.role_id == current_role.id
        )
    )
    return RolePublic(**current_role.model_dump(), permissions=stored_permission_ids)


def init_super_admin_role(session: Session, organization_id: int) -> None:
    """
    Create the single, global super_admin role, scoped to the T4D organization,
    pre-loaded with its default permissions.

    This must only ever be called once, for T4D — super_admin is never cloned
    into any other organization.
    """
    super_admin_permissions = get_role_permissions(super_admin, session)
    create_role(
        session, super_admin, super_admin_permissions, organization_id=organization_id
    )


def init_org_roles(session: Session, organization_id: int) -> None:
    """
    Create system_admin, state_admin, test_admin, and candidate roles scoped to
    one organization, pre-loaded with their default permissions. Idempotent —
    safe to call multiple times for the same organization.
    """
    for role in (system_admin, state_admin, test_admin, candidate):
        role_permissions = get_role_permissions(role, session)
        create_role(session, role, role_permissions, organization_id=organization_id)


def get_valid_roles(role: Role) -> list[str]:
    """
    Get list of role names that the given role can view/create/update,
    based on that role's own allowed_roles.
    """
    return role.allowed_roles or []


def can_assign_role(role: Role, target_role_name: str) -> bool:
    """
    Check if the given role can assign the target role name,
    based on that role's own allowed_roles.
    """
    return target_role_name in get_valid_roles(role)


def is_location_scoped_role(role: Role) -> bool:
    """
    Check if a role's access is restricted to its assigned states/districts.
    """
    return role.location_scope is not None
