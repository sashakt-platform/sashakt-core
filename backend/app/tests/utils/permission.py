from sqlmodel import Session

from app.models import Permission, PermissionCreate
from app.tests.utils.utils import random_lower_string


def create_random_permission(session: Session) -> Permission:
    name = random_lower_string()
    description = random_lower_string()
    permission_in = PermissionCreate(name=name, description=description)

    db_permission = Permission.model_validate(permission_in)
    session.add(db_permission)
    session.commit()
    session.refresh(db_permission)
    return db_permission
