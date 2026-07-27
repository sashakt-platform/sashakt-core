from sqlmodel import Session

from app.models import Role, RoleCreate
from app.tests.utils.organization import create_random_organization
from app.tests.utils.utils import random_lower_string


def create_random_role(session: Session, organization_id: int | None = None) -> Role:
    if organization_id is None:
        organization_id = create_random_organization(session=session).id
        assert organization_id is not None

    name = random_lower_string()
    description = random_lower_string()
    label = random_lower_string()
    role_in = RoleCreate(name=name, description=description, label=label)

    db_role = Role(
        **role_in.model_dump(exclude={"permissions"}),
        organization_id=organization_id,
    )
    session.add(db_role)
    session.commit()
    session.refresh(db_role)

    return db_role
