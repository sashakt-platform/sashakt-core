from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, not_, select

from app.api.deps import SessionDep
from app.models import Message, Role, RoleCreate, RolePublic, RolesPublic, RoleUpdate

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", response_model=RolesPublic)
def read_roles(session: SessionDep, skip: int = 0, limit: int = 100) -> RolePublic:
    """
    Retrieve roles.
    """
    count_statement = (
        select(func.count()).select_from(Role).where(not_(Role.is_deleted))
    )
    count = session.exec(count_statement).one()
    statement = select(Role).where(not_(Role.is_deleted)).offset(skip).limit(limit)
    roles = session.exec(statement).all()

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

    return RolesPublic(data=roles, count=count)


@router.get("/{id}", response_model=RolePublic)
def read_role(session: SessionDep, id: int) -> Any:
    """
    Get role by ID.
    """
    role = session.get(Role, id)
    if not role or role.is_deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    return role


@router.post("/", response_model=RolePublic)
def create_role(*, session: SessionDep, role_in: RoleCreate) -> Role:
    """
    Create new role.
    """
    role = Role.model_validate(role_in)
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.put("/{id}", response_model=RolePublic)
def update_role(
    *,
    session: SessionDep,
    id: int,
    role_in: RoleUpdate,
) -> Any:
    """
    Update an role.
    """
    role = session.get(Role, id)
    if not role or role.is_deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = role_in.model_dump(exclude_unset=True)
    role.sqlmodel_update(update_dict)
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.patch("/{role_id}", response_model=RolePublic)
def set_visibility_role(
    *,
    session: SessionDep,
    role_id: int,
    is_active: bool = Query(False, description="Set visibility of Role"),
) -> Role:
    """
    Set visibility of role.
    """
    role = session.get(Role, role_id)
    if not role or role.is_deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    role.is_active = is_active
    session.add(role)
    session.commit()
    session.refresh(role)
    return role


@router.delete("/{role_id}")
def delete_role(session: SessionDep, role_id: int) -> Message:
    """
    Delete an role.
    """
    role = session.get(Role, role_id)
    if not role or role.is_deleted:
        raise HTTPException(status_code=404, detail="Role not found")
    # if not current_user.is_superuser and (role.owner_id != current_user.id):
    #     raise HTTPException(status_code=400, detail="Not enough permissions")
    role.is_deleted = True
    session.commit()
    session.refresh(role)
    return Message(message="Role deleted successfully")
