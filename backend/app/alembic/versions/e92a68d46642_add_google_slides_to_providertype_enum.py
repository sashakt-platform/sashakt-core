"""add google_slides to providertype enum

Revision ID: e92a68d46642
Revises: 36fb8ed74f93
Create Date: 2026-01-25 19:44:42.154779

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e92a68d46642"
down_revision = "36fb8ed74f93"
branch_labels = None
depends_on = None


def upgrade():
    # Add GOOGLE_SLIDES to the providertype enum
    op.execute("ALTER TYPE providertype ADD VALUE 'GOOGLE_SLIDES'")


def downgrade():
    # For now, leave the enum value in place (it won't hurt anything)
    pass
