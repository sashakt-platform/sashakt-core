from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Sequence, not_, select

from app.api.deps import SessionDep
from app.models import (
    Message,
    Permission,
    PermissionCreate,
    PermissionPublic,
    PermissionUpdate,
)

router = APIRouter(prefix="/permission", tags=["Permission"])


@router.post("/", response_model=PermissionPublic)
def create_permission(
    permission_create: PermissionCreate, session: SessionDep
) -> Permission:
    permission = Permission.model_validate(permission_create)
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


@router.get("/", response_model=list[PermissionPublic])
def get_permission(session: SessionDep) -> Sequence[PermissionPublic]:
    permission = session.exec(
        select(Permission).where(not_(Permission.is_deleted))
    ).all()
    return permission


# Get Permission by ID
@router.get("/{permission_id}", response_model=PermissionPublic)
def get_permission_by_id(permission_id: int, session: SessionDep) -> Permission:
    permission = session.get(Permission, permission_id)
    if not permission or permission.is_deleted is True:
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission


# Update a Permission
@router.put("/{permission_id}", response_model=PermissionPublic)
def update_permission(
    permission_id: int,
    updated_data: PermissionUpdate,
    session: SessionDep,
) -> Permission:
    permission = session.get(Permission, permission_id)
    if not permission or permission.is_deleted is True:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission_data = updated_data.model_dump(exclude_unset=True)
    permission.sqlmodel_update(permission_data)
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


# Set Visibility of permission
@router.patch("/{permission_id}", response_model=PermissionPublic)
def visibility_permission(
    permission_id: int,
    session: SessionDep,
    is_active: bool = Query(
        False, title="Permission Visibility", description="Set visibility of Permission"
    ),
) -> Permission:
    permission = session.get(Permission, permission_id)
    if not permission or permission.is_deleted is True:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission.is_active = is_active
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return permission


# Delete a Permission
@router.delete("/{permission_id}")
def delete_permission(permission_id: int, session: SessionDep) -> Message:
    permission = session.get(Permission, permission_id)
    if not permission or permission.is_deleted is True:
        raise HTTPException(status_code=404, detail="Permission not found")
    permission.is_deleted = True
    session.add(permission)
    session.commit()
    session.refresh(permission)
    return Message(message="Permission deleted successfully")
