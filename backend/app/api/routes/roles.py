from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.core.roles import get_valid_roles, super_admin
from app.models import (
    Message,
    Role,
    RoleCreate,
    RolePermission,
    RolePublic,
    RolesPublic,
    RoleUpdate,
)

router = APIRouter(
    prefix="/roles",
    tags=["roles"],
)


def _get_own_org_role(session: SessionDep, current_user: CurrentUser, id: int) -> Role:
    """
    Get role by ID, scoped to the caller's own organization.
    """
    role = session.get(Role, id)
    if not role or role.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def _ensure_not_super_admin(role: Role) -> None:
    """
    Block modification of the super_admin role.
    """
    if role.name == super_admin.name:
        raise HTTPException(
            status_code=403, detail="The super_admin role cannot be modified"
        )


@router.get(
    "/",
    response_model=RolesPublic,
    dependencies=[Depends(permission_dependency("read_role"))],
)
def read_roles(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 150
) -> Any:
    """
    Retrieve roles based on current user's role hierarchy, scoped to their
    own organization.
    """
    # get available role names based on current user's role
    available_roles = get_valid_roles(current_user.role.name)

    if not available_roles:
        # if user has no available roles, return empty result
        return RolesPublic(data=[], count=0)

    count_statement = (
        select(func.count())
        .select_from(Role)
        .where(
            col(Role.name).in_(available_roles),
            Role.organization_id == current_user.organization_id,
        )
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Role)
        .where(
            col(Role.name).in_(available_roles),
            Role.organization_id == current_user.organization_id,
        )
        .offset(skip)
        .limit(limit)
    )
    roles = session.exec(statement).all()

    role_public = []
    for role in roles:
        stored_permission_ids = session.exec(
            select(RolePermission.permission_id).where(
                RolePermission.role_id == role.id
            )
        )
        role_public.append(
            RolePublic(
                **role.model_dump(),
                permissions=stored_permission_ids,
            )
        )

    return RolesPublic(data=role_public, count=count)


@router.get(
    "/{id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("read_role"))],
)
def read_role(session: SessionDep, current_user: CurrentUser, id: int) -> Any:
    """
    Get role by ID. See `_get_own_org_role`.
    """
    role = _get_own_org_role(session, current_user, id)
    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )

    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.post(
    "/",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("create_role"))],
)
def create_role(
    *, session: SessionDep, role_in: RoleCreate, current_user: CurrentUser
) -> Any:
    """
    Create new role.
    """
    role_data = role_in.model_dump(exclude={"permissions"})
    role = Role(**role_data, organization_id=current_user.organization_id)
    session.add(role)
    session.commit()
    if role_in.permissions:
        permission_ids = role_in.permissions
        permission_links = [
            RolePermission(role_id=role.id, permission_id=permission_id)
            for permission_id in permission_ids
        ]
        session.add_all(permission_links)
        session.commit()
    session.refresh(role)

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )

    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.put(
    "/{id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("update_role"))],
)
def update_role(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: int,
    role_update: RoleUpdate,
) -> Any:
    """
    Update a role.
    """
    role = _get_own_org_role(session, current_user, id)
    _ensure_not_super_admin(role)

    # Updating Permission
    permission_remove = [
        permissions.id
        for permissions in (role.permissions or [])
        if permissions.id not in (role_update.permissions or [])
    ]
    permissions_add = [
        permission
        for permission in (role_update.permissions or [])
        if permission not in [t.id for t in (role.permissions or [])]
    ]

    if permission_remove:
        for permission in permission_remove:
            session.delete(
                session.exec(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == permission,
                    )
                ).one()
            )
        session.commit()

    if permissions_add:
        for permission in permissions_add:
            session.add(RolePermission(role_id=role.id, permission_id=permission))
        session.commit()

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )

    update_dict = role_update.model_dump(exclude_unset=True)
    role.sqlmodel_update(update_dict)
    session.add(role)
    session.commit()
    session.refresh(role)
    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.patch(
    "/{id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("update_role"))],
)
def set_visibility_role(
    session: SessionDep,
    current_user: CurrentUser,
    id: int,
    is_active: bool = Query(True, description="Set visibility of the Role"),
) -> RolePublic:
    """
    Set visibility of the Role. See `_get_own_org_role` and `_ensure_not_super_admin`.
    """
    role = _get_own_org_role(session, current_user, id)
    _ensure_not_super_admin(role)
    role.is_active = is_active
    session.add(role)
    session.commit()
    session.refresh(role)

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == id)
    )
    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.delete(
    "/{id}",
    dependencies=[Depends(permission_dependency("delete_role"))],
)
def delete_role(session: SessionDep, current_user: CurrentUser, id: int) -> Message:
    """
    Delete a role. See `_get_own_org_role` and `_ensure_not_super_admin`.
    """
    role = _get_own_org_role(session, current_user, id)
    _ensure_not_super_admin(role)
    session.delete(role)
    session.commit()
    return Message(message="Role deleted successfully")
