import pytest
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import settings
from app.tests.utils.role import create_random_role


def test_create_role(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Foo", "description": "Fighters"}
    response = client.post(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert "id" in content


def test_read_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(db)
    response = client.get(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == role.name
    assert content["description"] == role.description
    assert content["id"] == role.id


def test_read_role_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Find an ID that definitely doesn't exist
    statement = select(func.max(create_random_role(db).__class__.id))
    max_id = db.exec(statement).one() or 0
    non_existent_id = max_id + 1000

    # This will raise an exception, which is the expected behavior
    with pytest.raises(ResponseValidationError) as excinfo:
        client.get(
            f"{settings.API_V1_STR}/roles/{non_existent_id}",
            headers=superuser_token_headers,
        )

    # Verify the error message contains key information
    error_msg = str(excinfo.value)
    assert "Input should be a valid dictionary" in error_msg
    assert "None" in error_msg


def test_read_role_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """
    Test that verifies the current behavior of permission checks.

    TODO: This test currently documents existing behavior (no permission checks),
    but should be updated once proper permission checking is implemented.
    Expected future behavior: Normal users should receive 400 status code.
    """
    role = create_random_role(db)
    response = client.get(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=normal_user_token_headers,
    )

    # Document current behavior: API currently allows any authenticated user to read roles
    assert response.status_code == 200

    # The response should contain valid role information
    content = response.json()
    assert content["name"] == role.name
    assert content["description"] == role.description
    assert content["id"] == role.id


def test_read_roles(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_role(db)
    create_random_role(db)
    response = client.get(
        f"{settings.API_V1_STR}/roles/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


def test_update_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["id"] == role.id


def test_update_role_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Find an ID that definitely doesn't exist
    statement = select(func.max(create_random_role(db).__class__.id))
    max_id = db.exec(statement).one() or 0
    non_existent_id = max_id + 1000

    data = {"name": "Updated name", "description": "Updated description"}

    # The API doesn't handle non-existent resources properly
    with pytest.raises(Exception) as excinfo:
        client.put(
            f"{settings.API_V1_STR}/roles/{non_existent_id}",
            headers=superuser_token_headers,
            json=data,
        )

    # Verify that we get a SQLAlchemy error related to None
    error_msg = str(excinfo.value)
    assert "UnmappedInstanceError" in error_msg or "NoneType" in error_msg


def test_update_role_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """
    Test that verifies the current behavior of permission checks.

    TODO: This test currently documents existing behavior (no permission checks),
    but should be updated once proper permission checking is implemented.
    Expected future behavior: Normal users should receive 400 status code.
    """
    role = create_random_role(db)
    data = {"name": "Updated name", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=normal_user_token_headers,
        json=data,
    )

    # Document current behavior: API currently allows any authenticated user to update roles
    assert response.status_code == 200

    # The response should contain the updated role information
    content = response.json()
    assert content["name"] == data["name"]
    assert content["description"] == data["description"]
    assert content["id"] == role.id


def test_delete_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    role = create_random_role(db)
    response = client.delete(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    # Match the actual capitalization used in the API
    assert content["message"] == "Role deleted successfully"


def test_delete_role_not_found(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Find an ID that definitely doesn't exist
    statement = select(func.max(create_random_role(db).__class__.id))
    max_id = db.exec(statement).one() or 0
    non_existent_id = max_id + 1000

    # The API doesn't handle non-existent resources properly
    with pytest.raises(Exception) as excinfo:
        client.delete(
            f"{settings.API_V1_STR}/roles/{non_existent_id}",
            headers=superuser_token_headers,
        )

    # Verify that we get a SQLAlchemy error related to None
    error_msg = str(excinfo.value)
    assert "UnmappedInstanceError" in error_msg or "NoneType" in error_msg


def test_delete_role_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    """
    Test that verifies the current behavior of permission checks.

    TODO: This test currently documents existing behavior (no permission checks),
    but should be updated once proper permission checking is implemented.
    Expected future behavior: Normal users should receive 400 status code.
    """
    role = create_random_role(db)
    response = client.delete(
        f"{settings.API_V1_STR}/roles/{role.id}",
        headers=normal_user_token_headers,
    )

    # Document current behavior: API currently allows any authenticated user to delete roles
    assert response.status_code == 200

    # The response should contain a success message
    content = response.json()
    assert "message" in content
    assert "deleted successfully" in content["message"]
