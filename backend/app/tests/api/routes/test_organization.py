from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models.location import Country, State
from app.models.organization import Organization
from app.models.question import Question, QuestionLocation, QuestionRevision
from app.models.role import Role
from app.models.test import Test, TestState
from app.models.user import UserState
from app.tests.utils.organization import (
    create_random_organization,
)
from app.tests.utils.user import (
    authentication_token_from_email,
    create_random_user,
    get_current_user_data,
)
from app.tests.utils.utils import (
    assert_paginated_response,
    random_email,
    random_lower_string,
)


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


def test_aggregated_data_for_state_admin(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_y = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_x, state_y])
    db.commit()
    db.refresh(state_x)
    db.refresh(state_y)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state_x.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    user_state_x = create_random_user(db, new_organization.id)
    db.add(user_state_x)
    db.commit()
    db.refresh(user_state_x)
    db.add(UserState(user_id=user_state_x.id, state_id=state_x.id))

    user_state_y = create_random_user(db, new_organization.id)
    db.add(user_state_y)
    db.commit()
    db.refresh(user_state_y)
    db.add(UserState(user_id=user_state_y.id, state_id=state_y.id))

    db.commit()

    questions = []
    for _ in range(4):
        q = Question(
            created_by_id=user_state_x.id,
            organization_id=new_organization.id,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        db.add(QuestionLocation(question_id=q.id, state_id=state_x.id))
        questions.append(q)

    for _ in range(2):
        q = Question(
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        db.add(QuestionLocation(question_id=q.id, state_id=state_y.id))
        questions.append(q)

    db.commit()

    tests = []
    for i in range(3):
        t = Test(
            name=f"Test X {i + 1}",
            created_by_id=user_state_x.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_x.id))
        tests.append(t)

    for i in range(2):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_y.id))
        tests.append(t)

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/aggregated_data",
        headers=token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 4
    assert data["total_tests"] == 3
    assert data["total_users"] == 2


def test_aggregated_data_for_state_admin_distinct_check(
    client: TestClient,
    get_user_superadmin_token: dict[str, str],
    db: SessionDep,
) -> None:
    new_organization = create_random_organization(db)
    db.add(new_organization)
    db.commit()

    country = Country(name=random_lower_string(), is_active=True)
    db.add(country)
    db.commit()
    db.refresh(country)

    state_x = State(name=random_lower_string(), is_active=True, country_id=country.id)
    state_y = State(name=random_lower_string(), is_active=True, country_id=country.id)
    db.add_all([state_x, state_y])
    db.commit()
    db.refresh(state_x)
    db.refresh(state_y)

    state_admin_role = db.exec(select(Role).where(Role.name == "state_admin")).first()
    assert state_admin_role is not None

    email = random_email()
    state_admin_payload = {
        "email": email,
        "password": random_lower_string(),
        "phone": random_lower_string(),
        "full_name": random_lower_string(),
        "role_id": state_admin_role.id,
        "organization_id": new_organization.id,
        "state_ids": [state_x.id],
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=state_admin_payload,
        headers=get_user_superadmin_token,
    )
    token_headers = authentication_token_from_email(client=client, email=email, db=db)

    user_state_x = create_random_user(db, new_organization.id)
    db.add(user_state_x)
    db.commit()
    db.refresh(user_state_x)
    db.add(UserState(user_id=user_state_x.id, state_id=state_x.id))

    user_state_y = create_random_user(db, new_organization.id)
    db.add(user_state_y)
    db.commit()
    db.refresh(user_state_y)
    db.add(UserState(user_id=user_state_y.id, state_id=state_y.id))

    another_user = create_random_user(db, new_organization.id)
    db.add(another_user)
    db.commit()
    db.refresh(another_user)

    db.commit()

    questions = []
    for _ in range(4):
        q = Question(
            created_by_id=user_state_x.id,
            organization_id=new_organization.id,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        db.add(QuestionLocation(question_id=q.id, state_id=state_x.id))
        questions.append(q)

    for _ in range(2):
        q = Question(
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        db.add(QuestionLocation(question_id=q.id, state_id=state_y.id))
        db.add(QuestionLocation(question_id=q.id, state_id=state_x.id))
        questions.append(q)

    db.commit()

    for _ in range(2):
        q = Question(
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        db.add(QuestionLocation(question_id=q.id, state_id=state_y.id))
        questions.append(q)

    db.commit()

    for _ in range(2):
        q = Question(
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
        )
        db.add(q)
        db.flush()
        db.refresh(q)
        questions.append(q)

    db.commit()

    tests = []
    for i in range(3):
        t = Test(
            name=f"Test X {i + 1}",
            created_by_id=user_state_x.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_x.id))
        tests.append(t)

    for i in range(2):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_y.id))
        db.add(TestState(test_id=t.id, state_id=state_x.id))
        tests.append(t)

    for i in range(3):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        db.add(TestState(test_id=t.id, state_id=state_y.id))
        tests.append(t)

    db.commit()

    for i in range(2):
        t = Test(
            name=f"Test Y {i + 1}",
            created_by_id=user_state_y.id,
            organization_id=new_organization.id,
            is_template=False,
        )
        db.add(t)
        db.flush()
        db.refresh(t)
        tests.append(t)

    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/organization/aggregated_data",
        headers=token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] == 8
    assert data["total_tests"] == 7
    assert data["total_users"] == 2


def test_get_current_organization(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    org = Organization(
        name=random_lower_string(),
        description=random_lower_string(),
        is_active=True,
        is_deleted=False,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    email_with_org = random_email()
    role = db.exec(select(Role).where(Role.name == "candidate")).first()
    assert role is not None

    user_payload = {
        "email": email_with_org,
        "password": random_lower_string(),
        "full_name": random_lower_string(),
        "phone": random_lower_string(),
        "role_id": role.id,
        "organization_id": org.id,
    }
    client.post(
        f"{settings.API_V1_STR}/users/",
        json=user_payload,
        headers=get_user_superadmin_token,
    )
    headers_with_org = authentication_token_from_email(
        client=client, email=email_with_org, db=db
    )

    response = client.get(
        f"{settings.API_V1_STR}/organization/current", headers=headers_with_org
    )
    data = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert data["id"] == org.id
    assert data["name"] == org.name
    assert data["description"] == org.description


def test_update_current_organization(
    client: TestClient, db: SessionDep, get_user_superadmin_token: dict[str, str]
) -> None:
    org = Organization(
        name=random_lower_string(),
        description=random_lower_string(),
        is_active=True,
        is_deleted=False,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    role = db.exec(select(Role).where(Role.name == "super_admin")).first()
    assert role is not None

    email = random_email()
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={
            "email": email,
            "password": random_lower_string(),
            "full_name": random_lower_string(),
            "phone": random_lower_string(),
            "role_id": role.id,
            "organization_id": org.id,
        },
        headers=get_user_superadmin_token,
    )

    headers = authentication_token_from_email(client=client, email=email, db=db)

    new_name = random_lower_string()
    new_description = random_lower_string()

    response = client.patch(
        f"{settings.API_V1_STR}/organization/current",
        json={
            "name": new_name,
            "description": new_description,
        },
        headers=headers,
    )
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["id"] == org.id
    assert data["name"] == new_name
    assert data["description"] == new_description


def test_get_public_organization_by_shortcode_success(
    client: TestClient, db: SessionDep
) -> None:
    org = Organization(
        name=random_lower_string(),
        logo=random_lower_string(),
        shortcode=random_lower_string(),
        is_active=True,
        is_deleted=False,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    response = client.get(f"{settings.API_V1_STR}/organization/public/{org.shortcode}")

    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert data["name"] == org.name
    assert data["logo"] == org.logo
    assert data["shortcode"] == org.shortcode


def test_get_public_organization_by_shortcode_inactive(
    client: TestClient, db: SessionDep
) -> None:
    org = Organization(
        name=random_lower_string(),
        logo=random_lower_string(),
        shortcode=random_lower_string(),
        is_active=False,
        is_deleted=False,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    response = client.get(f"{settings.API_V1_STR}/organization/public/{org.shortcode}")

    data = response.json()

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert data["detail"] == "Organization not found"
