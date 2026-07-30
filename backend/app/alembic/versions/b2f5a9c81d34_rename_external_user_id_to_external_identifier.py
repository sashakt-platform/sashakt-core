"""Rename candidate.external_user_id to external_identifier

Renames the external-login column (and its partial unique index) from
external_user_id to external_identifier, matching the API/model rename.

Revision ID: b2f5a9c81d34
Revises: 929353af67bf
Create Date: 2026-07-31 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b2f5a9c81d34'
down_revision = '929353af67bf'
branch_labels = None
depends_on = None


OLD_INDEX = "uq_candidate_org_external_user_id"
NEW_INDEX = "uq_candidate_org_external_identifier"


def upgrade():
    op.alter_column(
        'candidate', 'external_user_id', new_column_name='external_identifier'
    )
    op.execute(f'ALTER INDEX {OLD_INDEX} RENAME TO {NEW_INDEX}')


def downgrade():
    op.execute(f'ALTER INDEX {NEW_INDEX} RENAME TO {OLD_INDEX}')
    op.alter_column(
        'candidate', 'external_identifier', new_column_name='external_user_id'
    )
