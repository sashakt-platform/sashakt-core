"""Consolidate and remove redundant permissions superseded by broader ones

Revision ID: 803a08724747
Revises: 929353af67bf
Create Date: 2026-08-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '803a08724747'
down_revision = '929353af67bf'
branch_labels = None
depends_on = None


# permission_name -> (description, {role_name: has_permission})
REMOVED_PERMISSIONS = {
    # Consolidated into 'candidate'
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
    # Consolidated into 'question'
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
    # Superseded by 'update_my_organization'
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
    # PATCH /users/me no longer needs a permission check
    "update_user_me": (
        "Update Own User Details",
        {
            "super_admin": True,
            "system_admin": True,
            "state_admin": True,
            "test_admin": True,
            "candidate": True,
        },
    ),
    # Superseded by 'update_my_organization'
    "update_my_organization_settings": (
        "Update Settings for Own Organization",
        {"super_admin": True, "system_admin": True},
    ),
    # Superseded by 'read_candidate'
    "read_form_response": (
        "Read Form Response Details",
        {
            "super_admin": True,
            "system_admin": True,
            "state_admin": True,
            "test_admin": True,
        },
    ),
    # Superseded by 'update_organization'
    "update_organization_settings": (
        "Update Settings for Any Organization",
        {"super_admin": True},
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
