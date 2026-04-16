"""add_admin_id_to_candidate_test

Revision ID: 1aa2d346ea8b
Revises: d84165c8e013
Create Date: 2026-04-16 13:07:48.523380

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '1aa2d346ea8b'
down_revision = 'd84165c8e013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('candidate_test', sa.Column('admin_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'candidate_test_admin_id_fkey', 'candidate_test', 'user', ['admin_id'], ['id']
    )


def downgrade():
    op.alter_column('candidate_test', 'admin_id', nullable=True)
    op.drop_constraint('candidate_test_admin_id_fkey', 'candidate_test', type_='foreignkey')
    op.drop_column('candidate_test', 'admin_id')
