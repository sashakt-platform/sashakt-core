"""add pause_test to organization settings

Revision ID: b3e9f2a1c047
Revises: aa4fc4afb4ff
Create Date: 2026-05-18 00:00:00.000000

"""

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e9f2a1c047"
down_revision: str = "aa4fc4afb4ff"
branch_labels = None
depends_on = None

# Frozen default — do not reference live model constants.
_FROZEN_PAUSE_TEST_DEFAULT = {
    "mode": "fixed",
    "value": {"default": False},
}


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE organization_settings
            SET settings = settings
                || jsonb_build_object('pause_test', CAST(:pause_test AS JSONB))
                || jsonb_build_object('version', 4)
            """
        ).bindparams(pause_test=json.dumps(_FROZEN_PAUSE_TEST_DEFAULT))
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE organization_settings
        SET settings = (settings - 'pause_test')
            || jsonb_build_object('version', 3)
        """
    )
