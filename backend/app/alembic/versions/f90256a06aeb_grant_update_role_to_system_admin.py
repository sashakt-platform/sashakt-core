"""grant update_role to system_admin

Revision ID: f90256a06aeb
Revises: 7f3a9c2e5b81
Create Date: 2026-08-19 12:50:31.434873

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f90256a06aeb'
down_revision = '7f3a9c2e5b81'
branch_labels = None
depends_on = None

PERMISSIONS_TO_GRANT = ["update_role", "read_permission"]


def upgrade():

    for perm_name in PERMISSIONS_TO_GRANT:
        op.execute(
            sa.text("""
                INSERT INTO role_permission (role_id, permission_id)
                SELECT r.id, p.id
                FROM role r
                CROSS JOIN permission p
                WHERE r.name = 'system_admin'
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
                WHERE role_id IN (SELECT id FROM role WHERE name = 'system_admin')
                  AND permission_id = (SELECT id FROM permission WHERE name = :name)
            """).bindparams(name=perm_name)
        )
