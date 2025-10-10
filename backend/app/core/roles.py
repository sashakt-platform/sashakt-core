import json

from sqlmodel import Session, select

from app.models import (
    Permission,
    Role,
    RoleCreate,
    RolePermission,
    RolePublic,
)

ROLE_HIERARCHY = {
    "super_admin": 1,
    "system_admin": 2,
    "state_admin": 3,
    "test_admin": 4,
    "candidate": 5,
}

super_admin = RoleCreate(
    name="super_admin",
    label="Super Admin",
    description="A super-admin has overall access to the system",
)

system_admin = RoleCreate(
    name="system_admin",
    label="System Admin",
    description="System-level admin who can handle organization-level tasks",
)


state_admin = RoleCreate(
    name="state_admin",
    label="State Admin",
    description="State-level admin of a organization",
)


test_admin = RoleCreate(
    name="test_admin",
    label="Test Admin",
    description="Test Admin who creates and conducts test",
)


candidate = RoleCreate(
    name="candidate",
    label="Candidate",
    description="Candidate who attempts Test",
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
    session: Session, role_create: RoleCreate, permissions: list[int]
) -> RolePublic:
    current_role = session.exec(
        select(Role).where(Role.name == role_create.name)
    ).first()

    if not current_role:
        current_role = Role(**role_create.model_dump())
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
    else:
        stored_permission_ids = session.exec(
            select(RolePermission.permission_id).where(
                RolePermission.role_id == current_role.id
            )
        )
    return RolePublic(**current_role.model_dump(), permissions=stored_permission_ids)


def init_roles(session: Session) -> None:
    """
    Function to initialize roles in the database.
    It creates roles based on the data provided in permission_data.json file.
    """
    super_admin_permissions = get_role_permissions(super_admin, session)
    system_admin_permissions = get_role_permissions(system_admin, session)
    state_admin_permissions = get_role_permissions(state_admin, session)
    test_admin_permissions = get_role_permissions(test_admin, session)
    candidate_permissions = get_role_permissions(candidate, session)

    create_role(session, super_admin, super_admin_permissions)

    create_role(session, system_admin, system_admin_permissions)

    create_role(session, state_admin, state_admin_permissions)

    create_role(session, test_admin, test_admin_permissions)

    create_role(session, candidate, candidate_permissions)
