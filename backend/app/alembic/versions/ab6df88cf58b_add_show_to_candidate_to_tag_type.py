"""add show_to_candidate to tag_type

Revision ID: ab6df88cf58b
Revises: d8640b20c143
Create Date: 2026-08-13 16:17:33.052894

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab6df88cf58b'
down_revision = 'd8640b20c143'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tag_type', sa.Column('show_to_candidate', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('tag_type', 'show_to_candidate')
