from sqlmodel import Session

from app import crud
from app.models import Role, RoleCreate
from app.tests.utils.user import create_random_user
from app.tests.utils.utils import random_lower_string


def create_random_role(db: Session) -> Role:
    user = create_random_user(db)
    created_by_id = user.id
    assert created_by_id is not None
    name = random_lower_string()
    description = random_lower_string()
    role_in = RoleCreate(name=name, description=description)
    return crud.create_role(session=db, role_in=role_in)
