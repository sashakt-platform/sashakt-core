from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import SessionDep
from app.models import (
    Message,
    Permission,
    PermissionCreate,
    PermissionPublic,
    PermissionsPublic,
    PermissionUpdate,
)

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/", response_model=PermissionsPublic)
def read_permissions(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve permissions.
    """

    count_statement = select(func.count()).select_from(Permission)
    count = session.exec(count_statement).one()
    statement = select(Permission).offset(skip).limit(limit)
    permissions = session.exec(statement).all()

    # if current_user.is_superuser:
    #     count_statement = select(func.count()).select_from(Permission)
    #     count = session.exec(count_statement).one()
    #     statement = select(Permission).offset(skip).limit(limit)
    #     permissions = session.exec(statement).all()
    # else:
    #     count_statement = (
    #         select(func.count())
    #         .select_from(Permission)
    #         .where(Permission.owner_id == current_user.id)
    #     )
    #     count = session.exec(count_statement).one()
    #     statement = (
    #         select(Permission)
    #         .where(Permission.owner_id == current_user.id)
    #         .offset(skip)
    #         .limit(limit)
    #     )
    #     permissions = session.exec(statement).all()

    return PermissionsPublic(data=permissions, count=count)


@router.get("/{id}", response_model=PermissionPublic)
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


@router.post("/", response_model=PermissionPublic)
def create_permission(*, session: SessionDep, permission_in: PermissionCreate) -> Any:
    """
    Create new permission.
    """
    permission = Permission.model_validate(permission_in)
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


@router.put("/{id}", response_model=PermissionPublic)
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


@router.patch("/{id}")
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


@router.delete("/{id}")
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
