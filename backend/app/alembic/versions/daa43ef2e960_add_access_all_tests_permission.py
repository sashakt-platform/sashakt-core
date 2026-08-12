"""add access_all_tests permission

Revision ID: daa43ef2e960
Revises: 81a19c8cceaa
Create Date: 2026-08-06 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'daa43ef2e960'
down_revision = '81a19c8cceaa'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    perm_name = "access_all_tests"
    perm_desc = "Access, update and delete tests regardless of who created them"

    existing = connection.execute(
        sa.text("SELECT id FROM permission WHERE name = :name"),
        {"name": perm_name},
    ).fetchone()

    if not existing:
        connection.execute(
            sa.text(
                "INSERT INTO permission (name, description, is_active) VALUES (:name, :description, :is_active)"
            ),
            {"name": perm_name, "description": perm_desc, "is_active": True},
        )

    permission_id = connection.execute(
        sa.text("SELECT id FROM permission WHERE name = :name"),
        {"name": perm_name},
    ).fetchone()[0]

    roles = connection.execute(
        sa.text(
            "SELECT id, name FROM role WHERE name IN ('super_admin', 'system_admin')"
        )
    ).fetchall()

    for role_id, _role_name in roles:
        existing_link = connection.execute(
            sa.text(
                "SELECT id FROM role_permission WHERE role_id = :role_id AND permission_id = :permission_id"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        ).fetchone()

        if not existing_link:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) VALUES (:role_id, :permission_id)"
                ),
                {"role_id": role_id, "permission_id": permission_id},
            )


def downgrade():
    connection = op.get_bind()

    permission = connection.execute(
        sa.text("SELECT id FROM permission WHERE name = 'access_all_tests'")
    ).fetchone()

    if permission:
        perm_id = permission[0]
        connection.execute(
            sa.text("DELETE FROM role_permission WHERE permission_id = :perm_id"),
            {"perm_id": perm_id},
        )
        connection.execute(
            sa.text("DELETE FROM permission WHERE id = :perm_id"),
            {"perm_id": perm_id},
        )
