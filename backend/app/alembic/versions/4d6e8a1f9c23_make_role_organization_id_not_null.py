"""make role organization_id not null

Revision ID: 4d6e8a1f9c23
Revises: 7f3a9c2e5b81
Create Date: 2026-08-16 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d6e8a1f9c23'
down_revision = '7f3a9c2e5b81'
branch_labels = None
depends_on = None


# Contract step of an expand -> backfill -> contract migration. By this point
# every role row has been backfilled with an organization_id (see revision
# 7f3a9c2e5b81), so it's now safe to enforce NOT NULL and uniqueness.
UQ_NAME = "role_organization_id_name_key"


def upgrade():
    op.alter_column(
        "role", "organization_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.create_unique_constraint(UQ_NAME, "role", ["organization_id", "name"])


def downgrade():
    op.drop_constraint(UQ_NAME, "role", type_="unique")
    op.alter_column(
        "role", "organization_id", existing_type=sa.INTEGER(), nullable=True
    )
