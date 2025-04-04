from sqlmodel import Session, select

from app.models import (
    PermissionPublic,
    Role,
    RoleCreate,
    RolePermission,
    RolePublic,
)

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


def create_role(
    session: Session, role_create: RoleCreate, permissions: list[PermissionPublic]
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
                    role_id=current_role.id, permission_id=permission.id
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
