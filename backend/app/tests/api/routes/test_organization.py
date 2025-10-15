from fastapi import status
from fastapi.testclient import TestClient

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.organization import Organization
from app.models.question import Question, QuestionRevision
from app.models.test import Test
from app.tests.utils.organization import (
    create_random_organization,
)
from app.tests.utils.user import create_random_user, get_current_user_data
from app.tests.utils.utils import assert_paginated_response, random_lower_string


def test_create_organization(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    get_user_candidate_token: dict[str, str],
) -> None:
    name = random_lower_string()
    description = random_lower_string()
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={
            "name": name,
            "description": description,
        },
        headers=get_user_superadmin_token,
    )

    data = response.json()
    assert response.status_code == 200
    assert data["name"] == name
    assert data["description"] == description
    assert "id" in data
    assert data["is_active"] is True
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={
            "name": name,
            "description": description,
        },
        headers=get_user_candidate_token,
    )
    data = response.json()
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert data["detail"] == "User Not Permitted"


def test_read_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
    get_user_candidate_token: dict[str, str],
) -> None:
    for _ in range(12):
        create_random_organization(db)

    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    assert_paginated_response(
        response,
        expected_page=1,
        expected_size=25,
        min_expected_total=12,
        min_expected_pages=1,
    )

    response = client.get(
        f"{settings.API_V1_STR}/organization/?page=2",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200

    jal_vikas = Organization(name=random_lower_string())
    maha_vikas = Organization(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add(jal_vikas)
    db.add(maha_vikas)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    assert_paginated_response(
        response,
        expected_page=1,
        expected_size=25,
        min_expected_total=14,
        min_expected_pages=1,
    )
    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_candidate_token,
    )
    assert response.status_code == 200
    assert_paginated_response(
        response,
        expected_page=1,
        expected_size=25,
        min_expected_total=0,
        min_expected_pages=1,
    )


def test_read_organization_filter_by_name(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    organization_name = random_lower_string()
    organization_name_2 = random_lower_string()

    organization = Organization(name=organization_name + random_lower_string())
    organization_2 = Organization(
        name=organization_name,
        description=random_lower_string(),
    )
    organization_3 = Organization(
        name=organization_name_2,
        description=random_lower_string(),
    )
    db.add_all([organization, organization_2, organization_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/?name={organization_name}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 2
    assert_paginated_response(
        response,
        expected_page=1,
        expected_size=25,
        min_expected_total=2,
        min_expected_pages=1,
    )

    response = client.get(
        f"{settings.API_V1_STR}/organization/?name={organization_name_2}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 1

    response = client.get(
        f"{settings.API_V1_STR}/organization/?name={random_lower_string()}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 0


def test_read_organization_filter_by_description(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    organization_description = random_lower_string()
    organization_description_2 = random_lower_string()

    organization = Organization(
        name=random_lower_string(),
        description=organization_description + random_lower_string(),
    )
    organization_2 = Organization(
        name=random_lower_string(),
        description=organization_description,
    )
    organization_3 = Organization(
        name=random_lower_string(),
        description=organization_description_2,
    )
    db.add_all([organization, organization_2, organization_3])
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/?description={organization_description}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert_paginated_response(
        response,
        expected_page=1,
        expected_size=25,
        min_expected_total=2,
        min_expected_pages=1,
    )

    response = client.get(
        f"{settings.API_V1_STR}/organization/?description={organization_description_2}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 1

    response = client.get(
        f"{settings.API_V1_STR}/organization/?description={random_lower_string()}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    items = data["items"]
    assert len(items) == 0


def test_read_organization_order_by(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    create_random_organization(db)
    create_random_organization(db)
    create_random_organization(db)
    create_random_organization(db)

    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]

    organization_created_date = [item["created_date"] for item in items]

    sorted_organization_created_date = sorted(organization_created_date)

    assert sorted_organization_created_date == organization_created_date

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-created_date",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    organization_created_date = [item["created_date"] for item in items]

    sorted_organization_created_date = sorted(organization_created_date, reverse=True)

    assert sorted_organization_created_date == organization_created_date

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=name",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    organization_name = [item["name"] for item in items]

    sorted_organization_name = sorted(organization_name, key=str.lower)

    assert sorted_organization_name == organization_name

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-name",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    organization_name = [item["name"] for item in items]

    sorted_organization_name = sorted(organization_name, key=str.lower, reverse=True)

    assert sorted_organization_name == organization_name

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-name&order_by=created_date",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    organization_name_date = [
        {"name": item["name"], "created_date": item["created_date"]} for item in items
    ]

    sort_by_date = sorted(organization_name_date, key=lambda x: x["created_date"])
    sorted_array = sorted(sort_by_date, key=lambda x: x["name"].lower(), reverse=True)

    assert sorted_array == organization_name_date

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-test",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid" in data["detail"].lower()

    response = client.get(
        f"{settings.API_V1_STR}/organization/?order_by=-",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid" in data["detail"].lower()


def test_read_organization_by_id(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    jal_vikas = Organization(name=random_lower_string())
    maha_vikas = Organization(
        name=random_lower_string(), description=random_lower_string()
    )
    db.add(jal_vikas)
    db.add(maha_vikas)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] is None

    response = client.get(
        f"{settings.API_V1_STR}/organization/{maha_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == maha_vikas.name
    assert data["id"] == maha_vikas.id
    assert data["description"] == maha_vikas.description
    assert data["is_active"] is True


def test_update_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    initial_name = random_lower_string()
    updated_name = random_lower_string()
    inital_description = random_lower_string()
    updated_description = random_lower_string()
    jal_vikas = Organization(name=initial_name)
    db.add(jal_vikas)
    db.commit()
    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": updated_name, "description": None},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == updated_name
    assert data["id"] == jal_vikas.id
    assert data["name"] != initial_name
    assert data["description"] is None

    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": jal_vikas.name, "description": inital_description},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] == inital_description

    response = client.put(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        json={"name": jal_vikas.name, "description": updated_description},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["id"] == jal_vikas.id
    assert data["description"] == updated_description


def test_visibility_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    jal_vikas = Organization(name=random_lower_string())
    db.add(jal_vikas)
    db.commit()
    response = client.patch(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        params={"is_active": True},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == jal_vikas.name
    assert data["is_active"] is True
    assert data["is_active"] is not False and not None

    response = client.patch(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        params={"is_active": False},
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == jal_vikas.id
    assert data["is_active"] is False
    assert data["is_active"] is not True and not None


def test_delete_organization(
    client: TestClient,
    db: SessionDep,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/organization/0",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}
    jal_vikas = Organization(name=random_lower_string())
    db.add(jal_vikas)
    db.commit()
    assert jal_vikas.is_deleted is False
    response = client.delete(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200

    assert "delete" in data["message"]

    response = client.get(
        f"{settings.API_V1_STR}/organization/{jal_vikas.id}",
        headers=get_user_superadmin_token,
    )
    data = response.json()

    assert response.status_code == 404
    assert "id" not in data


def test_inactive_organization_not_listed(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/organization/",
        json={
            "name": "inactive org",
            "description": "organization is not active",
            "is_active": False,
        },
        headers=get_user_superadmin_token,
    )
    data = response.json()
    assert response.status_code == 200
    org_id = data["id"]
    assert data["is_active"] is False

    response = client.get(
        f"{settings.API_V1_STR}/organization/",
        headers=get_user_superadmin_token,
    )
    data = response.json()
    items = data["items"]
    assert all(item["id"] != org_id for item in items)


def test_get_aggregated_data_for_organization(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    user_data = get_current_user_data(client, get_user_superadmin_token)
    org_id = user_data["organization_id"]
    user_id = user_data["id"]
    user_a = create_random_user(db, org_id)
    user_b = create_random_user(db, org_id)
    db.add(user_a)
    db.add(user_b)
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    questions = []
    for i in range(5):
        q = Question(
            created_by_id=user_id,
            organization_id=org_id,
            is_active=True,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        q_rev = QuestionRevision(
            question_text=f"Sample question {i + 1}?",
            created_by_id=user_id,
            question_id=q.id,
            question_type="single_choice",
            options=[{"id": 1, "key": "A", "value": "Option A"}],
            correct_answer=[1],
        )
        db.add(q_rev)
        db.flush()
        db.refresh(q_rev)

        q.last_revision_id = q_rev.id
        db.add(q)
        questions.append(q)

    db.add(questions[0])
    test = Test(
        name="Sample Test",
        description=random_lower_string(),
        time_limit=30,
        marks=50,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=False,
        random_questions=False,
        organization_id=org_id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    test2 = Test(
        name="Sample Test2",
        description=random_lower_string(),
        time_limit=30,
        marks=60,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=True,
        random_questions=False,
        organization_id=org_id,
    )
    db.add(test2)
    db.commit()
    db.refresh(test2)
    test3 = Test(
        name="template test2",
        description=random_lower_string(),
        time_limit=30,
        marks=60,
        start_instructions=random_lower_string(),
        link=random_lower_string(),
        created_by_id=user_id,
        is_active=True,
        is_deleted=False,
        random_questions=False,
        is_template=True,
        organization_id=org_id,
    )
    db.add(test3)
    db.commit()
    db.refresh(test3)

    response = client.get(
        f"{settings.API_V1_STR}/organization/aggregated_data",
        headers=get_user_superadmin_token,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 5
    assert data["total_users"] == 3
    assert data["total_tests"] == 2
