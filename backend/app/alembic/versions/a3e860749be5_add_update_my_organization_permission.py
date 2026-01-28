"""Add update_my_organization permission to roles

Revision ID: a3e860749be5
Revises: bc4b80a867c5
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3e860749be5'
down_revision = 'bc4b80a867c5'
branch_labels = None
depends_on = None


def upgrade():
    # First, create the permission if it doesn't exist
    op.execute("""
        INSERT INTO permission (name, description, is_active)
        SELECT 'update_my_organization', 'Update Own Organization', true
        WHERE NOT EXISTS (
            SELECT 1 FROM permission WHERE name = 'update_my_organization'
        )
    """)

    # Add permission to super_admin and system_admin roles (if not already assigned)
    op.execute("""
        INSERT INTO role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM role r
        CROSS JOIN permission p
        WHERE r.name IN ('super_admin', 'system_admin')
        AND p.name = 'update_my_organization'
        AND NOT EXISTS (
            SELECT 1 FROM role_permission rp
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
        )
    """)


def downgrade():
    # Remove the role-permission mappings
    op.execute("""
        DELETE FROM role_permission
        WHERE permission_id = (
            SELECT id FROM permission WHERE name = 'update_my_organization'
        )
    """)

    # Remove the permission
    op.execute("""
        DELETE FROM permission WHERE name = 'update_my_organization'
    """)
