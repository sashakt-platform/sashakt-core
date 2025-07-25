from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import verify_password
from app.crud import create_user
from app.models import UserCreate
from app.tests.utils.organization import create_random_organization
from app.tests.utils.role import create_random_role
from app.tests.utils.user import user_authentication_headers
from app.tests.utils.utils import random_email, random_lower_string
from app.utils import generate_password_reset_token


def test_get_access_token(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert "expires_in" in tokens
    assert "token_type" in tokens
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert tokens["token_type"] == "bearer"


def test_get_access_token_incorrect_password(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": "incorrect",
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    assert r.status_code == 400


def test_refresh_token(client: TestClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200

    refresh_data = {"refresh_token": tokens["refresh_token"]}
    r = client.post(f"{settings.API_V1_STR}/login/refresh-token", json=refresh_data)
    new_tokens = r.json()
    assert r.status_code == 200
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert "expires_in" in new_tokens
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    assert new_tokens["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # New refresh token should be different (token rotation)
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


def test_refresh_token_invalid(client: TestClient) -> None:
    refresh_data = {"refresh_token": "invalid_token"}
    r = client.post(f"{settings.API_V1_STR}/login/refresh-token", json=refresh_data)
    assert r.status_code == 401


def test_refresh_token_reuse_prevention(client: TestClient) -> None:
    """Test that old refresh tokens cannot be reused after refresh"""
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    assert r.status_code == 200

    # Use refresh token once
    refresh_data = {"refresh_token": tokens["refresh_token"]}
    r = client.post(f"{settings.API_V1_STR}/login/refresh-token", json=refresh_data)
    # new_tokens = r.json()
    assert r.status_code == 200

    # Try to use the old refresh token again - should fail
    r = client.post(f"{settings.API_V1_STR}/login/refresh-token", json=refresh_data)
    assert r.status_code == 401


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/test-token",
        headers=superuser_token_headers,
    )
    result = r.json()
    assert r.status_code == 200
    assert "email" in result


def test_recovery_password(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    with (
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        email = "test@example.com"
        r = client.post(
            f"{settings.API_V1_STR}/password-recovery/{email}",
            headers=normal_user_token_headers,
        )
        assert r.status_code == 200
        assert r.json() == {"message": "Password recovery email sent"}


def test_recovery_password_user_not_exits(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    email = "jVgQr@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/{email}",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 404


def test_reset_password(client: TestClient, db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    new_password = random_lower_string()

    role = create_random_role(db)
    organization = create_random_organization(db)
    db.add_all([role, organization])
    db.commit()

    user_create = UserCreate(
        email=email,
        full_name=random_lower_string(),
        phone=random_lower_string(),
        password=password,
        is_active=True,
        role_id=role.id,
        organization_id=organization.id,
    )
    user = create_user(session=db, user_create=user_create)
    token = generate_password_reset_token(email=email)
    headers = user_authentication_headers(client=client, email=email, password=password)
    data = {"new_password": new_password, "token": token}

    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=headers,
        json=data,
    )

    assert r.status_code == 200
    assert r.json() == {"message": "Password updated successfully"}

    db.refresh(user)
    assert verify_password(new_password, user.hashed_password)


def test_reset_password_invalid_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"new_password": "changethis", "token": "invalid"}
    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=superuser_token_headers,
        json=data,
    )
    response = r.json()

    assert "detail" in response
    assert r.status_code == 400
    assert response["detail"] == "Invalid token"
