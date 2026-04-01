"""add question sets for tests

Revision ID: 4f2c8a6d9b11
Revises: 7d90fad13571
Create Date: 2026-03-24 19:15:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = '4f2c8a6d9b11'
down_revision = '7d90fad13571'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'question_set',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('modified_date', sa.DateTime(), nullable=True),
        sa.Column('test_id', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('max_questions_allowed_to_attempt', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('marking_scheme', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['test_id'], ['test.id'], ondelete='CASCADE'),
        sa.UniqueConstraint(
            'test_id',
            'display_order',
            name='uq_question_set_test_id_display_order',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_question_set_test_id', 'question_set', ['test_id'])
    op.add_column('test_question', sa.Column('question_set_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_test_question_question_set_id_question_set',
        'test_question',
        'question_set',
        ['question_set_id'],
        ['id'],
    )
    op.create_index('ix_test_question_question_set_id', 'test_question', ['question_set_id'])
    op.add_column(
        'candidate_test',
        sa.Column('question_set_ids', sa.JSON(), server_default='[]', nullable=False),
    )


def downgrade():
    op.drop_column('candidate_test', 'question_set_ids')
    op.drop_index('ix_test_question_question_set_id', table_name='test_question')
    op.drop_constraint(
        'fk_test_question_question_set_id_question_set',
        'test_question',
        type_='foreignkey',
    )
    op.drop_column('test_question', 'question_set_id')
    op.drop_index('ix_question_set_test_id', table_name='question_set')
    op.drop_table('question_set')
