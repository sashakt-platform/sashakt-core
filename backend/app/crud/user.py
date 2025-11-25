from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.roles import state_admin, test_admin
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import Permission, Role, RolePermission, State
from app.models.user import User, UserCreate, UserPublic, UserState, UserUpdate


def create_user(
    *,
    session: Session,
    user_create: UserCreate,
    created_by_id: int | None = None,
) -> User:
    db_obj = User.model_validate(
        user_create,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "created_by_id": created_by_id,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(db_obj.id, access_token_expires)

    db_obj.token = token
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_public(*, session: Session, db_user: User) -> UserPublic:
    role = session.exec(select(Role).where(Role.id == db_user.role_id)).first()
    role_name = role.name if role else "N/A"
    role_label = role.label if role else "N/A"

    states = None
    if role_name == state_admin.name or role_name == test_admin.name:
        state_query = (
            select(State)
            .join(UserState)
            .where(State.id == UserState.state_id)
            .where(UserState.user_id == db_user.id)
        )
        states = session.exec(state_query).all()

    user_public = UserPublic(
        id=db_user.id,
        full_name=db_user.full_name,
        created_date=db_user.created_date,
        modified_date=db_user.modified_date,
        email=db_user.email,
        phone=db_user.phone,
        role_id=db_user.role_id,
        organization_id=db_user.organization_id,
        created_by_id=db_user.created_by_id,
        is_active=db_user.is_active,
        role_label=role_label,
        states=states or None,
    )
    return user_public


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_id(*, session: Session, id: int) -> User | None:
    statement = select(User).where(User.id == id)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def get_user_permissions(*, session: Session, user: User) -> list[str]:
    role = session.get(Role, user.role_id)

    permissions = (
        list(
            session.exec(
                select(Permission.name)
                .join(RolePermission)
                .where(RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            ).all()
        )
        if role
        else []
    )
    return permissions
