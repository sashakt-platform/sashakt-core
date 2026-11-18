"""add external_attributes to candidate

Revision ID: c3b8f1d57e92
Revises: a1c4e7d92b36
Create Date: 2026-11-16 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c3b8f1d57e92'
down_revision = 'a1c4e7d92b36'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'candidate',
        sa.Column('external_attributes', sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column('candidate', 'external_attributes')
