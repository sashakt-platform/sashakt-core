"""add form permissions

Revision ID: a1b2c3d4e5f6
Revises: 906b459d2ebc
Create Date: 2026-01-30 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '906b459d2ebc'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # Insert form permissions
    form_permissions = [
        ('create_form', 'Create New Form'),
        ('read_form', 'Read Form Details'),
        ('update_form', 'Update Existing Form'),
        ('delete_form', 'Delete Existing Form'),
        ('read_form_response', 'Read Form Response Details'),
    ]

    for perm_name, perm_desc in form_permissions:
        # Check if permission already exists
        existing = connection.execute(
            sa.text("SELECT id FROM permission WHERE name = :name"),
            {"name": perm_name}
        ).fetchone()

        if not existing:
            connection.execute(
                sa.text(
                    "INSERT INTO permission (name, description, is_active) VALUES (:name, :description, :is_active)"
                ),
                {"name": perm_name, "description": perm_desc, "is_active": True}
            )

    # Get role IDs
    roles = connection.execute(
        sa.text("SELECT id, name FROM role WHERE name IN ('super_admin', 'system_admin', 'state_admin', 'test_admin')")
    ).fetchall()
    role_map = {row[1]: row[0] for row in roles}

    # Get permission IDs for form permissions
    permissions = connection.execute(
        sa.text("SELECT id, name FROM permission WHERE name IN ('create_form', 'read_form', 'update_form', 'delete_form', 'read_form_response')")
    ).fetchall()
    perm_map = {row[1]: row[0] for row in permissions}

    # Define which roles get which permissions
    role_permissions = [
        # create_form: super_admin, system_admin, state_admin, test_admin
        ('super_admin', 'create_form'),
        ('system_admin', 'create_form'),
        ('state_admin', 'create_form'),
        ('test_admin', 'create_form'),
        # read_form: super_admin, system_admin, state_admin, test_admin
        ('super_admin', 'read_form'),
        ('system_admin', 'read_form'),
        ('state_admin', 'read_form'),
        ('test_admin', 'read_form'),
        # update_form: super_admin, system_admin, state_admin, test_admin
        ('super_admin', 'update_form'),
        ('system_admin', 'update_form'),
        ('state_admin', 'update_form'),
        ('test_admin', 'update_form'),
        # delete_form: super_admin, system_admin, state_admin (NOT test_admin)
        ('super_admin', 'delete_form'),
        ('system_admin', 'delete_form'),
        ('state_admin', 'delete_form'),
        # read_form_response: super_admin, system_admin, state_admin, test_admin
        ('super_admin', 'read_form_response'),
        ('system_admin', 'read_form_response'),
        ('state_admin', 'read_form_response'),
        ('test_admin', 'read_form_response'),
    ]

    for role_name, perm_name in role_permissions:
        if role_name in role_map and perm_name in perm_map:
            # Check if role_permission already exists
            existing = connection.execute(
                sa.text("SELECT id FROM role_permission WHERE role_id = :role_id AND permission_id = :permission_id"),
                {"role_id": role_map[role_name], "permission_id": perm_map[perm_name]}
            ).fetchone()

            if not existing:
                connection.execute(
                    sa.text(
                        "INSERT INTO role_permission (role_id, permission_id) VALUES (:role_id, :permission_id)"
                    ),
                    {"role_id": role_map[role_name], "permission_id": perm_map[perm_name]}
                )


def downgrade():
    connection = op.get_bind()

    # Get permission IDs for form permissions
    permissions = connection.execute(
        sa.text("SELECT id FROM permission WHERE name IN ('create_form', 'read_form', 'update_form', 'delete_form', 'read_form_response')")
    ).fetchall()
    perm_ids = [row[0] for row in permissions]

    if perm_ids:
        # Delete role_permission mappings
        for perm_id in perm_ids:
            connection.execute(
                sa.text("DELETE FROM role_permission WHERE permission_id = :perm_id"),
                {"perm_id": perm_id}
            )
        # Delete permissions
        for perm_id in perm_ids:
            connection.execute(
                sa.text("DELETE FROM permission WHERE id = :perm_id"),
                {"perm_id": perm_id}
            )
