"""add pre_test_instructions and completion_message to organization settings

Revision ID: fe6a2f1b6886
Revises: c2f7d9a4b8e1
Create Date: 2026-06-10 00:00:00.000000

"""

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fe6a2f1b6886"
down_revision: str = "c2f7d9a4b8e1"
branch_labels = None
depends_on = None

# Frozen defaults — do not reference live model constants.
_FROZEN_PRE_TEST_INSTRUCTIONS_DEFAULT = {"value": {"text": None}}
_FROZEN_COMPLETION_MESSAGE_DEFAULT = {"value": {"text": None}}


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE organization_settings
            SET settings = settings
                || jsonb_build_object('pre_test_instructions', CAST(:pti AS JSONB))
                || jsonb_build_object('completion_message', CAST(:cm AS JSONB))
                || jsonb_build_object('version', 5)
            """
        ).bindparams(
            pti=json.dumps(_FROZEN_PRE_TEST_INSTRUCTIONS_DEFAULT),
            cm=json.dumps(_FROZEN_COMPLETION_MESSAGE_DEFAULT),
        )
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE organization_settings
        SET settings = (settings - 'pre_test_instructions' - 'completion_message')
            || jsonb_build_object('version', 4)
        """
    )
