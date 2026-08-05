"""add scope_by_own_location permission

Revision ID: b3c7e9f1a2d4
Revises: 803a08724747
Create Date: 2026-08-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c7e9f1a2d4'
down_revision = '803a08724747'
branch_labels = None
depends_on = None

PERMISSION_NAME = "scope_by_own_location"
PERMISSION_DESCRIPTION = "Restrict data access to the admin's assigned states/districts"
ROLES_TO_GRANT = ["state_admin", "test_admin"]


def upgrade():
    connection = op.get_bind()

    existing = connection.execute(
        sa.text("SELECT id FROM permission WHERE name = :name"),
        {"name": PERMISSION_NAME},
    ).fetchone()

    if not existing:
        connection.execute(
            sa.text(
                "INSERT INTO permission (name, description, is_active) "
                "VALUES (:name, :description, :is_active)"
            ),
            {
                "name": PERMISSION_NAME,
                "description": PERMISSION_DESCRIPTION,
                "is_active": True,
            },
        )

    permission_id = connection.execute(
        sa.text("SELECT id FROM permission WHERE name = :name"),
        {"name": PERMISSION_NAME},
    ).fetchone()[0]

    roles = connection.execute(
        sa.text("SELECT id, name FROM role WHERE name IN :names").bindparams(
            sa.bindparam("names", expanding=True)
        ),
        {"names": ROLES_TO_GRANT},
    ).fetchall()

    for role_id, _role_name in roles:
        existing_link = connection.execute(
            sa.text(
                "SELECT id FROM role_permission "
                "WHERE role_id = :role_id AND permission_id = :permission_id"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        ).fetchone()

        if not existing_link:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "VALUES (:role_id, :permission_id)"
                ),
                {"role_id": role_id, "permission_id": permission_id},
            )


def downgrade():
    connection = op.get_bind()

    permission = connection.execute(
        sa.text("SELECT id FROM permission WHERE name = :name"),
        {"name": PERMISSION_NAME},
    ).fetchone()

    if permission:
        permission_id = permission[0]
        connection.execute(
            sa.text("DELETE FROM role_permission WHERE permission_id = :permission_id"),
            {"permission_id": permission_id},
        )
        connection.execute(
            sa.text("DELETE FROM permission WHERE id = :permission_id"),
            {"permission_id": permission_id},
        )
