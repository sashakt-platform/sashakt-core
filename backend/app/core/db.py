from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import Role, User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Checking if super-admin roles are created
    super_admin = session.exec(select(Role).where(Role.name == "super_admin")).first()
    if not super_admin:
        # Handle the case where no role with label 'super-admin' exists
        super_admin = Role(
            label="Super Admin",
            name="super_admin",
            description="A super-admin has overall access to the system",
        )
        session.add(super_admin)
        session.commit()
        session.refresh(super_admin)
        super_admin_role_id = super_admin.id
    else:
        super_admin_role_id = super_admin.id

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            full_name=settings.FIRST_SUPERUSER_FULLNAME,
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            role_id=super_admin_role_id,
            phone=settings.FIRST_SUPERUSER_MOBILE,
            created_by_id=None,
        )
        user = crud.create_user(session=session, user_create=user_in)
