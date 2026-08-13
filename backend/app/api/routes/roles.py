from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.core.roles import get_valid_roles
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


def _fetch_roles_by_name(
    session: SessionDep, role_names: list[str], field_name: str
) -> list[Role]:
    """
    Look up roles by name, failing the whole request up front if any name
    doesn't match an existing role.
    """
    if not role_names:
        return []

    roles = list(session.exec(select(Role).where(col(Role.name).in_(role_names))).all())
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


@router.get(
    "/",
    response_model=RolesPublic,
    dependencies=[Depends(permission_dependency("read_role"))],
)
def read_roles(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 150
) -> Any:
    """
    Retrieve roles based on current user's role hierarchy.
    """
    # get available role names based on current user's role
    available_roles = get_valid_roles(current_user.role)

    if not available_roles:
        # if user has no available roles, return empty result
        return RolesPublic(data=[], count=0)

    count_statement = (
        select(func.count())
        .select_from(Role)
        .where(col(Role.name).in_(available_roles))
    )
    count = session.exec(count_statement).one()

    statement = (
        select(Role)
        .where(col(Role.name).in_(available_roles))
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
def read_role(session: SessionDep, id: int) -> Any:
    """
    Get role by ID.
    """
    role = session.get(Role, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
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
def create_role(*, session: SessionDep, role_in: RoleCreate) -> Any:
    """
    Create new role.
    """
    _fetch_roles_by_name(session, role_in.allowed_roles, "allowed_roles")
    allow_roles = _fetch_roles_by_name(
        session, role_in.visible_to_roles, "visible_to_roles"
    )

    role_data = role_in.model_dump(exclude={"permissions", "visible_to_roles"})
    role = Role.model_validate(role_data)
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
    "/{id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("update_role"))],
)
def update_role(
    *,
    session: SessionDep,
    id: int,
    role_update: RoleUpdate,
) -> Any:
    """
    Update an role.
    """
    role = session.get(Role, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    _fetch_roles_by_name(session, role_update.allowed_roles, "allowed_roles")

    allow_roles = (
        _fetch_roles_by_name(session, role_update.visible_to_roles, "visible_to_roles")
        if role_update.visible_to_roles is not None
        else []
    )

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


@router.patch(
    "/{id}",
    response_model=RolePublic,
    dependencies=[Depends(permission_dependency("update_role"))],
)
def set_visibility_role(
    session: SessionDep,
    id: int,
    is_active: bool = Query(True, description="Set visibility of the Role"),
) -> RolePublic:
    """
    Set visitibility of the Role
    """
    role = session.get(Role, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
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
def delete_role(session: SessionDep, id: int) -> Message:
    """
    Delete an role.
    """
    role = session.get(Role, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
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
