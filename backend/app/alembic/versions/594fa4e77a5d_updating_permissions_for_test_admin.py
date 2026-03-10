"""Updating Permissions for Test Admin

Revision ID: 594fa4e77a5d
Revises: 6d50cfd8d0a9
Create Date: 2026-03-10 15:41:47.281728

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlmodel import Session, select

from app.models.permission import Permission
from app.models.role import Role, RolePermission


# revision identifiers, used by Alembic.
revision = '594fa4e77a5d'
down_revision = '6d50cfd8d0a9'
branch_labels = None
depends_on = None

PERMISSIONS_TO_GRANT = ["create_user"]


def upgrade():

    bind = op.get_bind()
    session = Session(bind=bind)

    test_admin_role = session.exec(
        select(Role).where(Role.name == "test_admin")
    ).first()

    if not test_admin_role:
        return

    for perm_name in PERMISSIONS_TO_GRANT:
        permission = session.exec(
            select(Permission).where(Permission.name == perm_name)
        ).first()

        if not permission:
            continue

        existing = session.exec(
            select(RolePermission).where(
                RolePermission.role_id == test_admin_role.id,
                RolePermission.permission_id == permission.id,
            )
        ).first()

        if not existing:
            session.add(RolePermission(role_id=test_admin_role.id, permission_id=permission.id))

    session.commit()


def downgrade():

    bind = op.get_bind()
    session = Session(bind=bind)

    test_admin_role = session.exec(
        select(Role).where(Role.name == "test_admin")
    ).first()

    if not test_admin_role:
        return

    for perm_name in PERMISSIONS_TO_GRANT:
        permission = session.exec(
            select(Permission).where(Permission.name == perm_name)
        ).first()

        if not permission:
            continue

        role_perm = session.exec(
            select(RolePermission).where(
                RolePermission.role_id == test_admin_role.id,
                RolePermission.permission_id == permission.id,
            )
        ).first()

        if role_perm:
            session.delete(role_perm)

    session.commit()
