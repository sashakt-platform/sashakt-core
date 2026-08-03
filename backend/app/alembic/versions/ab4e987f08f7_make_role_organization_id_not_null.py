"""make role organization_id not null

Revision ID: ab4e987f08f7
Revises: dff7619e3cfb
Create Date: 2026-07-27 12:54:04.041739

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab4e987f08f7'
down_revision = 'dff7619e3cfb'
branch_labels = None
depends_on = None


# Contract step of an expand -> backfill -> contract migration. By this point
# every role row has been backfilled with an organization_id (see revision
# dff7619e3cfb), so it's now safe to enforce NOT NULL and uniqueness.
UQ_NAME = "uq_role_organization_id_name"


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
