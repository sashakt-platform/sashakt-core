"""backfill_admin_id_in_candidate_test

Revision ID: 5b4a66539713
Revises: 1aa2d346ea8b
Create Date: 2026-04-16 13:08:01.526816

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '5b4a66539713'
down_revision = '1aa2d346ea8b'
branch_labels = None
depends_on = None


def upgrade():
    # Populate admin_id for existing candidate_test rows by joining to test_link on test_id.
    # Each existing test has exactly one test_link row (seeded from created_by_id in the
    # earlier backfill migration), so the join is unambiguous.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE candidate_test ct "
            "SET admin_id = tl.created_by_id "
            "FROM test_link tl "
            "WHERE ct.test_id = tl.test_id "
            "AND ct.admin_id IS NULL"
        )
    )
    # All rows are now populated — enforce NOT NULL
    op.alter_column('candidate_test', 'admin_id', nullable=False)


def downgrade():
    op.alter_column('candidate_test', 'admin_id', nullable=True)
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE candidate_test SET admin_id = NULL"))
