from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.security import verify_password
from app.models import Role, User, UserCreate
from app.models.location import Country, State
from app.tests.utils.organization import (
    assert_paginated_response,
    create_random_organization,
)
from app.tests.utils.role import create_random_role
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import random_email, random_lower_string


def test_get_users_superuser_me(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["email"] == settings.FIRST_SUPERUSER


def test_get_users_normal_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["email"] == settings.EMAIL_TEST_USER


def test_create_user_new_email(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        username = random_email()
        full_name = random_lower_string()
        password = random_lower_string()
        phone = random_lower_string()
        role = create_random_role(db)
        organization = create_random_organization(db)
        data = {
            "email": username,
            "password": password,
            "phone": phone,
            "role_id": role.id,
            "full_name": full_name,
            "organization_id": organization.id,
        }
        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert 200 <= r.status_code < 300
        created_user = r.json()
        user = crud.get_user_by_email(session=db, email=username)
        assert user
        assert user.email == created_user["email"]

        current_user_data = get_current_user_data(client, superuser_token_headers)
        assert user.created_by_id == current_user_data["id"]


def test_get_existing_user(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    current_user = get_current_user_data(client, get_user_superadmin_token)
    organization = create_random_organization(db)
    username = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    phone = random_lower_string()
    role = create_random_role(db)
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=full_name,
        phone=phone,
        role_id=role.id,
        organization_id=current_user["organization_id"],
    )
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id
    r = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = crud.get_user_by_email(session=db, email=username)
    assert existing_user
    assert existing_user.email == api_user["email"]

    user_in = UserCreate(
        email=random_email(),
        password=password,
        full_name=full_name,
        phone=random_lower_string(),
        role_id=role.id,
        organization_id=organization.id,
    )
    user = crud.create_user(
        session=db, user_create=user_in, created_by_id=current_user["id"]
    )
    user_id = user.id
    response = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
    )
    assert 400 <= response.status_code < 500


def test_get_existing_user_current_user(client: TestClient, db: Session) -> None:
    username = random_email()
    password = random_lower_string()
    role = db.exec(select(Role.id).where(Role.name == "test_admin")).first()
    organization = create_random_organization(db)
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=role,
        organization_id=organization.id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id

    login_data = {
        "username": username,
        "password": password,
    }
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data=login_data,
    )
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}

    r = client.get(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=headers,
    )
    assert 200 <= r.status_code < 300
    api_user = r.json()
    existing_user = crud.get_user_by_email(session=db, email=username)
    assert existing_user
    assert existing_user.email == api_user["email"]


# TODO: Let's fix this once we have permissions in place
# def test_get_existing_user_permissions_error(
#     client: TestClient, normal_user_token_headers: dict[str, str]
# ) -> None:
#     r = client.get(
#         f"{settings.API_V1_STR}/users/444444",
#         headers=normal_user_token_headers,
#     )
#     assert r.status_code == 403
#     assert r.json() == {"detail": "The user doesn't have enough privileges"}
#


def test_create_user_existing_username(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    username = random_email()
    full_name = random_lower_string()
    password = random_lower_string()
    phone = random_lower_string()
    role = create_random_role(db)
    organization = create_random_organization(db)
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=role.id,
        organization_id=organization.id,
    )
    crud.create_user(session=db, user_create=user_in)
    data = {
        "email": username,
        "password": password,
        "phone": phone,
        "role_id": role.id,
        "full_name": full_name,
        "organization_id": organization.id,
    }
    r = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=data,
    )
    created_user = r.json()
    assert r.status_code == 400
    assert "_id" not in created_user


# TODO: let's fix this once we have permissions in place
# def test_create_user_by_normal_user(
#     client: TestClient, normal_user_token_headers: dict[str, str]
# ) -> None:
#     username = random_email()
#     password = random_lower_string()
#     data = {"email": username, "password": password}
#     r = client.post(
#         f"{settings.API_V1_STR}/users/",
#         headers=normal_user_token_headers,
#         json=data,
#     )
#     assert r.status_code == 403
#
# TODO: let's fix this once we have permissions in place


def test_retrieve_users(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    current_user = get_current_user_data(client, superuser_token_headers)
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=current_user["organization_id"],
    )
    crud.create_user(session=db, user_create=user_in)

    username2 = random_email()
    password2 = random_lower_string()
    user_in2 = UserCreate(
        email=username2,
        password=password2,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=current_user["organization_id"],
    )
    crud.create_user(session=db, user_create=user_in2)

    r = client.get(f"{settings.API_V1_STR}/users/", headers=superuser_token_headers)
    all_users = r.json()
    assert len(all_users["items"]) > 2

    assert_paginated_response(r, min_expected_total=1)
    for item in all_users["items"]:
        assert "email" in item
        assert "full_name" in item
        assert "phone" in item
        assert "role_id" in item
        assert "organization_id" in item
        assert item["organization_id"] == current_user["organization_id"]


def test_update_user_me(
    client: TestClient, get_user_candidate_token: dict[str, str], db: Session
) -> None:
    email = random_email()
    full_name = random_lower_string()
    password = random_lower_string()
    phone = random_lower_string()
    role = create_random_role(db)
    organization = create_random_organization(db)
    data = {
        "email": email,
        "password": password,
        "phone": phone,
        "role_id": role.id,
        "full_name": full_name,
        "organization_id": organization.id,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=get_user_candidate_token,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["email"] == email
    assert updated_user["full_name"] == full_name

    user_query = select(User).where(User.email == email)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == email
    assert user_db.full_name == full_name

    user = create_random_user(db)

    data = {
        "email": user.email,
        "phone": random_lower_string(),
        "password": password,
        "role_id": user.role_id,
        "full_name": user.full_name,
        "organization_id": organization.id,
    }
    response = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {user.token}"},
        json=data,
    )

    assert response.status_code == 401


def test_update_password_me(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    new_password = random_lower_string()
    data = {
        "current_password": settings.FIRST_SUPERUSER_PASSWORD,
        "new_password": new_password,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["message"] == "Password updated successfully"

    user_query = select(User).where(User.email == settings.FIRST_SUPERUSER)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == settings.FIRST_SUPERUSER
    assert verify_password(new_password, user_db.hashed_password)

    # Revert to the old password to keep consistency in test
    old_data = {
        "current_password": new_password,
        "new_password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=superuser_token_headers,
        json=old_data,
    )
    db.refresh(user_db)

    assert r.status_code == 200
    assert verify_password(settings.FIRST_SUPERUSER_PASSWORD, user_db.hashed_password)


def test_update_password_me_incorrect_password(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    new_password = random_lower_string()
    data = {"current_password": new_password, "new_password": new_password}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 400
    updated_user = r.json()
    assert updated_user["detail"] == "Incorrect password"


def test_update_user_me_email_exists(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=create_random_organization(db).id,
    )
    user = crud.create_user(session=db, user_create=user_in)

    data = {"email": user.email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User with this email already exists"


def test_update_password_me_same_password_error(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "current_password": settings.FIRST_SUPERUSER_PASSWORD,
        "new_password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me/password",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 400
    updated_user = r.json()
    assert (
        updated_user["detail"] == "New password cannot be the same as the current one"
    )


def test_register_user(
    client: TestClient,
    db: Session,
    get_user_superadmin_token: dict[str, str],
) -> None:
    username = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    phone = random_lower_string()
    role_id = create_random_role(db).id
    organization = create_random_organization(db)
    data = {
        "email": username,
        "password": password,
        "full_name": full_name,
        "phone": phone,
        "role_id": role_id,
        "organization_id": organization.id,
    }
    r = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json=data,
        headers=get_user_superadmin_token,
    )
    assert r.status_code == 200
    created_user = r.json()
    assert created_user["email"] == username
    assert created_user["full_name"] == full_name

    user_query = select(User).where(User.email == username)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == username
    assert user_db.full_name == full_name
    assert verify_password(password, user_db.hashed_password)


def test_register_user_already_exists_error(
    db: Session,
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    password = random_lower_string()
    full_name = random_lower_string()
    phone = random_lower_string()
    role_id = create_random_role(db).id
    organization = create_random_organization(db)
    data = {
        "email": settings.FIRST_SUPERUSER,
        "password": password,
        "full_name": full_name,
        "phone": phone,
        "role_id": role_id,
        "organization_id": organization.id,
    }
    r = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json=data,
        headers=get_user_superadmin_token,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "The user with this email already exists in the system"


def test_update_user(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()

    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=create_random_organization(db).id,
    )
    user = crud.create_user(session=db, user_create=user_in)

    data = {
        "email": user_in.email,
        "password": user_in.password,
        "full_name": "Updated_full_name",
        "phone": user_in.phone,
        "role_id": user_in.role_id,
        "organization_id": user_in.organization_id,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()

    assert updated_user["full_name"] == "Updated_full_name"

    user_query = select(User).where(User.email == username)
    user_db = db.exec(user_query).first()
    db.refresh(user_db)
    assert user_db
    assert user_db.full_name == "Updated_full_name"


def test_update_user_not_exists(
    db: Session, client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "full_name": "Updated_full_name",
        "phone": random_lower_string(),
        "role_id": create_random_role(db).id,
        "organization_id": create_random_organization(db).id,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/-1",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "The user with this id does not exist in the system"


def test_update_user_email_exists(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=create_random_organization(db).id,
    )
    user = crud.create_user(session=db, user_create=user_in)

    username2 = random_email()
    password2 = random_lower_string()
    user_in2 = UserCreate(
        email=username2,
        password=password2,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=create_random_organization(db).id,
    )
    user2 = crud.create_user(session=db, user_create=user_in2)

    data = {
        "email": user2.email,
        "password": user_in.password,
        "full_name": "Updated_full_name",
        "phone": user_in.phone,
        "role_id": user_in.role_id,
        "organization_id": user_in.organization_id,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User with this email already exists"


def test_delete_user_me(
    client: TestClient,
    db: Session,
) -> None:
    username = random_email()
    password = random_lower_string()
    role = db.exec(select(Role.id).where(Role.name == "system_admin")).first()
    organization_id = create_random_organization(db).id
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=role,
        organization_id=organization_id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id

    login_data = {
        "username": username,
        "password": password,
    }
    r = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data=login_data,
    )
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}

    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
    )
    assert r.status_code == 200
    deleted_user = r.json()
    assert deleted_user["message"] == "User deleted successfully"
    result = db.exec(select(User).where(User.id == user_id)).first()
    assert result is None

    user_query = select(User).where(User.id == user_id)
    user_db = db.exec(user_query).first()
    assert user_db is None


# TODO: let's fix this once we have permissions in place
# def test_delete_user_me_as_superuser(
#     client: TestClient, superuser_token_headers: dict[str, str]
# ) -> None:
#     r = client.delete(
#         f"{settings.API_V1_STR}/users/me",
#         headers=superuser_token_headers,
#     )
#     assert r.status_code == 403
#     response = r.json()
#     assert response["detail"] == "Super users are not allowed to delete themselves"


def test_delete_user_super_user(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=create_random_role(db).id,
        organization_id=create_random_organization(db).id,
    )
    user = crud.create_user(session=db, user_create=user_in)
    user_id = user.id
    r = client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    deleted_user = r.json()
    assert deleted_user["message"] == "User deleted successfully"
    result = db.exec(select(User).where(User.id == user_id)).first()
    assert result is None


def test_delete_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/users/0",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "User not found"


def test_delete_user_current_super_user_error(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    super_user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert super_user
    user_id = super_user.id

    r = client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "Super users are not allowed to delete themselves"


# TODO: let's fix this once we have permissions in place
# def test_delete_user_without_privileges(
#     client: TestClient, normal_user_token_headers: dict[str, str], db: Session
# ) -> None:
#     username = random_email()
#     password = random_lower_string()
#     user_in = UserCreate(email=username, password=password)
#     user = crud.create_user(session=db, user_create=user_in)
#
#     r = client.delete(
#         f"{settings.API_V1_STR}/users/{user.id}",
#         headers=normal_user_token_headers,
#     )
#     assert r.status_code == 403
#     assert r.json()["detail"] == "The user doesn't have enough privileges"


def test_create_inactive_user_not_listed(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    username = random_email()
    password = random_lower_string()
    full_name = random_lower_string()
    phone = random_lower_string()
    role = create_random_role(db)
    organization = create_random_organization(db)
    data = {
        "email": username,
        "password": password,
        "phone": phone,
        "role_id": role.id,
        "full_name": full_name,
        "organization_id": organization.id,
        "is_active": False,  # Create inactive user
    }
    r = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 200
    created_user = r.json()
    assert created_user["email"] == username
    user_id = created_user["id"]
    assert created_user["is_active"] is False
    r = client.get(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
    )
    all_users = r.json()
    assert all(item["id"] != user_id for item in all_users["items"])
    assert_paginated_response(r, min_expected_total=1)


def test_create_state_admin_without_state_id(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        email = random_email()
        full_name = random_lower_string()
        password = random_lower_string()
        phone = random_lower_string()
        role = db.exec(select(Role).where(Role.name == "state_admin")).first()
        assert role is not None
        organization = create_random_organization(db)
        data = {
            "email": email,
            "password": password,
            "phone": phone,
            "role_id": role.id,
            "full_name": full_name,
            "organization_id": organization.id,
        }
        response = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert response.status_code == 200
        data = response.json()
        assert "states" in data
        assert data["states"] is None


def test_create_state_admin_with_state_id(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        email = random_email()
        full_name = random_lower_string()
        password = random_lower_string()
        phone = random_lower_string()
        role = db.exec(select(Role).where(Role.name == "state_admin")).first()
        assert role is not None
        country = Country(name=random_lower_string(), is_active=True)
        db.add(country)
        db.commit()
        db.refresh(country)

        state1 = State(
            name=random_lower_string(), is_active=True, country_id=country.id
        )
        db.add(state1)
        db.commit()
        state2 = State(
            name=random_lower_string(), is_active=True, country_id=country.id
        )
        db.add(state2)
        db.commit()

        data = {
            "email": email,
            "password": password,
            "phone": phone,
            "role_id": role.id,
            "full_name": full_name,
            "organization_id": org_id,
            "state_ids": [state1.id, state2.id],
        }
        response = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=get_user_superadmin_token,
            json=data,
        )
        assert response.status_code == 200
        response_data = response.json()
        user_id = response_data["id"]
        assert response_data["email"] == email
        assert response_data["role_id"] == role.id
        assert role.name == "state_admin"
        assert "states" in response_data
        post_state_names = {s["name"] for s in response_data["states"]}
        post_state_ids = {s["id"] for s in response_data["states"]}
        assert state1.name in post_state_names
        assert state2.name in post_state_names
        assert state1.id in post_state_ids
        assert state2.id in post_state_ids
        assert len(response_data["states"]) == 2
        r = client.get(
            f"{settings.API_V1_STR}/users/{user_id}",
            headers=get_user_superadmin_token,
        )
        data = r.json()
        assert r.status_code == 200
        assert data["email"] == email
        assert data["role_id"] == role.id
        state_names = {s["name"] for s in data["states"]}
        state_ids = {s["id"] for s in data["states"]}
        assert state1.name in state_names
        assert state2.name in state_names
        assert state1.id in state_ids
        assert state2.id in state_ids
        assert len(data["states"]) == 2


def test_create_user_without_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        email = random_email()
        full_name = random_lower_string()
        password = random_lower_string()
        phone = random_lower_string()
        role = db.exec(select(Role).where(Role.name != "state_admin")).first()
        assert role is not None

        data = {
            "email": email,
            "password": password,
            "phone": phone,
            "role_id": role.id,
            "full_name": full_name,
            "organization_id": org_id,
        }
        response = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=get_user_superadmin_token,
            json=data,
        )
        assert response.status_code == 200
        response_data = response.json()
        user_id = response_data["id"]
        assert response_data["email"] == email
        assert response_data["role_id"] == role.id
        assert "states" in response_data
        assert not response_data["states"]

        r = client.get(
            f"{settings.API_V1_STR}/users/{user_id}",
            headers=get_user_superadmin_token,
        )
        data = r.json()
        assert r.status_code == 200
        assert data["email"] == email
        assert data["role_id"] == role.id
        assert "states" in data
        assert not data["states"]


def test_update_user_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)
    role = db.exec(select(Role).where(Role.name != "state_admin")).first()
    assert role is not None
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)
    state1 = State(name=random_lower_string(), country_id=country.id, is_active=True)
    state2 = State(name=random_lower_string(), country_id=country.id, is_active=True)
    state3 = State(name=random_lower_string(), country_id=country.id, is_active=True)
    db.add_all([state1, state2, state3])
    db.commit()
    create_payload = {
        "email": random_email(),
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": role.id,
        "full_name": random_lower_string(),
        "organization_id": org.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=create_payload,
    )
    assert response.status_code == 200
    user_data = response.json()
    user_id = user_data["id"]
    role1 = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert role1 is not None
    email = random_email()
    password = random_lower_string()
    phone = random_lower_string()

    email = random_email()
    password = random_lower_string()
    phone = random_lower_string()

    valid_patch_with_states = {
        "email": email,
        "password": password,
        "phone": phone,
        "role_id": role.id,
        "full_name": "full name",
        "organization_id": org.id,
        "state_ids": [state1.id, state3.id],
    }
    update_response = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=valid_patch_with_states,
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["states"] is None
    assert data["email"] == email
    assert data["role_id"] == role.id
    assert data["full_name"] == "full name"

    email = random_email()
    password = random_lower_string()
    phone = random_lower_string()
    invalid_role_patch = {
        "email": email,
        "password": password,
        "phone": phone,
        "role_id": -10,
        "full_name": random_lower_string(),
        "organization_id": org.id,
        "state_ids": [
            state1.id,
            state3.id,
        ],
    }
    update_response = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=invalid_role_patch,
    )
    assert update_response.status_code == 400
    assert update_response.json()["detail"] == "Invalid role ID provided."


def test_update_other_role_to_state_admin_and_remove_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    other_role = db.exec(select(Role).where(Role.name != "state_admin")).first()
    assert state_admin_role is not None
    assert other_role is not None

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state1 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state2 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state1)
    db.add(state2)
    db.commit()
    db.refresh(state1)
    db.refresh(state2)

    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": other_role.id,
        "full_name": random_lower_string(),
        "organization_id": org.id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert response.status_code == 200
    user_data = response.json()
    user_id = user_data["id"]
    assert user_data["role_id"] == other_role.id
    assert user_data["states"] is None

    patch_data = {
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "state_ids": [state1.id, state2.id],
    }
    patch_response = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=patch_data,
    )
    assert patch_response.status_code == 200
    updated_data = patch_response.json()
    assert updated_data["role_id"] == state_admin_role.id
    assert len(updated_data["states"]) == 2


def test_update_state_admin_to_other_role_and_remove_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    other_role = db.exec(select(Role).where(Role.name != "state_admin")).first()
    assert state_admin_role is not None
    assert other_role is not None

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state1 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state2 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state1)
    db.add(state2)
    db.commit()
    db.refresh(state1)
    db.refresh(state2)

    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": state_admin_role.id,
        "full_name": random_lower_string(),
        "organization_id": org.id,
        "state_ids": [state1.id, state2.id],
    }
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert response.status_code == 200
    user_data = response.json()
    user_id = user_data["id"]

    assert user_data["role_id"] == state_admin_role.id
    assert len(user_data["states"]) == 2
    state_ids = {s["id"] for s in user_data["states"]}
    assert state1.id in state_ids
    assert state2.id in state_ids

    data = {
        "role_id": other_role.id,
        "organization_id": org.id,
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "state_ids": [],
    }
    patch_response = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert patch_response.status_code == 200
    updated_data = patch_response.json()
    assert updated_data["role_id"] == other_role.id
    assert updated_data["states"] is None
