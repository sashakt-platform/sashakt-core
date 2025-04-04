from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.core.permissions import (
    attempt_test,
    create_permission,
    create_question,
    create_template,
    create_test,
    create_user,
    delete_question,
    delete_template,
    delete_test,
    delete_user,
    edit_question,
    edit_template,
    edit_test,
    edit_user,
    manage_organization,
    view_dashboard,
)
from app.core.roles import (
    candidate,
    create_role,
    state_admin,
    super_admin,
    system_admin,
    test_admin,
)
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Creating all Permissions
    manage_organization_permission = create_permission(
        session=session, permission_create=manage_organization
    )
    view_dashboard_permission = create_permission(
        session=session, permission_create=view_dashboard
    )
    create_user_permission = create_permission(
        session=session, permission_create=create_user
    )
    edit_user_permission = create_permission(
        session=session, permission_create=edit_user
    )
    delete_user_permission = create_permission(
        session=session, permission_create=delete_user
    )
    create_template_permission = create_permission(
        session=session, permission_create=create_template
    )
    edit_template_permission = create_permission(
        session=session, permission_create=edit_template
    )
    delete_template_permission = create_permission(
        session=session, permission_create=delete_template
    )
    create_test_permission = create_permission(
        session=session, permission_create=create_test
    )
    edit_test_permission = create_permission(
        session=session, permission_create=edit_test
    )
    delete_test_permission = create_permission(
        session=session, permission_create=delete_test
    )
    attempt_test_permission = create_permission(
        session=session, permission_create=attempt_test
    )
    create_question_permission = create_permission(
        session=session, permission_create=create_question
    )
    edit_question_permission = create_permission(
        session=session, permission_create=edit_question
    )
    delete_question_permission = create_permission(
        session=session, permission_create=delete_question
    )

    super_admin_role = create_role(
        session=session,
        role_create=super_admin,
        permissions=[
            manage_organization_permission,
            view_dashboard_permission,
            create_user_permission,
            edit_user_permission,
            delete_user_permission,
            create_template_permission,
            edit_template_permission,
            delete_template_permission,
            create_test_permission,
            edit_test_permission,
            delete_test_permission,
            create_question_permission,
            edit_question_permission,
            delete_question_permission,
        ],
    )

    create_role(
        session=session,
        role_create=system_admin,
        permissions=[
            view_dashboard_permission,
            create_user_permission,
            edit_user_permission,
            delete_user_permission,
            create_template_permission,
            edit_template_permission,
            delete_template_permission,
            create_test_permission,
            edit_test_permission,
            delete_test_permission,
            create_question_permission,
            edit_question_permission,
            delete_question_permission,
        ],
    )

    create_role(
        session=session,
        role_create=state_admin,
        permissions=[
            view_dashboard_permission,
            create_user_permission,
            edit_user_permission,
            delete_user_permission,
            create_test_permission,
            edit_test_permission,
            delete_test_permission,
            create_question_permission,
            edit_question_permission,
            delete_question_permission,
        ],
    )

    create_role(
        session=session,
        role_create=test_admin,
        permissions=[
            create_test_permission,
            edit_test_permission,
            delete_test_permission,
            view_dashboard_permission,
        ],
    )

    create_role(
        session=session,
        role_create=candidate,
        permissions=[
            attempt_test_permission,
        ],
    )

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()

    if not user:
        user_in = UserCreate(
            full_name=settings.FIRST_SUPERUSER_FULLNAME,
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            role_id=super_admin_role.id,
            phone=settings.FIRST_SUPERUSER_MOBILE,
            created_by_id=None,
        )
        user = crud.create_user(session=session, user_create=user_in)
