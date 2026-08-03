"""grant update_permission and update_role to system_admin

Revision ID: 587b1aa5408a
Revises: ab4e987f08f7
Create Date: 2026-07-27 18:57:14.060327

"""
from alembic import op
from app.models.permission import Permission
from app.models.role import Role, RolePermission
from sqlmodel import Session, select


# revision identifiers, used by Alembic.
revision = '587b1aa5408a'
down_revision = 'ab4e987f08f7'
branch_labels = None
depends_on = None



PERMISSION_NAMES = ("update_role","read_permission")


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    permission_ids = session.exec(
        select(Permission.id).where(Permission.name.in_(PERMISSION_NAMES))
    ).all()

    system_admin_role_ids = session.exec(
        select(Role.id).where(Role.name == "system_admin")
    ).all()

    for role_id in system_admin_role_ids:
        for permission_id in permission_ids:
            existing = session.exec(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == permission_id,
                )
            ).first()
            if not existing:
                session.add(
                    RolePermission(role_id=role_id, permission_id=permission_id)
                )

    session.commit()


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    permission_ids = session.exec(
        select(Permission.id).where(Permission.name.in_(PERMISSION_NAMES))
    ).all()

    system_admin_role_ids = session.exec(
        select(Role.id).where(Role.name == "system_admin")
    ).all()

    for role_id in system_admin_role_ids:
        for permission_id in permission_ids:
            role_permission = session.exec(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == permission_id,
                )
            ).first()
            if role_permission:
                session.delete(role_permission)

    session.commit()
