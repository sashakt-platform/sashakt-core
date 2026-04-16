"""fix_schema_drift_question_set_indexes_and_candidate_test_nullable

Revision ID: a640a03f877a
Revises: 4f2c8a6d9b11
Create Date: 2026-04-16 12:36:35.544214

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a640a03f877a'
down_revision = '4f2c8a6d9b11'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('candidate_test', 'question_set_ids',
               existing_type=sa.JSON(),
               nullable=True,
               existing_server_default=sa.text("'[]'::json"))
    op.drop_index(op.f('ix_question_set_test_id'), table_name='question_set')
    op.drop_index(op.f('ix_test_question_question_set_id'), table_name='test_question')


def downgrade():
    op.create_index(op.f('ix_test_question_question_set_id'), 'test_question', ['question_set_id'], unique=False)
    op.create_index(op.f('ix_question_set_test_id'), 'question_set', ['test_id'], unique=False)
    op.alter_column('candidate_test', 'question_set_ids',
               existing_type=sa.JSON(),
               nullable=False,
               existing_server_default=sa.text("'[]'::json"))
