"""Add permission for system admin to delete candidate

Revision ID: 2f69b3b1c488
Revises: fe6a2f1b6886
Create Date: 2026-06-24 13:10:34.296532

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f69b3b1c488'
down_revision = 'fe6a2f1b6886'
branch_labels = None
depends_on = None

PERMISSIONS_TO_GRANT = ["delete_candidate"]


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
                WHERE role_id = (SELECT id FROM role WHERE name = 'system_admin')
                  AND permission_id = (SELECT id FROM permission WHERE name = :name)
            """).bindparams(name=perm_name)
        )
