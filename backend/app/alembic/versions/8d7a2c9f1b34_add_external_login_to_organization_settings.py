"""add external_login to organization settings

Revision ID: 8d7a2c9f1b34
Revises: b3e9f2a1c047
Create Date: 2026-05-28 00:00:00.000000

"""

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d7a2c9f1b34"
down_revision: str = "b3e9f2a1c047"
branch_labels = None
depends_on = None

# Frozen default — do not reference live model constants.
_FROZEN_EXTERNAL_LOGIN_DEFAULT = {
    "mode": "fixed",
    "value": {
        "enabled": False,
        "provider": None,
        "block_anonymous_starts": False,
    },
}


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE organization_settings
            SET settings = settings
                || jsonb_build_object('external_login', CAST(:external_login AS JSONB))
                || jsonb_build_object('version', 5)
            """
        ).bindparams(external_login=json.dumps(_FROZEN_EXTERNAL_LOGIN_DEFAULT))
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE organization_settings
        SET settings = (settings - 'external_login')
            || jsonb_build_object('version', 4)
        """
    )
