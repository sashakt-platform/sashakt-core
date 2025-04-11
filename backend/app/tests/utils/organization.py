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
