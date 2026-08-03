"""Consolidate question_revision, question_tag, and question_location permissions into question

Revision ID: 9c05454d0bbf
Revises: aa209acb066d
Create Date: 2026-07-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c05454d0bbf'
down_revision = 'aa209acb066d'
branch_labels = None
depends_on = None


# permission_name -> (description, {role_name: has_permission})
REMOVED_PERMISSIONS = {
    "create_question_revision": (
        "Create New Question Revision",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "update_question_revision": (
        "Update Existing Question Revision",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "delete_question_revision": (
        "Delete Existing Question Revision",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "read_question_revision": (
        "Read Question Revision Details",
        {
            "super_admin": True,
            "system_admin": True,
            "state_admin": True,
            "test_admin": True,
        },
    ),
    "create_question_tag": (
        "Create New Question Tag",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "update_question_tag": (
        "Update Existing Question Tag",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "delete_question_tag": (
        "Delete Existing Question Tag",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "read_question_tag": (
        "Read Question Tag Details",
        {
            "super_admin": True,
            "system_admin": True,
            "state_admin": True,
            "test_admin": True,
        },
    ),
    "create_question_location": (
        "Create New Question Location",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "update_question_location": (
        "Update Existing Question Location",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "delete_question_location": (
        "Delete Existing Question Location",
        {"super_admin": True, "system_admin": True, "state_admin": True},
    ),
    "read_question_location": (
        "Read Question Location Details",
        {
            "super_admin": True,
            "system_admin": True,
            "state_admin": True,
            "test_admin": True,
        },
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
