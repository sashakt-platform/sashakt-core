from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.certificate import Certificate
from app.models.test import Test
from app.tests.api.routes.test_tag import setup_user_organization
from app.tests.utils.user import get_current_user_data
from app.tests.utils.utils import assert_paginated_response, random_lower_string


def test_create_certificate(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)

    data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "url": random_lower_string(),
        "is_active": True,
        "organization_id": organization.id,
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


def test_get_certificates(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    certificate = Certificate(
        name="testcertificate",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/certificate/",
        headers=get_user_superadmin_token,
    )

    data = response.json()
    response_data = data["items"]

    assert_paginated_response(response)
    assert response.status_code == 200

    assert any(item["name"] == certificate.name for item in response_data)
    assert any(item["description"] == certificate.description for item in response_data)
    assert any(
        item["organization_id"] == certificate.organization_id for item in response_data
    )
    assert any(
        item["created_by_id"] == certificate.created_by_id for item in response_data
    )
    assert any(item["is_active"] == certificate.is_active for item in response_data)

    for name_query in ["Testcertificate", "TESTCERTIFICATE", " TeStCeRtIfIcAtE"]:
        response = client.get(
            f"{settings.API_V1_STR}/certificate/?name={name_query}",
            headers=get_user_superadmin_token,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert any(item["name"].lower() == "testcertificate" for item in data["items"])

    certificate = Certificate(
        name="testcertificateAnother",
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/certificate/?name=TESTCERTIFICATE",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2


def test_get_certificate_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == certificate.name
    assert response_data["description"] == certificate.description
    assert response_data["organization_id"] == certificate.organization_id
    assert response_data["created_by_id"] == certificate.created_by_id
    assert response_data["is_active"] is True
    assert "created_date" in response_data
    assert "modified_date" in response_data


def test_get_certificate_by_id_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/certificate/-9",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Certificate not found"


def test_update_certificate_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    update_data_a = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "url": random_lower_string(),
        "organization_id": organization_id,
    }

    response = client.put(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        json=update_data_a,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == update_data_a["name"]
    assert response_data["description"] == update_data_a["description"]
    assert response_data["url"] == update_data_a["url"]
    assert "created_date" in response_data
    assert "modified_date" in response_data

    update_data_b = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "url": random_lower_string(),
        "organization_id": organization_id,
    }

    response = client.put(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        json=update_data_b,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["name"] == update_data_b["name"]
    assert response_data["description"] == update_data_b["description"]
    assert response_data["url"] == update_data_b["url"]


def test_update_certificate_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)

    organization_id = user_data["organization_id"]

    update_data = {
        "name": random_lower_string(),
        "description": random_lower_string(),
        "url": random_lower_string(),
        "organization_id": organization_id,
    }

    response = client.put(
        f"{settings.API_V1_STR}/certificate/-90",
        json=update_data,
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "Certificate not found"


def test_delete_certificate_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    response = client.get(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["id"] == certificate.id

    response = client.delete(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 200

    assert "deleted" in response_data["message"].lower()

    response = client.get(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "Certificate not found"


def test_delete_certificate_not_found(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/certificate/-90",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 404
    assert response_data["detail"] == "Certificate not found"


def test_delete_certificate_with_associated_tests(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    test = Test(
        name=random_lower_string(),
        created_by_id=user_id,
        organization_id=organization_id,
        certificate_id=certificate.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # try deleting certificate, should throw 400 error
    response = client.delete(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        headers=get_user_superadmin_token,
    )
    response_data = response.json()

    assert response.status_code == 400
    assert "associated tests" in response_data["detail"].lower()

    # verify certificate still exists
    response = client.get(
        f"{settings.API_V1_STR}/certificate/{certificate.id}",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200


# ============== Certificate Tokens Tests ==============


def test_get_certificate_tokens_fixed_only(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test getting certificate tokens without a form returns only fixed tokens."""
    response = client.get(
        f"{settings.API_V1_STR}/certificate/tokens",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    assert "tokens" in data

    tokens = data["tokens"]
    assert len(tokens) == 3

    # Check fixed tokens
    token_names = [t["token"] for t in tokens]
    assert "test_name" in token_names
    assert "completion_date" in token_names
    assert "score" in token_names

    # Verify structure
    for token in tokens:
        assert "token" in token
        assert "label" in token


def test_get_certificate_tokens_with_form(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test getting certificate tokens with a form returns fixed + form field tokens."""
    setup_user_organization(db)

    # Create a form
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    assert form_response.status_code == 200
    form_id = form_response.json()["id"]

    # Add form fields
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "Full Name", "name": "full_name"},
        headers=get_user_superadmin_token,
    )
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "email", "label": "Email Address", "name": "email"},
        headers=get_user_superadmin_token,
    )

    # Get tokens with form_id
    response = client.get(
        f"{settings.API_V1_STR}/certificate/tokens?form_id={form_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    tokens = data["tokens"]

    # Should have 3 fixed + 2 form fields = 5 tokens
    assert len(tokens) == 5

    token_names = [t["token"] for t in tokens]
    # Fixed tokens
    assert "test_name" in token_names
    assert "completion_date" in token_names
    assert "score" in token_names
    # Form field tokens
    assert "full_name" in token_names
    assert "email" in token_names


def test_get_certificate_tokens_with_nonexistent_form(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    """Test getting certificate tokens with non-existent form_id returns only fixed tokens."""
    response = client.get(
        f"{settings.API_V1_STR}/certificate/tokens?form_id=99999",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    data = response.json()
    tokens = data["tokens"]

    # Should only have fixed tokens
    assert len(tokens) == 3


def test_get_certificate_tokens_unauthorized(
    client: TestClient,
) -> None:
    """Test getting certificate tokens without auth fails."""
    response = client.get(
        f"{settings.API_V1_STR}/certificate/tokens",
    )

    assert response.status_code == 401
