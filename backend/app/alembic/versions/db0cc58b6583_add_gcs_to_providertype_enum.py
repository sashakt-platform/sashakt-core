"""add GCS to providertype enum

Revision ID: db0cc58b6583
Revises: 7d90fad13571
Create Date: 2026-03-15 03:58:38.514674

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'db0cc58b6583'
down_revision = '7d90fad13571'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE providertype ADD VALUE IF NOT EXISTS 'GCS'")


def downgrade():
    pass
