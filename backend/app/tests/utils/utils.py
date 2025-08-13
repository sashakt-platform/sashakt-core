import random
import string

from fastapi.testclient import TestClient
from httpx import Response

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


def assert_paginated_response(
    response: Response,
    expected_total: int = 1,
    expected_page: int = 1,
    expected_pages: int = 1,
    expected_size: int = 25,
    min_expected_total: int | None = None,
    min_expected_pages: int | None = None,
) -> None:
    assert response.status_code == 200
    data = response.json()
    required_fields = ["page", "size", "pages", "total", "items"]
    for field in required_fields:
        assert field in data

    assert data["page"] == expected_page
    assert data["size"] == expected_size
    if min_expected_pages is not None:
        assert data["pages"] >= min_expected_pages
    else:
        assert data["pages"] == expected_pages
    if min_expected_total is not None:
        assert data["total"] >= min_expected_total
    else:
        assert data["total"] == expected_total
