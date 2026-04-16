"""backfill_test_link_from_existing_test_links

Revision ID: d84165c8e013
Revises: efc4eeba0daf
Create Date: 2026-04-16 12:32:47.455140

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd84165c8e013'
down_revision = 'efc4eeba0daf'
branch_labels = None
depends_on = None


def upgrade():
    # Backfill existing Test.link values into test_link using created_by_id as the admin.
    # Preserves all existing shareable URLs for the admin who originally created the test.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, link, created_by_id FROM test "
            "WHERE link IS NOT NULL AND is_template = false AND created_by_id IS NOT NULL"
        )
    ).fetchall()
    if rows:
        conn.execute(
            sa.text(
                "INSERT INTO test_link (uuid, test_id, admin_id, created_date) "
                "VALUES (:uuid, :test_id, :admin_id, NOW()) "
                "ON CONFLICT DO NOTHING"
            ),
            [{"uuid": row.link, "test_id": row.id, "admin_id": row.created_by_id} for row in rows],
        )


def downgrade():
    # Remove all test_link rows that were backfilled from Test.link values
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM test_link WHERE uuid IN "
            "(SELECT link FROM test WHERE link IS NOT NULL)"
        )
    )
