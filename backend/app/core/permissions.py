from sqlmodel import Session, select

from app.models import Permission, PermissionCreate, PermissionPublic

manage_organization = PermissionCreate(
    name="manage_organization", description="Add/Remove/Edit Organizations"
)

create_user = PermissionCreate(name="create_user", description="Create New Users")
edit_user = PermissionCreate(name="edit_user", description="Edit Existing User")
delete_user = PermissionCreate(name="delete_user", description="Delete Existing User")

create_template = PermissionCreate(
    name="create_template", description="Create New Template"
)
edit_template = PermissionCreate(
    name="edit_template", description="Edit Existing Template"
)
delete_template = PermissionCreate(
    name="delete_template", description="Delete Template"
)

create_question = PermissionCreate(
    name="create_question", description="Create New Question"
)
edit_question = PermissionCreate(
    name="edit_question", description="Edit Existing Question"
)
delete_question = PermissionCreate(
    name="delete_question", description="Delete Question"
)

create_test = PermissionCreate(name="create_test", description="Create New Test")
edit_test = PermissionCreate(name="edit_test", description="Edit Existing Test")
delete_test = PermissionCreate(name="delete_test", description="Delete Test")
attempt_test = PermissionCreate(name="attempt_test", description="Attempt a Test")

view_dashboard = PermissionCreate(name="view_dashboard", description="View Dashboards")


def create_permission(
    session: Session, permission_create: PermissionCreate
) -> PermissionPublic:
    current_permission = session.exec(
        select(Permission).where(Permission.name == permission_create.name)
    ).first()

    if not current_permission:
        current_permission = Permission(**permission_create.model_dump())
        session.add(current_permission)
        session.commit()
        session.refresh(current_permission)
    return current_permission
