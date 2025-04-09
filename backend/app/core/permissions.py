import json

from sqlmodel import Session, select

from app.models import Permission, PermissionCreate

with open("app/core/permission_data.json") as file:
    permission_data = json.load(file)

permission_create_list = [
    PermissionCreate(**permission) for permission in permission_data
]


def init_permissions(session: Session) -> None:
    """
    Function to initialize permissions in the database.
    It creates permissions based on the data provided in permission_data.json file.
    """

    for permission in permission_create_list:
        current_permission = session.exec(
            select(Permission).where(Permission.name == permission.name)
        ).first()

        if not current_permission:
            current_permission = Permission(**permission.model_dump())
            session.add(current_permission)
            session.commit()
            session.refresh(current_permission)
