from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, permission_dependency
from app.core.roles import super_admin
from app.models import (
    Message,
    Permission,
    PermissionCreate,
    PermissionPublic,
    PermissionsPublic,
    PermissionUpdate,
)

router = APIRouter(prefix="/permissions", tags=["permissions"])


PERMISSIONS_HIDDEN_FROM_NON_SUPER_ADMIN = (
    "create_organization",
    "update_organization",
    "delete_organization",
    "read_organization",
    "create_location",
    "update_location",
    "read_location",
    "create_permission",
    "update_permission",
    "delete_permission",
    "read_permission",
)


@router.get(
    "/",
    response_model=PermissionsPublic,
    dependencies=[Depends(permission_dependency("read_permission"))],
)
def read_permissions(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve permissions.
    """

    count_statement = select(func.count()).select_from(Permission)
    statement = select(Permission)

    if current_user.role.name != super_admin.name:
        count_statement = count_statement.where(
            col(Permission.name).not_in(PERMISSIONS_HIDDEN_FROM_NON_SUPER_ADMIN)
        )
        statement = statement.where(
            col(Permission.name).not_in(PERMISSIONS_HIDDEN_FROM_NON_SUPER_ADMIN)
        )

    count = session.exec(count_statement).one()
    permissions = session.exec(statement.offset(skip).limit(limit)).all()

    return PermissionsPublic(data=permissions, count=count)


@router.get(
    "/{id}",
    response_model=PermissionPublic,
    dependencies=[Depends(permission_dependency("read_permission"))],
)
def read_permission(session: SessionDep, id: int) -> Any:
    """
    Get permission by ID.
    """
    permission = session.get(Permission, id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    # if not current_user.is_superuser and (permission.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    return permission


@router.post(
    "/",
    response_model=PermissionPublic,
    dependencies=[Depends(permission_dependency("create_permission"))],
)
def create_permission(
    *,
    session: SessionDep,
    permission_in: PermissionCreate,
) -> Any:
    """
    Create new permission.
    """
    permission = Permission.model_validate(permission_in)
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


@router.put(
    "/{id}",
    response_model=PermissionPublic,
    dependencies=[Depends(permission_dependency("update_permission"))],
)
def update_permission(
    *,
    session: SessionDep,
    id: int,
    permission_in: PermissionUpdate,
) -> Any:
    """
    Update an permission.
    """
    permission = session.get(Permission, id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    # if not current_user.is_superuser and (permission.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = permission_in.model_dump(exclude_unset=True)
    if permission:
        permission.sqlmodel_update(update_dict)
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


@router.patch(
    "/{id}",
    response_model=PermissionPublic,
    dependencies=[Depends(permission_dependency("update_permission"))],
)
def set_visibility_permission(
    session: SessionDep,
    id: int,
    is_active: bool = Query(True, description="Set visibility of the Permission"),
) -> Permission:
    """
    Set visitibility of the Permission
    """
    permission = session.get(Permission, id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission.is_active = is_active
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


@router.delete(
    "/{id}",
    dependencies=[Depends(permission_dependency("delete_permission"))],
)
def delete_permission(session: SessionDep, id: int) -> Message:
    """
    Delete an permission.
    """
    permission = session.get(Permission, id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    # if not current_user.is_superuser and (permission.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(permission)
    session.commit()
    return Message(message="Permission deleted successfully")
