"""Remove update_my_organization_settings permission, superseded by update_my_organization

Revision ID: e41ab027cdb5
Revises: ae2a197c680a
Create Date: 2026-08-03 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e41ab027cdb5'
down_revision = 'ae2a197c680a'
branch_labels = None
depends_on = None


PERMISSION_NAME = "update_my_organization_settings"
PERMISSION_DESCRIPTION = "Update Settings for Own Organization"
GRANTED_ROLES = ["super_admin", "system_admin"]


def upgrade():
    op.execute(
        sa.text("""
            DELETE FROM role_permission
            WHERE permission_id = (SELECT id FROM permission WHERE name = :name)
        """).bindparams(name=PERMISSION_NAME)
    )
    op.execute(
        sa.text("DELETE FROM permission WHERE name = :name").bindparams(
            name=PERMISSION_NAME
        )
    )


def downgrade():
    op.execute(
        sa.text("""
            INSERT INTO permission (name, description, is_active)
            SELECT :name, :description, true
            WHERE NOT EXISTS (
                SELECT 1 FROM permission WHERE name = :name
            )
        """).bindparams(name=PERMISSION_NAME, description=PERMISSION_DESCRIPTION)
    )
    for role_name in GRANTED_ROLES:
        op.execute(
            sa.text("""
                INSERT INTO role_permission (role_id, permission_id)
                SELECT r.id, p.id
                FROM role r
                CROSS JOIN permission p
                WHERE r.name = :role_name
                  AND p.name = :perm_name
                  AND NOT EXISTS (
                      SELECT 1 FROM role_permission rp
                      WHERE rp.role_id = r.id AND rp.permission_id = p.id
                  )
            """).bindparams(role_name=role_name, perm_name=PERMISSION_NAME)
        )
