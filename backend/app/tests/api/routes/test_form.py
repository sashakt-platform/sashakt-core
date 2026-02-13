from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.form import FormResponse
from app.models.test import Test
from app.tests.api.routes.test_tag import setup_user_organization
from app.tests.utils.user import get_current_user_data
from app.tests.utils.utils import random_lower_string

# ============== Form CRUD Tests ==============


def test_create_form(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user_id = user_data["id"]
    user, organization = setup_user_organization(db)

    data = {
        "name": random_lower_string(),
        "description": "Test form description",
    }

    response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]
    assert response_data["is_active"] is True
    assert response_data["created_by_id"] == user_id
    assert "id" in response_data
    assert "created_date" in response_data
    assert "modified_date" in response_data
    assert response_data["fields"] == []


def test_create_form_duplicate_name(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)
    form_name = random_lower_string()

    # Create first form
    data = {"name": form_name}
    response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    # Try to create duplicate
    response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_forms(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    data = {"name": random_lower_string()}
    client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )

    response = client.get(
        f"{settings.API_V1_STR}/form/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert "items" in response_data
    assert "total" in response_data


def test_get_form_by_id(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    data = {"name": random_lower_string(), "description": "Test description"}
    create_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )
    form_id = create_response.json()["id"]

    response = client.get(
        f"{settings.API_V1_STR}/form/{form_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == form_id
    assert response_data["name"] == data["name"]
    assert response_data["description"] == data["description"]


def test_get_form_not_found(
    client: TestClient, get_user_superadmin_token: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/form/99999",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404


def test_update_form(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    data = {"name": random_lower_string()}
    create_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )
    form_id = create_response.json()["id"]

    # Update the form
    update_data = {
        "name": random_lower_string(),
        "description": "Updated description",
        "is_active": False,
    }
    response = client.put(
        f"{settings.API_V1_STR}/form/{form_id}",
        json=update_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == update_data["name"]
    assert response_data["description"] == update_data["description"]
    assert response_data["is_active"] is False


def test_delete_form(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    data = {"name": random_lower_string()}
    create_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=data,
        headers=get_user_superadmin_token,
    )
    form_id = create_response.json()["id"]

    # Delete the form
    response = client.delete(
        f"{settings.API_V1_STR}/form/{form_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Form deleted successfully"

    # Verify form is deleted
    get_response = client.get(
        f"{settings.API_V1_STR}/form/{form_id}",
        headers=get_user_superadmin_token,
    )
    assert get_response.status_code == 404


# ============== Form Field Tests ==============


def test_add_field_to_form(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add a text field
    field_data = {
        "field_type": "text",
        "label": "Full Name",
        "name": "full_name",
        "placeholder": "Enter your name",
        "is_required": True,
    }
    response = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json=field_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["field_type"] == field_data["field_type"]
    assert response_data["label"] == field_data["label"]
    assert response_data["name"] == field_data["name"]
    assert response_data["is_required"] is True
    assert response_data["form_id"] == form_id


def test_add_select_field_with_options(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add a select field with options
    field_data = {
        "field_type": "select",
        "label": "Gender",
        "name": "gender",
        "is_required": True,
        "options": [
            {"id": 1, "label": "Male", "value": "male"},
            {"id": 2, "label": "Female", "value": "female"},
            {"id": 3, "label": "Other", "value": "other"},
        ],
    }
    response = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json=field_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["field_type"] == "select"
    assert len(response_data["options"]) == 3


def test_add_duplicate_field_name(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add first field
    field_data = {
        "field_type": "text",
        "label": "Name",
        "name": "user_name",
    }
    response = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json=field_data,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    # Try to add duplicate field name
    duplicate_field = {
        "field_type": "text",
        "label": "Another Name",
        "name": "user_name",  # Same name
    }
    response = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json=duplicate_field,
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_form_fields(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create a form and add fields
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add two fields
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "Field 1", "name": "field1"},
        headers=get_user_superadmin_token,
    )
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "email", "label": "Field 2", "name": "field2"},
        headers=get_user_superadmin_token,
    )

    # Get fields
    response = client.get(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    fields = response.json()
    assert len(fields) == 2


def test_update_form_field(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create form and add field
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    field_response = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "Original", "name": "original_field"},
        headers=get_user_superadmin_token,
    )
    field_id = field_response.json()["id"]

    # Update field
    update_data = {
        "label": "Updated Label",
        "is_required": True,
        "placeholder": "New placeholder",
    }
    response = client.put(
        f"{settings.API_V1_STR}/form/{form_id}/field/{field_id}",
        json=update_data,
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["label"] == "Updated Label"
    assert response_data["is_required"] is True
    assert response_data["placeholder"] == "New placeholder"


def test_delete_form_field(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create form and add field
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    field_response = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "To Delete", "name": "delete_field"},
        headers=get_user_superadmin_token,
    )
    field_id = field_response.json()["id"]

    # Delete field
    response = client.delete(
        f"{settings.API_V1_STR}/form/{form_id}/field/{field_id}",
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Field deleted successfully"


def test_reorder_form_fields(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user, organization = setup_user_organization(db)

    # Create form and add multiple fields
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add three fields
    field1_resp = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "Field 1", "name": "f1"},
        headers=get_user_superadmin_token,
    )
    field2_resp = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "Field 2", "name": "f2"},
        headers=get_user_superadmin_token,
    )
    field3_resp = client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "text", "label": "Field 3", "name": "f3"},
        headers=get_user_superadmin_token,
    )

    field1_id = field1_resp.json()["id"]
    field2_id = field2_resp.json()["id"]
    field3_id = field3_resp.json()["id"]

    # Reorder: 3, 1, 2
    response = client.put(
        f"{settings.API_V1_STR}/form/{form_id}/field/reorder",
        json={"field_ids": [field3_id, field1_id, field2_id]},
        headers=get_user_superadmin_token,
    )

    assert response.status_code == 200
    fields = response.json()
    assert fields[0]["id"] == field3_id
    assert fields[0]["order"] == 0
    assert fields[1]["id"] == field1_id
    assert fields[1]["order"] == 1
    assert fields[2]["id"] == field2_id
    assert fields[2]["order"] == 2


# ============== Form with Test Integration Tests ==============


def test_public_test_includes_form(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user, organization = setup_user_organization(db)

    # Create a form with fields
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add a field
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={
            "field_type": "text",
            "label": "Name",
            "name": "name",
            "is_required": True,
        },
        headers=get_user_superadmin_token,
    )

    # Create a test with candidate_profile enabled and form_id
    import uuid

    test_uuid = str(uuid.uuid4())
    test = Test(
        name=random_lower_string(),
        link=test_uuid,
        candidate_profile=True,
        form_id=form_id,
        organization_id=user_data["organization_id"],
        created_by_id=user_data["id"],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Get public test info
    response = client.get(f"{settings.API_V1_STR}/test/public/{test_uuid}")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["candidate_profile"] is True
    assert response_data["form"] is not None
    assert response_data["form"]["id"] == form_id
    assert len(response_data["form"]["fields"]) == 1
    assert response_data["form"]["fields"][0]["name"] == "name"


def test_start_test_with_form_responses(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    user, organization = setup_user_organization(db)

    # Create a form
    form_data = {"name": random_lower_string()}
    form_response = client.post(
        f"{settings.API_V1_STR}/form/",
        json=form_data,
        headers=get_user_superadmin_token,
    )
    form_id = form_response.json()["id"]

    # Add fields
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "full_name", "label": "Name", "name": "full_name"},
        headers=get_user_superadmin_token,
    )
    client.post(
        f"{settings.API_V1_STR}/form/{form_id}/field/",
        json={"field_type": "email", "label": "Email", "name": "email"},
        headers=get_user_superadmin_token,
    )

    # Create a test with form
    import uuid

    test_uuid = str(uuid.uuid4())
    test = Test(
        name=random_lower_string(),
        link=test_uuid,
        candidate_profile=True,
        form_id=form_id,
        organization_id=user_data["organization_id"],
        created_by_id=user_data["id"],
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    # Start test with form responses
    start_request = {
        "test_id": test.id,
        "device_info": "test_device",
        "form_responses": {
            "full_name": "John Doe",
            "email": "john@example.com",
        },
    }
    response = client.post(
        f"{settings.API_V1_STR}/candidate/start_test",
        json=start_request,
    )

    assert response.status_code == 200
    response_data = response.json()
    assert "candidate_uuid" in response_data
    assert "candidate_test_id" in response_data

    # Verify form response was stored
    form_response_record = (
        db.query(FormResponse)
        .filter(FormResponse.candidate_test_id == response_data["candidate_test_id"])
        .first()
    )

    assert form_response_record is not None
    assert form_response_record.form_id == form_id
    assert form_response_record.responses["full_name"] == "John Doe"
    assert form_response_record.responses["email"] == "john@example.com"


# ============== Permission Tests ==============


def test_form_requires_permission(
    client: TestClient, get_user_candidate_token: dict[str, str]
) -> None:
    # Candidate role should not have form permissions
    response = client.get(
        f"{settings.API_V1_STR}/form/",
        headers=get_user_candidate_token,
    )
    assert response.status_code == 401  # User Not Permitted


def test_form_accessible_by_test_admin(
    client: TestClient, get_user_testadmin_token: dict[str, str]
) -> None:
    # Test admin should have form permissions
    response = client.get(
        f"{settings.API_V1_STR}/form/",
        headers=get_user_testadmin_token,
    )
    assert response.status_code == 200
