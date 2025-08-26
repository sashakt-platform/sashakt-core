"""add numerical_decimal to questiontype enum

Revision ID: ae31b05eff57
Revises: b0a29fe32d37
Create Date: 2025-08-25 18:28:54.069552

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'ae31b05eff57'
down_revision = 'b0a29fe32d37'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'numerical_decimal'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'matrix_matches'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'matrix_ratings'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'matrix_numbers'")
    op.execute("ALTER TYPE questiontype ADD VALUE IF NOT EXISTS 'matrix_texts'")


def downgrade():
    pass
