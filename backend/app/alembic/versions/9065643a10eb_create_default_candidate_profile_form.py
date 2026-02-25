"""create default candidate profile form

Revision ID: 9065643a10eb
Revises: a1b2c3d4e5f6
Create Date: 2026-02-08 00:58:03.141155

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9065643a10eb'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # Find distinct organizations that have tests with candidate_profile=True
    orgs_with_profile = connection.execute(
        sa.text(
            "SELECT DISTINCT organization_id FROM test "
            "WHERE candidate_profile = TRUE"
        )
    ).fetchall()

    for (org_id,) in orgs_with_profile:
        # Find CLF entity type for this organization
        clf_row = connection.execute(
            sa.text(
                "SELECT id FROM entitytype "
                "WHERE name = 'CLF' AND organization_id = :org_id"
            ),
            {"org_id": org_id}
        ).fetchone()

        if not clf_row:
            continue

        clf_entity_type_id = clf_row[0]

        # Get created_by_id from the first test with candidate_profile in this org
        test_row = connection.execute(
            sa.text(
                "SELECT created_by_id FROM test "
                "WHERE organization_id = :org_id AND candidate_profile = TRUE "
                "ORDER BY id LIMIT 1"
            ),
            {"org_id": org_id}
        ).fetchone()

        created_by_id = test_row[0]

        # Create the Candidate Profile form
        result = connection.execute(
            sa.text(
                "INSERT INTO form (name, description, is_active, organization_id, created_by_id, created_date, modified_date) "
                "VALUES (:name, :description, :is_active, :org_id, :created_by_id, NOW(), NOW()) "
                "RETURNING id"
            ),
            {
                "name": "Candidate Profile",
                "description": "Default candidate profile form",
                "is_active": True,
                "org_id": org_id,
                "created_by_id": created_by_id,
            }
        )
        form_id = result.fetchone()[0]

        # Create the Select CLF entity field
        connection.execute(
            sa.text(
                "INSERT INTO form_field (form_id, field_type, label, name, is_required, \"order\", entity_type_id, created_date, modified_date) "
                "VALUES (:form_id, 'ENTITY', :label, :field_name, :is_required, :order, :entity_type_id, NOW(), NOW())"
            ),
            {
                "form_id": form_id,
                "label": "Select CLF",
                "field_name": "entity_id",
                "is_required": True,
                "order": 0,
                "entity_type_id": clf_entity_type_id,
            }
        )

        # Update all tests with candidate_profile=True in this org to use this form
        connection.execute(
            sa.text(
                "UPDATE test SET form_id = :form_id "
                "WHERE organization_id = :org_id AND candidate_profile = TRUE AND form_id IS NULL"
            ),
            {"form_id": form_id, "org_id": org_id}
        )


def downgrade():
    connection = op.get_bind()

    # Find forms created by this migration
    forms = connection.execute(
        sa.text(
            "SELECT id FROM form "
            "WHERE name = 'Candidate Profile' AND description = 'Default candidate profile form'"
        )
    ).fetchall()

    form_ids = [row[0] for row in forms]

    if form_ids:
        for form_id in form_ids:
            # Unlink tests from these forms
            connection.execute(
                sa.text("UPDATE test SET form_id = NULL WHERE form_id = :form_id"),
                {"form_id": form_id}
            )
            # Delete form fields
            connection.execute(
                sa.text("DELETE FROM form_field WHERE form_id = :form_id"),
                {"form_id": form_id}
            )
            # Delete the form
            connection.execute(
                sa.text("DELETE FROM form WHERE id = :form_id"),
                {"form_id": form_id}
            )
