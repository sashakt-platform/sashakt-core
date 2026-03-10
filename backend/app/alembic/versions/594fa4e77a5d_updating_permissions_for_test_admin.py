"""Updating Permissions for Test Admin

Revision ID: 594fa4e77a5d
Revises: 6d50cfd8d0a9
Create Date: 2026-03-10 15:41:47.281728

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '594fa4e77a5d'
down_revision = '6d50cfd8d0a9'
branch_labels = None
depends_on = None

PERMISSIONS_TO_GRANT = ["create_user"]


def upgrade():
    bind = op.get_bind()
    for perm_name in PERMISSIONS_TO_GRANT:
        bind.execute(sa.text("""
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r, permission p
            WHERE r.name = :role_name
              AND p.name = :perm_name
              AND NOT EXISTS (
                  SELECT 1 FROM role_permission rp
                  WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
        """), {"role_name": "test_admin", "perm_name": perm_name})


def downgrade():
    bind = op.get_bind()
    for perm_name in PERMISSIONS_TO_GRANT:
        bind.execute(sa.text("""
            DELETE FROM role_permission
            WHERE role_id = (SELECT id FROM role WHERE name = :role_name)
              AND permission_id = (SELECT id FROM permission WHERE name = :perm_name)
        """), {"role_name": "test_admin", "perm_name": perm_name})
