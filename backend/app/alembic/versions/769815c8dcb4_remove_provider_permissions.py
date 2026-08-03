"""Remove provider permissions, superseded by update_my_organization

Revision ID: 769815c8dcb4
Revises: 9c05454d0bbf
Create Date: 2026-08-03 09:46:01.826685

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '769815c8dcb4'
down_revision = '9c05454d0bbf'
branch_labels = None
depends_on = None


# permission_name -> (description, {role_name: has_permission})
REMOVED_PERMISSIONS = {
    "create_provider": (
        "Create New Provider",
        {"super_admin": True, "system_admin": True},
    ),
    "update_provider": (
        "Update Existing Provider",
        {"super_admin": True, "system_admin": True},
    ),
    "delete_provider": (
        "Delete Existing Provider",
        {"super_admin": True, "system_admin": True},
    ),
    "read_provider": (
        "Read Provider Details",
        {"super_admin": True, "system_admin": True},
    ),
}


def upgrade():
    for perm_name in REMOVED_PERMISSIONS:
        op.execute(
            sa.text("""
                DELETE FROM role_permission
                WHERE permission_id = (SELECT id FROM permission WHERE name = :name)
            """).bindparams(name=perm_name)
        )
        op.execute(
            sa.text("DELETE FROM permission WHERE name = :name").bindparams(
                name=perm_name
            )
        )


def downgrade():
    for perm_name, (description, roles) in REMOVED_PERMISSIONS.items():
        op.execute(
            sa.text("""
                INSERT INTO permission (name, description, is_active)
                SELECT :name, :description, true
                WHERE NOT EXISTS (
                    SELECT 1 FROM permission WHERE name = :name
                )
            """).bindparams(name=perm_name, description=description)
        )
        for role_name in roles:
            op.execute(
                sa.text("""
                    INSERT INTO role_permission (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM role r
                    CROSS JOIN permission p
                    WHERE r.name = :role_name
                      AND p.name = :perm_name
                      AND NOT EXISTS (
                          SELECT 1 FROM role_permission rp
                          WHERE rp.role_id = r.id AND rp.permission_id = p.id
                      )
                """).bindparams(role_name=role_name, perm_name=perm_name)
            )
