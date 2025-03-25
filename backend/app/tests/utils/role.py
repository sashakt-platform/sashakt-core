from sqlmodel import Session

from app import crud
from app.models import Role, RoleCreate
from app.tests.utils.utils import random_lower_string


def create_random_role(db: Session) -> Role:
    name = random_lower_string()
    description = random_lower_string()
    role_in = RoleCreate(name=name, description=description)
    return crud.create_role(session=db, role_in=role_in)
