"""Consolidate candidate_test and candidate_test_answer permissions into candidate

Revision ID: aa209acb066d
Revises: 929353af67bf
Create Date: 2026-07-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aa209acb066d'
down_revision = '929353af67bf'
branch_labels = None
depends_on = None


# permission_name -> (description, {role_name: has_permission})
REMOVED_PERMISSIONS = {
    "create_candidate_test": (
        "Create New Candidate Test",
        {"candidate": True},
    ),
    "update_candidate_test": (
        "Update Existing Candidate Test",
        {"candidate": True},
    ),
    "delete_candidate_test": (
        "Delete Existing Candidate Test",
        {"super_admin": True},
    ),
    "read_candidate_test": (
        "Read Candidate Test Details",
        {
            "super_admin": True,
            "system_admin": True,
            "state_admin": True,
            "test_admin": True,
        },
    ),
    "create_candidate_test_answer": (
        "Create New Candidate Test Answer",
        {"candidate": True},
    ),
    "update_candidate_test_answer": (
        "Update Existing Candidate Test Answer",
        {"candidate": True},
    ),
    "delete_candidate_test_answer": (
        "Delete Existing Candidate Test Answer",
        {},
    ),
    "read_candidate_test_answer": (
        "Read Candidate Test Answer Details",
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
