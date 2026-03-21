"""seed default providers

Revision ID: 0344796ba737
Revises: db0cc58b6583
Create Date: 2026-03-21 08:38:12.047332

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '0344796ba737'
down_revision = 'db0cc58b6583'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO provider (name, provider_type, description, is_active)
        SELECT 'Big Query', 'BIGQUERY', 'Google BigQuery data sync provider', true
        WHERE NOT EXISTS (SELECT 1 FROM provider WHERE provider_type = 'BIGQUERY')
    """)
    op.execute("""
        INSERT INTO provider (name, provider_type, description, is_active)
        SELECT 'Google Slides', 'GOOGLE_SLIDES', 'Google Slides certificate provider', true
        WHERE NOT EXISTS (SELECT 1 FROM provider WHERE provider_type = 'GOOGLE_SLIDES')
    """)
    op.execute("""
        INSERT INTO provider (name, provider_type, description, is_active)
        SELECT 'Google Cloud Storage', 'GCS', 'Google Cloud Storage media provider', true
        WHERE NOT EXISTS (SELECT 1 FROM provider WHERE provider_type = 'GCS')
    """)


def downgrade():
    op.execute("""
        DELETE FROM provider
        WHERE provider_type IN ('BIGQUERY', 'GOOGLE_SLIDES', 'GCS')
        AND id NOT IN (SELECT provider_id FROM organization_provider)
    """)
