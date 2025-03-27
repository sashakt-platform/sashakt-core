from sqlmodel import Session

from app.models import Role, RoleCreate
from app.tests.utils.utils import random_lower_string


def create_random_role(session: Session) -> Role:
    name = random_lower_string()
    description = random_lower_string()
    role_in = RoleCreate(name=name, description=description)

    db_role = Role.model_validate(role_in)
    session.add(db_role)
    session.commit()
    session.refresh(db_role)

    return db_role
