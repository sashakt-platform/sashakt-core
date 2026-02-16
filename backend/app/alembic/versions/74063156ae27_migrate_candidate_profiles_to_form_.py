"""migrate candidate profiles to form responses

Revision ID: 74063156ae27
Revises: 9065643a10eb
Create Date: 2026-02-16 14:36:47.161089

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74063156ae27'
down_revision = '9065643a10eb'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # Migrate candidate_test_profile data into form_response.
    # Join path: candidate_test_profile -> candidate_test -> test (for form_id)
    # Only migrate where test.form_id IS NOT NULL (set by previous migration 9065643a10eb)
    # ON CONFLICT DO NOTHING makes this idempotent.
    connection.execute(
        sa.text("""
            INSERT INTO form_response (candidate_test_id, form_id, responses, created_date)
            SELECT
                ctp.candidate_test_id,
                t.form_id,
                json_build_object('entity_id', ctp.entity_id),
                ctp.created_date
            FROM candidate_test_profile ctp
            JOIN candidate_test ct ON ctp.candidate_test_id = ct.id
            JOIN test t ON ct.test_id = t.id
            WHERE t.form_id IS NOT NULL
            ON CONFLICT (candidate_test_id, form_id) DO NOTHING
        """)
    )


def downgrade():
    connection = op.get_bind()

    # Delete form_response rows that were migrated from candidate_test_profile.
    # Identified by having a matching candidate_test_id in candidate_test_profile.
    connection.execute(
        sa.text("""
            DELETE FROM form_response fr
            WHERE EXISTS (
                SELECT 1 FROM candidate_test_profile ctp
                WHERE ctp.candidate_test_id = fr.candidate_test_id
            )
        """)
    )
