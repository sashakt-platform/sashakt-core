from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
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


def _get_own_org_role(
    session: SessionDep, current_user: CurrentUser, role_id: int
) -> Role:
    """
    Get role by ID, scoped to the caller's own organization.
    """
    role = session.get(Role, role_id)
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


def _fetch_roles_by_name(
    session: SessionDep, organization_id: int, role_names: list[str], field_name: str
) -> list[Role]:
    """
    Look up roles by name within the caller's own organization, failing the
    whole request up front if any name doesn't match an existing role there.
    """
    if not role_names:
        return []

    roles = list(
        session.exec(
            select(Role).where(
                col(Role.name).in_(role_names),
                Role.organization_id == organization_id,
            )
        ).all()
    )
    missing = set(role_names) - {role.name for role in roles}
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown role name(s) in {field_name}: {', '.join(sorted(missing))}",
        )
    return roles


def _grant_visibility(
    session: SessionDep, role_name: str, allow_roles: list[Role]
) -> None:
    """
    Append role_name to each allow role's allowed_roles, if not already
    present. Caller is responsible for committing - this only stages
    changes, since session.commit() expires every object tracked by the
    session (not just the ones just added), which would otherwise blow away
    attributes the caller is about to read off its own role instance.
    """
    for allow_role in allow_roles:
        if role_name not in (allow_role.allowed_roles or []):
            allow_role.allowed_roles = [
                *(allow_role.allowed_roles or []),
                role_name,
            ]
            session.add(allow_role)


def _revoke_visibility(
    session: SessionDep, role_name: str, revoke_roles: list[Role]
) -> None:
    """
    Remove role_name from each revoke role's allowed_roles, if present.
    Caller is responsible for committing - see _grant_visibility.
    """
    for revoke_role in revoke_roles:
        if role_name in (revoke_role.allowed_roles or []):
            revoke_role.allowed_roles = [
                allowed_role_name
                for allowed_role_name in revoke_role.allowed_roles
                if allowed_role_name != role_name
            ]
            session.add(revoke_role)


def _roles_visible_to(
    session: SessionDep, organization_id: int, role_name: str
) -> list[Role]:
    """
    Find every role within the caller's own organization that currently has
    role_name in its allowed_roles. allowed_roles is a JSON column, so this
    scans the (small, org-scoped) roles table rather than issuing a JSON-
    containment query.
    """
    org_roles = session.exec(
        select(Role).where(Role.organization_id == organization_id)
    ).all()
    return [
        existing_role
        for existing_role in org_roles
        if role_name in (existing_role.allowed_roles or [])
    ]


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
    available_roles = get_valid_roles(current_user.role)

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
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("read_role"))],
)
def read_role(session: SessionDep, current_user: CurrentUser, role_id: int) -> Any:
    """
    Get role by ID. See `_get_own_org_role`.
    """
    role = _get_own_org_role(session, current_user, role_id)
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
    Create new role, stamped with the caller's own organization.
    """
    org_id = current_user.organization_id
    _fetch_roles_by_name(session, org_id, role_in.allowed_roles, "allowed_roles")
    allow_roles = _fetch_roles_by_name(
        session, org_id, role_in.visible_to_roles, "visible_to_roles"
    )

    role_data = role_in.model_dump(exclude={"permissions", "visible_to_roles"})
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

    _grant_visibility(session, role.name, allow_roles)
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
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("update_role"))],
)
def update_role(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    role_id: int,
    role_update: RoleUpdate,
) -> Any:
    """
    Update a role.
    """
    role = _get_own_org_role(session, current_user, role_id)
    _ensure_not_super_admin(role)
    org_id = current_user.organization_id

    _fetch_roles_by_name(session, org_id, role_update.allowed_roles, "allowed_roles")

    if role_update.permissions is not None:
        permission_remove = [
            permission.id
            for permission in (role.permissions or [])
            if permission.id not in role_update.permissions
        ]
        permissions_add = [
            permission
            for permission in role_update.permissions
            if permission not in [existing.id for existing in (role.permissions or [])]
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

    update_dict = role_update.model_dump(
        exclude_unset=True, exclude={"visible_to_roles", "name"}
    )
    role.sqlmodel_update(update_dict)
    session.add(role)
    session.commit()
    session.refresh(role)

    if role_update.visible_to_roles is not None:
        target_roles = _fetch_roles_by_name(
            session, org_id, role_update.visible_to_roles, "visible_to_roles"
        )
        target_role_ids = {target_role.id for target_role in target_roles}

        revoke_roles = [
            currently_visible_role
            for currently_visible_role in _roles_visible_to(session, org_id, role.name)
            if currently_visible_role.id not in target_role_ids
        ]

        _grant_visibility(session, role.name, target_roles)
        _revoke_visibility(session, role.name, revoke_roles)
        session.commit()
        session.refresh(role)

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )

    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.patch(
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("update_role"))],
)
def set_visibility_role(
    session: SessionDep,
    current_user: CurrentUser,
    role_id: int,
    is_active: bool = Query(True, description="Set visibility of the Role"),
) -> RolePublic:
    """
    Set visibility of the Role. See `_get_own_org_role` and `_ensure_not_super_admin`.
    """
    role = _get_own_org_role(session, current_user, role_id)
    _ensure_not_super_admin(role)
    role.is_active = is_active
    session.add(role)
    session.commit()
    session.refresh(role)

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role_id)
    )
    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.delete(
    "/{role_id}",
    dependencies=[Depends(permission_dependency("delete_role"))],
)
def delete_role(
    session: SessionDep, current_user: CurrentUser, role_id: int
) -> Message:
    """
    Delete a role. See `_get_own_org_role` and `_ensure_not_super_admin`.
    """
    role = _get_own_org_role(session, current_user, role_id)
    _ensure_not_super_admin(role)
    if role.is_restricted:
        raise HTTPException(
            status_code=400,
            detail="This role is restricted and cannot be deleted",
        )

    session.delete(role)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a role that is still assigned to users",
        )
    return Message(message="Role deleted successfully")
