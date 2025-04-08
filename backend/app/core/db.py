from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.core.location import init_location
from app.models import Permission, Role, RolePermission, RolePublic, User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Creating Location Data
    init_location(session)
    # Creating all Permissions

    def create_permission(name: str, description: str | None = None) -> Permission:
        permission = session.exec(
            select(Permission).where(Permission.name == name)
        ).first()

        if not permission:
            permission = Permission(name=name, description=description)
            session.add(permission)
            session.commit()
            session.refresh(permission)
        return permission

    # organization Permission

    manage_organization = create_permission(
        name="manage_organization", description="Add/Remove/Edit Organizations"
    )
    create_user = create_permission(name="create_user", description="Create New Users")
    edit_user = create_permission(name="edit_user", description="Edit Existing User")
    delete_user = create_permission(
        name="delete_user", description="Delete Existing User"
    )
    create_template = create_permission(
        name="create_template", description="Create New Template"
    )
    edit_template = create_permission(
        name="edit_template", description="Edit Existing Template"
    )
    delete_template = create_permission(
        name="delete_template", description="Delete Template"
    )
    create_question = create_permission(
        name="create_question", description="Create New Question"
    )
    edit_question = create_permission(
        name="edit_question", description="Edit Existing Question"
    )
    delete_question = create_permission(
        name="delete_question", description="Delete Question"
    )
    create_test = create_permission(name="create_test", description="Create New Test")
    edit_test = create_permission(name="edit_test", description="Edit Existing Test")
    delete_test = create_permission(name="delete_test", description="Delete Test")
    attempt_test = create_permission(name="attempt_test", description="Attempt a Test")
    view_dashboard = create_permission(
        name="view_dashboard", description="View Dashboards"
    )

    # Creating role

    def create_role(
        name: str,
        label: str,
        permissions: list[Permission],
        description: str | None = None,
    ) -> RolePublic:
        role = session.exec(select(Role).where(Role.name == name)).first()
        if not role:
            role = Role(name=name, description=description, label=label)
            session.add(role)
            session.commit()
            session.refresh(role)
            if len(permissions) > 0:
                for permission in permissions:
                    role_permission = RolePermission(
                        role_id=role.id, permission_id=permission.id
                    )
                    session.add(role_permission)
                    session.commit()
                    session.refresh(role_permission)

            stored_permission_ids = session.exec(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == role.id
                )
            )
        else:
            stored_permission_ids = session.exec(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == role.id
                )
            )

        return RolePublic(
            **role.model_dump(),
            permissions=stored_permission_ids,
        )

    super_admin = create_role(
        name="super_admin",
        label="Super Admin",
        description="A super-admin has overall access to the system",
        permissions=[
            manage_organization,
            create_user,
            edit_user,
            delete_user,
            create_template,
            edit_template,
            delete_template,
            create_question,
            edit_question,
            delete_question,
            create_test,
            edit_test,
            delete_test,
            view_dashboard,
        ],
    )
    create_role(
        name="system_admin",
        label="System Admin",
        description="System-level admin who can handle organization-level tasks",
        permissions=[
            create_user,
            edit_user,
            delete_user,
            create_template,
            edit_template,
            delete_template,
            create_question,
            edit_question,
            delete_question,
            create_test,
            edit_test,
            delete_test,
            view_dashboard,
        ],
    )

    create_role(
        name="state_admin",
        label="State Admin",
        description="State-level admin of a organization",
        permissions=[
            create_user,
            edit_user,
            delete_user,
            create_question,
            edit_question,
            delete_question,
            create_test,
            edit_test,
            delete_test,
            view_dashboard,
        ],
    )

    create_role(
        name="test_admin",
        label="Test Admin",
        description="Test Admin who creates and conducts test",
        permissions=[create_test, edit_test, delete_test, view_dashboard],
    )

    create_role(
        name="candidate",
        label="Candidate",
        description="Candidate who attempts Test",
        permissions=[attempt_test],
    )
    print("super_admin-->", super_admin)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()

    if not user:
        user_in = UserCreate(
            full_name=settings.FIRST_SUPERUSER_FULLNAME,
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            role_id=super_admin.id,
            phone=settings.FIRST_SUPERUSER_MOBILE,
            created_by_id=None,
        )
        user = crud.create_user(session=session, user_create=user_in)
