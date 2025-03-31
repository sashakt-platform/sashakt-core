from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import SessionDep
from app.models import (
    Message,
    Role,
    RoleCreate,
    RolePermission,
    RolePublic,
    RolesPublic,
    RoleUpdate,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", response_model=RolesPublic)
def read_roles(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve roles.
    """

    count_statement = select(func.count()).select_from(Role)
    count = session.exec(count_statement).one()
    statement = select(Role).offset(skip).limit(limit)
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

    # if current_user.is_superuser:
    #     count_statement = select(func.count()).select_from(Role)
    #     count = session.exec(count_statement).one()
    #     statement = select(Role).offset(skip).limit(limit)
    #     roles = session.exec(statement).all()
    # else:
    #     count_statement = (
    #         select(func.count())
    #         .select_from(Role)
    #         .where(Role.owner_id == current_user.id)
    #     )
    #     count = session.exec(count_statement).one()
    #     statement = (
    #         select(Role)
    #         .where(Role.owner_id == current_user.id)
    #         .offset(skip)
    #         .limit(limit)
    #     )
    #     roles = session.exec(statement).all()

    return RolesPublic(data=role_public, count=count)


@router.get("/{id}", response_model=RolePublic)
def read_role(session: SessionDep, id: int) -> Any:
    """
    Get role by ID.
    """
    role = session.get(Role, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )

    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.post("/", response_model=RolePublic)
def create_role(*, session: SessionDep, role_in: RoleCreate) -> Any:
    """
    Create new role.
    """
    role_data = role_in.model_dump(exclude={"permissions"})
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

    stored_permission_ids = session.exec(
        select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
    )

    return RolePublic(
        **role.model_dump(),
        permissions=stored_permission_ids,
    )


@router.put("/{id}", response_model=RolePublic)
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
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")

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


@router.patch("/{id}")
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
    return role


@router.delete("/{id}")
def delete_role(session: SessionDep, id: int) -> Message:
    """
    Delete an role.
    """
    role = session.get(Role, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(role)
    session.commit()
    return Message(message="Role deleted successfully")
