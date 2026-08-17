from typing import Any, cast

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.roles import init_org_roles, init_super_admin_role
from app.models import Organization, Role, User, UserCreate, UserUpdate
from app.tests.utils.organization import create_random_organization
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


def create_random_user(db: Session, organization_id: int | None = None) -> User:
    if organization_id is not None:
        organization = db.get(Organization, organization_id)
        if not organization:
            raise ValueError(f"Organization with ID {organization_id} not found")
    else:
        organization = create_random_organization(session=db)
    if organization.id is None:
        raise ValueError("Organization has no id")
    role = Role(
        name=random_lower_string(),
        label=random_lower_string(),
        organization_id=organization.id,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
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
        organization_id=organization.id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    return user


def get_user_token_for_org(
    *, db: Session, organization_id: int, role: str
) -> dict[str, str]:
    """
    Like `get_user_token`, but scoped to an already-existing organization
    instead of creating a fresh one. Seeds that organization's default roles
    first if they don't exist yet.
    """

    if role == "super_admin":
        init_super_admin_role(db, organization_id)
    init_org_roles(db, organization_id)

    current_role = db.exec(
        select(Role).where(Role.name == role, Role.organization_id == organization_id)
    ).first()
    if not current_role:
        current_role = Role(name=role, label=role, organization_id=organization_id)
        db.add(current_role)
        db.commit()
        db.refresh(current_role)

    user_in = UserCreate(
        full_name=random_lower_string(),
        email=random_email(),
        phone=random_lower_string(),
        password=random_lower_string(),
        role_id=current_role.id,
        organization_id=organization_id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    headers = {"Authorization": f"Bearer {user.token}"}
    return headers


def get_user_token(*, db: Session, role: str) -> dict[str, str]:
    organization = Organization(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    if organization.id is None:
        raise ValueError("Organization has no id")

    return get_user_token_for_org(db=db, organization_id=organization.id, role=role)


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = crud.get_user_by_email(session=db, email=email)
    organization = create_random_organization(db)
    if organization.id is None:
        raise ValueError("Organization has no id")
    if not user:
        init_super_admin_role(db, organization.id)
        super_admin_role = db.exec(
            select(Role).where(
                Role.name == "super_admin", Role.organization_id == organization.id
            )
        ).first()
        if not super_admin_role:
            raise Exception("Role with name 'super_admin' not found")
        role_id = super_admin_role.id
        user_in_create = UserCreate(
            email=email,
            password=password,
            full_name=random_lower_string(),
            phone=random_lower_string(),
            role_id=role_id,
            organization_id=organization.id,
        )
        user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(
            full_name=user.full_name,
            phone=user.phone,
            role_id=user.role_id,
            email=user.email,
            password=password,
            organization_id=user.organization_id,
        )
        if not user.id:
            raise Exception("User id not set")
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)


def get_org_user(client: TestClient, db: Session, token: dict[str, str]) -> User:
    organization_id = get_current_user_data(client, token)["organization_id"]
    return create_random_user(db, organization_id=organization_id)


def get_current_user_data(
    client: TestClient, auth_header: dict[str, Any]
) -> dict[str, Any]:
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=auth_header,
    )
    assert response.status_code == 200, f"Failed to fetch user info: {response.text}"
    user_data = cast(dict[str, Any], response.json())
    return user_data
