"""add allowed roles and is restricted to role

Revision ID: d8640b20c143
Revises: daa43ef2e960
Create Date: 2026-08-10 10:51:03.893401

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8640b20c143'
down_revision = 'daa43ef2e960'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "role",
        sa.Column(
            "allowed_roles", sa.JSON(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "role",
        sa.Column(
            "is_restricted", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE role SET allowed_roles = '["system_admin"]', is_restricted = true
            WHERE name = 'super_admin'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE role
            SET allowed_roles = '["system_admin", "state_admin", "test_admin"]',
                is_restricted = true
            WHERE name = 'system_admin'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE role SET allowed_roles = '["state_admin", "test_admin"]', is_restricted = true
            WHERE name = 'state_admin'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE role SET allowed_roles = '["test_admin"]', is_restricted = true
            WHERE name = 'test_admin'
            """
        )
    )
    connection.execute(
        sa.text(
            "UPDATE role SET is_restricted = true WHERE name = 'candidate'"
        )
    )


def downgrade():
    op.drop_column("role", "is_restricted")
    op.drop_column("role", "allowed_roles")
