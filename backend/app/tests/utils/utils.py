import random
import string
from typing import Any, cast

from fastapi.testclient import TestClient

from app.core.config import settings


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def get_user_data_from_me_route(
    client: TestClient, auth_header: dict[str, Any]
) -> dict[str, Any]:
    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=auth_header,
    )
    assert response.status_code == 200, f"Failed to fetch user info: {response.text}"
    user_data = cast(dict[str, Any], response.json())
    return user_data
