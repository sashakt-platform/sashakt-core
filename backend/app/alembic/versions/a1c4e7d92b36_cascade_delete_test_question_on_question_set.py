"""cascade delete test_question rows when their question set is deleted

Revision ID: a1c4e7d92b36
Revises: f90256a06aeb
Create Date: 2026-10-14 12:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1c4e7d92b36'
down_revision = 'f90256a06aeb'
branch_labels = None
depends_on = None

FK_NAME = 'fk_test_question_question_set_id_question_set'


def upgrade():
    op.drop_constraint(FK_NAME, 'test_question', type_='foreignkey')
    op.create_foreign_key(
        FK_NAME,
        'test_question',
        'question_set',
        ['question_set_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade():
    op.drop_constraint(FK_NAME, 'test_question', type_='foreignkey')
    op.create_foreign_key(
        FK_NAME,
        'test_question',
        'question_set',
        ['question_set_id'],
        ['id'],
    )
