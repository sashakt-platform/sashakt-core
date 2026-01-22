from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.user import get_current_user_data
from app.tests.utils.utils import random_lower_string


def test_create_certificate(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "url": random_lower_string(),
        "is_active": True,
    }

    response = client.post(
        f"{settings.API_V1_STR}/certificate/",
        json=data,
        headers=get_user_superadmin_token,
    )

    response_data = response.json()
    assert response.status_code == 200
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["url"] == data["url"]
    assert response_data["is_active"] is True
    assert response_data["created_by_id"] == user_id
    assert "created_date" in response_data
    assert "modified_date" in response_data
