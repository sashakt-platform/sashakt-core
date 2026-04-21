import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.candidate import Candidate, CandidateTest
from app.models.certificate import Certificate
from app.models.entity import Entity, EntityType
from app.models.form import Form, FormField, FormFieldType
from app.models.location import Block, Country, District, State
from app.models.test import Test
from app.services.certificate_tokens import resolve_form_response_values
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


def test_get_certificates_filter_is_active(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    active_cert = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
        is_active=True,
    )
    inactive_cert = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
        is_active=False,
    )
    db.add(active_cert)
    db.add(inactive_cert)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/certificate/?is_active=true",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["is_active"] is True for item in items)
    assert any(item["name"] == active_cert.name for item in items)
    assert not any(item["name"] == inactive_cert.name for item in items)

    response = client.get(
        f"{settings.API_V1_STR}/certificate/?is_active=false",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["is_active"] is False for item in items)
    assert any(item["name"] == inactive_cert.name for item in items)
    assert not any(item["name"] == active_cert.name for item in items)

    response = client.get(
        f"{settings.API_V1_STR}/certificate/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    items = response.json()["items"]
    names = [item["name"] for item in items]
    assert active_cert.name in names
    assert inactive_cert.name in names


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


def test_download_certificate_invalid_token(
    client: TestClient,
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/certificate/download/nonexistent-token"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Certificate not found"


def test_download_certificate_no_certificate_on_test(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    token = str(uuid.uuid4())

    test = Test(
        name=random_lower_string(),
        organization_id=organization_id,
        certificate_id=None,
        created_by_id=user_id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    candidate = Candidate()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2025-01-01T10:00:00",
        certificate_data={"token": token},
        admin_id=user_id,
    )
    db.add(candidate_test)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/certificate/download/{token}")

    assert response.status_code == 404
    assert response.json()["detail"] == "No certificate for this test"


def test_download_certificate_certificate_not_active(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    token = str(uuid.uuid4())

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
        is_active=False,
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    test = Test(
        name=random_lower_string(),
        organization_id=organization_id,
        certificate_id=certificate.id,
        created_by_id=user_id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    candidate = Candidate()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2025-01-01T10:00:00",
        certificate_data={
            "token": token,
            "candidate_name": random_lower_string(),
            "test_name": test.name,
            "score": "70%",
            "completion_date": "2025-01-01",
        },
    )
    db.add(candidate_test)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/certificate/download/{token}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Certificate not available"


def test_download_certificate_no_provider_configured(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    organization_id = user_data["organization_id"]

    token = str(uuid.uuid4())

    certificate = Certificate(
        name=random_lower_string(),
        description=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
        url=random_lower_string(),
        is_active=True,
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    test = Test(
        name=random_lower_string(),
        organization_id=organization_id,
        certificate_id=certificate.id,
        created_by_id=user_id,
        is_active=True,
        link=random_lower_string(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    candidate = Candidate()
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    candidate_test = CandidateTest(
        test_id=test.id,
        candidate_id=candidate.id,
        device=random_lower_string(),
        consent=True,
        start_time="2025-01-01T10:00:00",
        certificate_data={
            "token": token,
            "candidate_name": random_lower_string(),
            "test_name": test.name,
            "score": "80%",
            "completion_date": "2025-01-01",
        },
    )
    db.add(candidate_test)
    db.commit()

    response = client.get(f"{settings.API_V1_STR}/certificate/download/{token}")

    assert response.status_code == 503
    assert response.json()["detail"] == "Certificate generation service not configured"


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


# ============== Token Resolution Tests ==============


def _create_form_with_fields(
    db: SessionDep, organization_id: int, user_id: int, fields: list[dict[str, Any]]
) -> tuple[Form, list[FormField]]:
    """Helper to create a form with fields directly in DB."""
    form = Form(
        name=random_lower_string(),
        organization_id=organization_id,
        created_by_id=user_id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    created_fields = []
    for i, field_data in enumerate(fields):
        field = FormField(
            form_id=form.id,
            order=i,
            **field_data,
        )
        db.add(field)
        db.commit()
        db.refresh(field)
        created_fields.append(field)

    return form, created_fields


def test_resolve_entity_field(
    db: SessionDep,
) -> None:
    """Test that entity field IDs are resolved to entity names."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    entity_type = EntityType(
        name="School",
        organization_id=organization.id,
        created_by_id=user.id,
    )
    db.add(entity_type)
    db.commit()
    db.refresh(entity_type)

    entity = Entity(
        name="ABC Public School",
        entity_type_id=entity_type.id,
        created_by_id=user.id,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.ENTITY,
                "label": "School",
                "name": "school",
                "entity_type_id": entity_type.id,
            },
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={"school": entity.id},
        session=db,
    )

    assert resolved["school"] == "ABC Public School"


def test_resolve_location_fields(
    db: SessionDep,
) -> None:
    """Test that state/district/block IDs are resolved to names."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    country = Country(name="India")
    db.add(country)
    db.commit()
    db.refresh(country)

    state = State(name="Maharashtra", country_id=country.id)
    db.add(state)
    db.commit()
    db.refresh(state)

    district = District(name="Mumbai", state_id=state.id)
    db.add(district)
    db.commit()
    db.refresh(district)

    block = Block(name="Andheri", district_id=district.id)
    db.add(block)
    db.commit()
    db.refresh(block)

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {"field_type": FormFieldType.STATE, "label": "State", "name": "state"},
            {
                "field_type": FormFieldType.DISTRICT,
                "label": "District",
                "name": "district",
            },
            {"field_type": FormFieldType.BLOCK, "label": "Block", "name": "block"},
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={
            "state": state.id,
            "district": district.id,
            "block": block.id,
        },
        session=db,
    )

    assert resolved["state"] == "Maharashtra"
    assert resolved["district"] == "Mumbai"
    assert resolved["block"] == "Andheri"


def test_resolve_select_radio_fields(
    db: SessionDep,
) -> None:
    """Test that select/radio option values are resolved to labels."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.SELECT,
                "label": "Gender",
                "name": "gender",
                "options": [
                    {"id": 1, "label": "Male", "value": "male"},
                    {"id": 2, "label": "Female", "value": "female"},
                ],
            },
            {
                "field_type": FormFieldType.RADIO,
                "label": "Experience",
                "name": "experience",
                "options": [
                    {"id": 1, "label": "0-2 Years", "value": "junior"},
                    {"id": 2, "label": "3-5 Years", "value": "mid"},
                ],
            },
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={"gender": "male", "experience": "mid"},
        session=db,
    )

    assert resolved["gender"] == "Male"
    assert resolved["experience"] == "3-5 Years"


def test_resolve_multi_select_field(
    db: SessionDep,
) -> None:
    """Test that multi-select values are resolved to comma-joined labels."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.MULTI_SELECT,
                "label": "Subjects",
                "name": "subjects",
                "options": [
                    {"id": 1, "label": "Mathematics", "value": "math"},
                    {"id": 2, "label": "Science", "value": "science"},
                    {"id": 3, "label": "English", "value": "english"},
                ],
            },
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={"subjects": ["math", "english"]},
        session=db,
    )

    assert resolved["subjects"] == "Mathematics, English"


def test_resolve_text_fields_unchanged(
    db: SessionDep,
) -> None:
    """Test that text/email/phone fields pass through unchanged."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.FULL_NAME,
                "label": "Full Name",
                "name": "full_name",
            },
            {
                "field_type": FormFieldType.EMAIL,
                "label": "Email",
                "name": "email",
            },
            {
                "field_type": FormFieldType.TEXT,
                "label": "Notes",
                "name": "notes",
            },
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={
            "full_name": "John Doe",
            "email": "john@example.com",
            "notes": "Some notes",
        },
        session=db,
    )

    assert resolved["full_name"] == "John Doe"
    assert resolved["email"] == "john@example.com"
    assert resolved["notes"] == "Some notes"


def test_resolve_missing_entity_graceful(
    db: SessionDep,
) -> None:
    """Test that a missing entity ID resolves to empty string."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.ENTITY,
                "label": "School",
                "name": "school",
            },
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={"school": 99999},
        session=db,
    )

    assert resolved["school"] == "N/A"


def test_resolve_empty_responses(
    db: SessionDep,
) -> None:
    """Test that empty responses return empty dict."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.TEXT,
                "label": "Name",
                "name": "name",
            },
        ],
    )
    assert form.id is not None

    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={},
        session=db,
    )

    # Missing fields default to empty string so {{name}} doesn't appear on certificate
    assert resolved == {"name": "N/A"}


def test_resolve_unanswered_fields_default_to_empty(
    db: SessionDep,
) -> None:
    """Test that form fields not present in responses default to empty string."""
    user, organization = setup_user_organization(db)
    assert user.id is not None
    assert organization.id is not None

    form, _ = _create_form_with_fields(
        db,
        organization.id,
        user.id,
        [
            {
                "field_type": FormFieldType.FULL_NAME,
                "label": "Full Name",
                "name": "full_name",
            },
            {
                "field_type": FormFieldType.EMAIL,
                "label": "Email",
                "name": "email",
            },
            {
                "field_type": FormFieldType.TEXT,
                "label": "Phone",
                "name": "phone",
            },
        ],
    )
    assert form.id is not None

    # User only filled in full_name, skipped email and phone
    resolved = resolve_form_response_values(
        form_id=form.id,
        responses={"full_name": "John Doe"},
        session=db,
    )

    assert resolved["full_name"] == "John Doe"
    assert resolved["email"] == "N/A"
    assert resolved["phone"] == "N/A"
