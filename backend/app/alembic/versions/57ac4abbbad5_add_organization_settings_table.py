"""add organization_settings table

Revision ID: 57ac4abbbad5
Revises: 4f2c8a6d9b11
Create Date: 2026-04-17 19:04:28.862966

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.models.organization_settings import DEFAULT_ORGANIZATION_SETTINGS

# revision identifiers, used by Alembic.
revision = '57ac4abbbad5'
down_revision = '4f2c8a6d9b11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'organization_settings',
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('modified_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_organization_settings_organization_id'),
        'organization_settings',
        ['organization_id'],
        unique=True,
    )

    # Backfill: one settings row per existing organization with defaults.
    defaults_json = json.dumps(DEFAULT_ORGANIZATION_SETTINGS)
    op.execute(
        sa.text(
            """
            INSERT INTO organization_settings (organization_id, settings, created_date, modified_date)
            SELECT o.id, CAST(:defaults AS JSONB), NOW(), NOW()
            FROM organization o
            WHERE NOT EXISTS (
                SELECT 1 FROM organization_settings os WHERE os.organization_id = o.id
            )
            """
        ).bindparams(defaults=defaults_json)
    )

    # Add the new permission and grant to super_admin + system_admin.
    op.execute(
        """
        INSERT INTO permission (name, description, is_active)
        SELECT 'update_organization_settings', 'Update Organization Settings', true
        WHERE NOT EXISTS (
            SELECT 1 FROM permission WHERE name = 'update_organization_settings'
        )
        """
    )
    op.execute(
        """
        INSERT INTO role_permission (role_id, permission_id)
        SELECT r.id, p.id
        FROM role r
        CROSS JOIN permission p
        WHERE r.name IN ('super_admin', 'system_admin')
        AND p.name = 'update_organization_settings'
        AND NOT EXISTS (
            SELECT 1 FROM role_permission rp
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
        )
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM role_permission
        WHERE permission_id = (
            SELECT id FROM permission WHERE name = 'update_organization_settings'
        )
        """
    )
    op.execute(
        "DELETE FROM permission WHERE name = 'update_organization_settings'"
    )
    op.drop_index(
        op.f('ix_organization_settings_organization_id'),
        table_name='organization_settings',
    )
    op.drop_table('organization_settings')
