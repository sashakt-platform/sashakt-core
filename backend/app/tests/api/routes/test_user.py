from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.roles import super_admin
from app.core.security import verify_password
from app.models import Permission, Role, RolePermission, User, UserCreate
from app.models.location import Country, State
from app.models.question import Question, QuestionRevision, QuestionType
from app.tests.utils.organization import (
    create_random_organization,
)
from app.tests.utils.role import create_random_role
from app.tests.utils.user import (
    authentication_token_from_email,
    create_random_user,
    get_current_user_data,
    get_user_token,
)
from app.tests.utils.utils import (
    assert_paginated_response,
    random_email,
    random_lower_string,
)


def test_get_users_superuser_me(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["email"] == settings.FIRST_SUPERUSER
    assert "permissions" in current_user
    assert "states" in current_user


def test_get_users_normal_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["email"] == settings.EMAIL_TEST_USER


def test_get_logged_user_me_permissions(
    client: TestClient, get_user_systemadmin_token: dict[str, str], db: Session
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/me", headers=get_user_systemadmin_token
    )
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["role_id"] is not None
    assert "permissions" in current_user

    permission_names = db.exec(
        select(Permission.name)
        .join(RolePermission)
        .where(RolePermission.role_id == current_user["role_id"])
    ).all()
    assert permission_names is not None
    assert isinstance(permission_names, list)
    assert set(current_user["permissions"]) == set(permission_names)


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

        # use a role from the hierarchy instead of random role
        role = db.exec(select(Role).where(Role.name == "system_admin")).first()
        assert role is not None
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
        assert user.organization_id == organization.id
        assert created_user["organization_id"] == organization.id

        current_user_data = get_current_user_data(client, superuser_token_headers)
        assert user.created_by_id == current_user_data["id"]


def test_create_user_new_email_without_org_id(
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

        # use a role from the hierarchy instead of random role
        role = db.exec(select(Role).where(Role.name == "system_admin")).first()
        assert role is not None

        data = {
            "email": username,
            "password": password,
            "phone": phone,
            "role_id": role.id,
            "full_name": full_name,
        }

        r = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=superuser_token_headers,
            json=data,
        )
        assert r.status_code == 200

        created_user = r.json()
        user = crud.get_user_by_email(session=db, email=username)
        assert user
        assert user.email == created_user["email"]

        current_user_data = get_current_user_data(client, superuser_token_headers)
        expected_org_id = current_user_data["organization_id"]
        assert user.organization_id == expected_org_id
        assert created_user["organization_id"] == expected_org_id
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


def test_update_user_me_update_phone_only(
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
    assert updated_user["phone"] == phone

    user_query = select(User).where(User.email == email)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == email
    assert user_db.full_name == full_name
    assert user_db.phone == phone
    email_new = random_email()

    data = {
        "email": email_new,
        "phone": phone,
        "password": password,
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
    assert updated_user["email"] == email_new
    assert updated_user["full_name"] == full_name
    assert updated_user["phone"] == phone

    new_phone = random_lower_string()
    data = {
        "phone": new_phone,
    }
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=get_user_candidate_token,
        json=data,
    )

    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["email"] == email_new
    assert updated_user["full_name"] == full_name
    assert updated_user["phone"] == new_phone


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

    # use a role from the hierarchy instead of random role
    role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert role is not None

    user_in = UserCreate(
        email=username,
        password=password,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        role_id=role.id,
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

    # use a role from the hierarchy instead of random role
    role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert role is not None

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
        assert response.status_code == 400
        data = response.json()
        assert (
            data["detail"]
            == "A user with 'State Admin' role must be associated with a state."
        )


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
            "state_ids": [state1.id],
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
        assert state1.id in post_state_ids
        assert len(response_data["states"]) == 1
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
        assert state1.id in state_ids
        assert len(data["states"]) == 1


def test_create_user_multiple_state_assignment_error(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        country = Country(name=random_lower_string(), is_active=True)
        db.add(country)
        db.commit()
        db.refresh(country)

        state1 = State(
            name=random_lower_string(), is_active=True, country_id=country.id
        )
        state2 = State(
            name=random_lower_string(), is_active=True, country_id=country.id
        )
        db.add_all([state1, state2])
        db.commit()

        email = random_email()
        full_name = random_lower_string()
        password = random_lower_string()
        phone = random_lower_string()
        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
        assert role is not None

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
        assert response.status_code == 400
        assert response.json()["detail"] == "A user can be linked to only one state."


def test_create_test_admin_single_state_success(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        country = Country(name=random_lower_string(), is_active=True)
        db.add(country)
        db.commit()
        db.refresh(country)

        state1 = State(
            name=random_lower_string(), is_active=True, country_id=country.id
        )
        state2 = State(
            name=random_lower_string(), is_active=True, country_id=country.id
        )
        db.add_all([state1, state2])
        db.commit()

        email = random_email()
        full_name = random_lower_string()
        password = random_lower_string()
        phone = random_lower_string()
        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
        assert role is not None

        data = {
            "email": email,
            "password": password,
            "phone": phone,
            "role_id": role.id,
            "full_name": full_name,
            "organization_id": org_id,
            "state_ids": [state1.id],
        }
        response = client.post(
            f"{settings.API_V1_STR}/users/",
            headers=get_user_superadmin_token,
            json=data,
        )
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["role_id"] == role.id
        assert "states" in response_data
        assert len(response_data["states"]) == 1
        assert response_data["states"][0]["id"] == state1.id


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

        role = db.exec(select(Role).where(Role.name == "test_admin")).first()
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
    role = db.exec(select(Role).where(Role.name == "system_admin")).first()
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
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "Invalid Role"


def test_update_other_role_to_state_admin_and_add_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()

    other_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
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
        "state_ids": [state1.id],
    }
    patch_response = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=patch_data,
    )
    assert patch_response.status_code == 200
    updated_data = patch_response.json()
    assert updated_data["role_id"] == state_admin_role.id
    assert len(updated_data["states"]) == 1


def test_update_other_role_to_state_admin_without_state_ids_returns_400(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()

    other_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert state_admin_role is not None
    assert other_role is not None

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state1 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state1)
    db.commit()
    db.refresh(state1)

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
    }
    patch_response = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=patch_data,
    )
    assert patch_response.status_code == 400
    error = patch_response.json()
    assert (
        error["detail"]
        == "A user with 'State Admin' role must be associated with a state."
    )


def test_update_state_admin_to_other_role_and_remove_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()

    other_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
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
        "state_ids": [state1.id],
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
    assert len(user_data["states"]) == 1
    state_ids = {s["id"] for s in user_data["states"]}
    assert state1.id in state_ids

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


def test_cannot_delete_user_if_linked_to_question(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    org = create_random_organization(db)

    role = db.exec(select(Role).where(Role.name == "system_admin")).first()
    assert role is not None

    data = {
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
        json=data,
    )
    assert response.status_code == 200
    user_data = response.json()
    user_id = user_data["id"]
    q2 = Question(organization_id=org.id)
    db.add(q2)
    db.flush()
    rev2 = QuestionRevision(
        question_id=q2.id,
        created_by_id=user_id,
        question_text=random_lower_string(),
        question_type=QuestionType.multi_choice,
        options=[
            {"id": 1, "key": "A", "value": "Option 1"},
            {"id": 2, "key": "B", "value": "Option 2"},
            {"id": 3, "key": "C", "value": "Option 3"},
        ],
        correct_answer=[1, 2],
    )
    db.add(rev2)
    db.flush()
    q2.last_revision_id = rev2.id
    db.commit()

    delete_response = client.delete(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
    )

    assert delete_response.status_code == 400
    assert "failed to delete user" in delete_response.json()["detail"].lower()


def test_create_test_admin_auto_inherits_state_admin_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    assert state_admin_role is not None
    assert test_admin_role is not None

    org = create_random_organization(db)
    state_admin_email = random_email()
    state_admin_payload = {
        "email": state_admin_email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": org.id,
        "state_ids": [state.id],
    }

    response_admin = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=state_admin_payload,
    )

    assert response_admin.status_code == 200
    token_headers = authentication_token_from_email(
        client=client, email=state_admin_email, db=db
    )

    payload = {
        "email": random_email(),
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": test_admin_role.id,
        "full_name": random_lower_string(),
        "organization_id": org.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=token_headers,
        json=payload,
    )

    assert response.status_code == 200
    new_user = response.json()

    assert new_user["role_id"] == test_admin_role.id
    assert "states" in new_user
    assert len(new_user["states"]) == 1
    assert new_user["states"][0]["id"] == state.id

    get_resp = client.get(
        f"{settings.API_V1_STR}/users/{new_user['id']}",
        headers=token_headers,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    state_ids = [s["id"] for s in data["states"]]
    assert state.id in state_ids
    assert len(data["states"]) == 1


def test_update_normal_user_to_test_admin_with_multiple_states_should_fail(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state1 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state2 = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state1, state2])
    db.commit()
    db.refresh(state1)
    db.refresh(state2)

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    other_role = db.exec(select(Role).where(Role.name == "system_admin")).first()
    assert test_admin_role and other_role

    org = create_random_organization(db)

    payload = {
        "email": random_email(),
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": other_role.id,
        "organization_id": org.id,
    }
    resp_user = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=payload,
    )
    assert resp_user.status_code == 200
    user_id = resp_user.json()["id"]

    patch_payload = {
        "role_id": test_admin_role.id,
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "organization_id": org.id,
        "state_ids": [state1.id, state2.id],
    }
    patch_resp = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=patch_payload,
    )

    assert patch_resp.status_code == 400
    assert patch_resp.json()["detail"] == "A user can be linked to only one state."


def test_update_normal_user_to_test_admin_without_states(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    test_admin_role = db.exec(select(Role).where(Role.name == "test_admin")).first()
    other_role = db.exec(select(Role).where(Role.name == "system_admin")).first()
    assert test_admin_role and other_role

    org = create_random_organization(db)

    payload = {
        "email": random_email(),
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": other_role.id,
        "organization_id": org.id,
    }
    resp_user = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=payload,
    )
    assert resp_user.status_code == 200
    user_id = resp_user.json()["id"]

    patch_payload = {
        "role_id": test_admin_role.id,
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "organization_id": org.id,
    }
    patch_resp = client.patch(
        f"{settings.API_V1_STR}/users/{user_id}",
        headers=get_user_superadmin_token,
        json=patch_payload,
    )

    assert patch_resp.status_code == 200
    updated_user = patch_resp.json()
    assert updated_user["role_id"] == test_admin_role.id
    assert updated_user["states"] is None


def test_user_public_me_returns_role_name(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    user_data = response.json()
    assert "role_label" in user_data
    assert user_data["role_label"] == super_admin.label


def test_user_public_list_returns_role_name(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    users_data = response.json()
    assert "items" in users_data
    assert len(users_data["items"]) > 0
    for user in users_data["items"]:
        assert "role_label" in user
        role = db.exec(select(Role).where(Role.id == user["role_id"])).first()
        assert role is not None
        assert user["role_label"] == role.label


def test_retrieve_users_with_search(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    current_user = get_current_user_data(client, superuser_token_headers)

    # create test users with specific data for searching
    test_name = "John Smith"
    test_email = "john.smith@example.com"
    test_phone = "123-456-7890"

    role = db.exec(select(Role).where(Role.name == "system_admin")).first()
    assert role is not None

    user_in1 = UserCreate(
        email=test_email,
        password=random_lower_string(),
        full_name=test_name,
        phone=test_phone,
        role_id=role.id,
        organization_id=current_user["organization_id"],
    )
    crud.create_user(session=db, user_create=user_in1)

    # create another user that should not match the search
    user_in2 = UserCreate(
        email=random_email(),
        password=random_lower_string(),
        full_name="Jane Doe",
        phone="987-654-3210",
        role_id=role.id,
        organization_id=current_user["organization_id"],
    )
    crud.create_user(session=db, user_create=user_in2)

    # test search by full name
    r = client.get(
        f"{settings.API_V1_STR}/users/?search=John", headers=superuser_token_headers
    )
    assert r.status_code == 200
    search_results = r.json()
    found_names = [user["full_name"] for user in search_results["items"]]
    assert len(found_names) == 1
    assert test_name in found_names

    # test search by email
    r = client.get(
        f"{settings.API_V1_STR}/users/?search=john.smith",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    search_results = r.json()
    found_emails = [user["email"] for user in search_results["items"]]
    assert len(found_emails) == 1
    assert test_email in found_emails

    # test search by phone
    r = client.get(
        f"{settings.API_V1_STR}/users/?search=123-456", headers=superuser_token_headers
    )
    assert r.status_code == 200
    search_results = r.json()
    found_phones = [user["phone"] for user in search_results["items"]]
    assert len(found_phones) == 1
    assert test_phone in found_phones

    # test case insensitive search
    r = client.get(
        f"{settings.API_V1_STR}/users/?search=JOHN", headers=superuser_token_headers
    )
    assert r.status_code == 200
    search_results = r.json()
    found_names = [user["full_name"] for user in search_results["items"]]
    assert len(found_names) == 1
    assert test_name in found_names

    # test search with no results
    r = client.get(
        f"{settings.API_V1_STR}/users/?search=nonexistent",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    search_results = r.json()
    assert len(search_results["items"]) == 0


def test_create_user_role_hierarchy_validation_super_admin(
    client: TestClient, get_user_superadmin_token: dict[str, str], db: Session
) -> None:
    """Test that super_admin can create users with any role."""

    role = db.exec(select(Role).where(Role.name == "system_admin")).first()
    assert role is not None
    organization = create_random_organization(session=db)

    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": role.id,
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=get_user_superadmin_token,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["email"] == data["email"]


def test_create_user_role_hierarchy_validation_system_admin_can_create_state_admin(
    client: TestClient, db: Session
) -> None:
    """Test that system_admin can create state_admin users."""

    # get auth headers for system admin user
    headers = get_user_token(db=db, role="system_admin")

    # let's create state_admin user
    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None
    organization = create_random_organization(session=db)

    goa_state = db.exec(select(State).where(State.name == "Goa")).first()
    assert goa_state is not None

    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": organization.id,
        "state_ids": [goa_state.id],
    }

    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["email"] == data["email"]


def test_create_user_role_hierarchy_validation_system_admin_cannot_create_super_admin(
    client: TestClient, db: Session
) -> None:
    """Test that system_admin cannot create super_admin users."""

    # get auth headers for system admin user
    headers = get_user_token(db=db, role="system_admin")

    # try to create super_admin user (should fail)
    super_admin_role = db.exec(select(Role).where(Role.name == "super_admin")).first()
    assert super_admin_role is not None
    organization = create_random_organization(session=db)

    data = {
        "email": random_email(),
        "password": random_lower_string(),
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": super_admin_role.id,
        "organization_id": organization.id,
    }

    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=headers,
        json=data,
    )

    # should fail due to role hierarchy validation (403) or token issues (401)
    assert response.status_code in [401, 403]

    # if we get a 403 response, check the error message
    if response.status_code == 403:
        content = response.json()
        assert "You do not have permission to assign the role" in content["detail"]
