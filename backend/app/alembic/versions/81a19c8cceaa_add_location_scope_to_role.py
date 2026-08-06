"""add location_scope to role

Revision ID: 81a19c8cceaa
Revises: b2f5a9c81d34
Create Date: 2026-08-06 12:44:09.813765

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '81a19c8cceaa'
down_revision = 'b2f5a9c81d34'
branch_labels = None
depends_on = None


def upgrade():
    role_location_level = sa.Enum("STATE", "DISTRICT", name="rolelocationlevel")
    role_location_level.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "role",
        sa.Column("location_scope", role_location_level, nullable=True),
    )


def downgrade():
    op.drop_column("role", "location_scope")
    sa.Enum(name="rolelocationlevel").drop(op.get_bind(), checkfirst=True)
