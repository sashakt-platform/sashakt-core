from httpx import Response
from sqlmodel import Session

from app.models import Organization, OrganizationCreate
from app.tests.utils.utils import random_lower_string


def create_random_organization(session: Session) -> Organization:
    name = random_lower_string()
    description = random_lower_string()
    organization_in = OrganizationCreate(name=name, description=description)

    organization = Organization.model_validate(organization_in)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


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

    assert data["page"] == expected_page
    assert data["size"] == expected_size
    if min_expected_pages is not None:
        assert data["pages"] >= min_expected_pages
    elif expected_pages is not None:
        assert data["pages"] == expected_pages
    if min_expected_total is not None:
        assert data["total"] >= min_expected_total
    elif expected_total is not None:
        assert data["total"] == expected_total
