"""add platform guide and analytics link to settings

Revision ID: 951c45c3eba3
Revises: 44b95b87d350
Create Date: 2026-04-23 06:03:32.407621

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '951c45c3eba3'
down_revision = '44b95b87d350'
branch_labels = None
depends_on = None


# Frozen snapshot — do not reference live model constants.
_FROZEN_PLATFORM_GUIDE_DEFAULT = {"value": {"file_path": None}}
_FROZEN_ANALYTICS_LINK_DEFAULT = {"value": {"url": None}}


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE organization_settings
            SET settings = settings
                || jsonb_build_object('platform_guide', CAST(:guide AS JSONB))
                || jsonb_build_object('analytics_link', CAST(:link AS JSONB))
                || jsonb_build_object('version', 3)
            """
        ).bindparams(
            guide=json.dumps(_FROZEN_PLATFORM_GUIDE_DEFAULT),
            link=json.dumps(_FROZEN_ANALYTICS_LINK_DEFAULT),
        )
    )


def downgrade():
    op.execute(
        """
        UPDATE organization_settings
        SET settings = (settings - 'platform_guide' - 'analytics_link')
            || jsonb_build_object('version', 2)
        """
    )
