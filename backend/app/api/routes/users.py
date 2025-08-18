from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi_pagination import Page, paginate
from sqlmodel import col, select

from app import crud
from app.api.deps import (
    CurrentUser,
    Pagination,
    SessionDep,
    get_current_active_superuser,
    permission_dependency,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.models.location import State
from app.models.role import Role
from app.models.user import UserState
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(permission_dependency("read_user"))],
    response_model=Page[UserPublic],
)
def read_users(
    session: SessionDep,
    current_user: CurrentUser,
    param: Pagination = Depends(),
) -> Page[UserPublic]:
    """
    Retrieve users.
    """
    current_user_organization_id = current_user.organization_id

    statement = select(User).where(User.organization_id == current_user_organization_id)
    users = session.exec(statement).all()

    return cast(Page[UserPublic], paginate(users, params=param))


@router.post(
    "/",
    dependencies=[Depends(permission_dependency("create_user"))],
    response_model=UserPublic,
)
def create_user(
    *,
    session: SessionDep,
    user_in: UserCreate,
    current_user: CurrentUser,
) -> UserPublic:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = crud.create_user(
        session=session, user_create=user_in, created_by_id=current_user.id
    )
    states = None
    role = session.exec(select(Role).where(Role.id == user.role_id)).first()

    if role and role.name == "state_admin" and user_in.state_ids:
        existing_states = session.exec(
            select(State).where(col(State.id).in_(user_in.state_ids))
        ).all()
        user_states = [
            UserState(user_id=user.id, state_id=state.id) for state in existing_states
        ]
        session.add_all(user_states)
        state_query = select(State).join(UserState).where(UserState.user_id == user.id)
        states = session.exec(state_query).all()

    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    session.commit()
    user_data = UserPublic.model_validate(user)
    return user_data.model_copy(update={"states": states})


@router.patch(
    "/me",
    response_model=UserPublic,
    dependencies=[Depends(permission_dependency("update_user_me"))],
)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch(
    "/me/password",
    response_model=Message,
    dependencies=[Depends(permission_dependency("update_user"))],
)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get(
    "/me",
    response_model=UserPublic,
    dependencies=[Depends(permission_dependency("read_user"))],
)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete(
    "/me",
    response_model=Message,
    dependencies=[Depends(permission_dependency("delete_user"))],
)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    # if current_user.is_superuser:
    #     raise HTTPException(
    #         status_code=403, detail="Super users are not allowed to delete themselves"
    #     )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post(
    "/signup",
    response_model=UserPublic,
    dependencies=[Depends(permission_dependency("create_user"))],
)
def register_user(session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    dependencies=[Depends(permission_dependency("read_user"))],
)
def read_user_by_id(
    user_id: int, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if (
        not user
        or user.is_deleted
        or user.organization_id != current_user.organization_id
    ):
        raise HTTPException(status_code=404, detail="User not found")
    _ = user.states
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(permission_dependency("update_user"))],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: int,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    final_role_id = user_in.role_id or db_user.role_id
    final_role = session.get(Role, final_role_id)

    if not final_role:
        raise HTTPException(status_code=400, detail="Invalid role ID provided.")

    is_state_admin = final_role.name == "state_admin"

    if is_state_admin and user_in.state_ids is not None:
        if user_in.state_ids == []:
            db_user.states = []

        else:
            db_user.states = list(
                session.exec(
                    select(State).where(col(State.id).in_(user_in.state_ids))
                ).all()
            )

    updated_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    states = db_user.states if is_state_admin else None

    return UserPublic(**updated_user.model_dump(), states=states)


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: int
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    try:
        session.delete(user)
        session.commit()
        return Message(message="User deleted successfully")
    except Exception as e:
        session.rollback()

        raise HTTPException(
            status_code=400, detail=f"Failed to delete user. Reason: {str(e)}"
        )
