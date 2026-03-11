"""Updating Permissions for Test Admin

Revision ID: 594fa4e77a5d
Revises: 6d50cfd8d0a9
Create Date: 2026-03-10 15:41:47.281728

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '594fa4e77a5d'
down_revision = '6d50cfd8d0a9'
branch_labels = None
depends_on = None

PERMISSIONS_TO_GRANT = ["create_user", "read_role"]


def upgrade():
    # For existing deployments: grant permissions to test_admin.
    # For new installs: initial_data.py handles this via permission_data.json.
    # Safe no-op if role or permission doesn't exist yet.
    for perm_name in PERMISSIONS_TO_GRANT:
        op.execute(
            sa.text("""
                INSERT INTO role_permission (role_id, permission_id)
                SELECT r.id, p.id
                FROM role r
                CROSS JOIN permission p
                WHERE r.name = 'test_admin'
                  AND p.name = :name
                  AND NOT EXISTS (
                      SELECT 1 FROM role_permission rp
                      WHERE rp.role_id = r.id AND rp.permission_id = p.id
                  )
            """).bindparams(name=perm_name)
        )


def downgrade():
    for perm_name in PERMISSIONS_TO_GRANT:
        op.execute(
            sa.text("""
                DELETE FROM role_permission
                WHERE role_id = (SELECT id FROM role WHERE name = 'test_admin')
                  AND permission_id = (SELECT id FROM permission WHERE name = :name)
            """).bindparams(name=perm_name)
        )
