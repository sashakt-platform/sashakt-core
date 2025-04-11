from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.core.location import init_location
from app.core.permissions import (
    init_permissions,
)
from app.core.roles import (
    init_roles,
    super_admin,
)
from app.models import Organization, Role, User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Creating Initial Location Data
    init_location(session)

    # Creating Initial Permissions
    init_permissions(session)

    # Creating Initial Roles
    init_roles(session)

    initial_organization = Organization(name="T4D", description="T4D Organization")
    session.add(initial_organization)
    session.commit()

    super_admin_role = session.exec(
        select(Role.id).where(Role.name == super_admin.name)
    ).first()

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()

    if not user:
        user_in = UserCreate(
            full_name=settings.FIRST_SUPERUSER_FULLNAME,
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            role_id=super_admin_role,
            phone=settings.FIRST_SUPERUSER_MOBILE,
            created_by_id=None,
            organization_id=initial_organization.id,
        )
        user = crud.create_user(session=session, user_create=user_in)
