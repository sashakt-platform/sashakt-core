"""Add external_user_id to candidate for external-login candidate reuse

Revision ID: a1e4c7b2f9d0
Revises: 8d7a2c9f1b34
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a1e4c7b2f9d0'
down_revision = '8d7a2c9f1b34'
branch_labels = None
depends_on = None


# Reuse a single candidate per (organization, external user). Anonymous QR
# candidates keep external_user_id NULL, so the partial index leaves them alone.
UNIQUE_INDEX_NAME = "uq_candidate_org_external_user_id"


def upgrade():
    op.add_column(
        'candidate',
        sa.Column(
            'external_user_id',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )
    op.create_index(
        UNIQUE_INDEX_NAME,
        'candidate',
        ['organization_id', 'external_user_id'],
        unique=True,
        postgresql_where=sa.text('external_user_id IS NOT NULL'),
    )


def downgrade():
    op.drop_index(UNIQUE_INDEX_NAME, table_name='candidate')
    op.drop_column('candidate', 'external_user_id')
