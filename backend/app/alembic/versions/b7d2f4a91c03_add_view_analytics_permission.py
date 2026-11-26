"""Add view_analytics permission to roles

Revision ID: b7d2f4a91c03
Revises: a1c4e7d92b36
Create Date: 2026-11-26

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b7d2f4a91c03'
down_revision = 'a1c4e7d92b36'
branch_labels = None
depends_on = None


def upgrade():
    # Create the permission if it doesn't exist
    op.execute("""
        INSERT INTO permission (name, description, is_active)
        SELECT 'view_analytics', 'View Organization Analytics', true
        WHERE NOT EXISTS (
            SELECT 1 FROM permission WHERE name = 'view_analytics'
        )
    """)

    # Grant to system_admin and state_admin roles (if not already assigned)
    op.execute("""
        INSERT INTO role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM role r
        CROSS JOIN permission p
        WHERE r.name IN ('system_admin', 'state_admin')
        AND p.name = 'view_analytics'
        AND NOT EXISTS (
            SELECT 1 FROM role_permission rp
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
        )
    """)


def downgrade():
    op.execute("""
        DELETE FROM role_permission
        WHERE permission_id = (
            SELECT id FROM permission WHERE name = 'view_analytics'
        )
    """)

    op.execute("""
        DELETE FROM permission WHERE name = 'view_analytics'
    """)
