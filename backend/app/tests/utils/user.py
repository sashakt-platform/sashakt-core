from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import Role, User, UserCreate, UserUpdate
from app.tests.utils.utils import random_email, random_lower_string


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_random_user(db: Session) -> User:
    role = Role(name=random_lower_string(), label=random_lower_string())
    db.add(role)
    db.commit()
    email = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    phone = random_lower_string()
    user_in = UserCreate(
        email=email,
        password=password,
        phone=phone,
        full_name=full_name,
        role_id=role.id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    return user


def get_user_token(*, db: Session, role: str) -> dict[str, str]:
    current_role = db.exec(select(Role).where(Role.name == role)).first()
    if not current_role:
        raise Exception(f"Role with name '{role}' not found")
    user_in = UserCreate(
        full_name=random_lower_string(),
        email=random_email(),
        phone=random_lower_string(),
        password=random_lower_string(),
        role_id=current_role.id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    headers = {"Authorization": f"Bearer {user.token}"}
    return headers


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        super_admin = db.exec(select(Role).where(Role.name == "super_admin")).first()
        if not super_admin:
            raise Exception("Role with name 'super_admin' not found")
        role_id = super_admin.id
        user_in_create = UserCreate(
            email=email,
            password=password,
            full_name=random_lower_string(),
            phone=random_lower_string(),
            role_id=role_id,
        )
        user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(
            full_name=user.full_name,
            phone=user.phone,
            role_id=user.role_id,
            email=user.email,
            password=password,
        )
        if not user.id:
            raise Exception("User id not set")
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)
