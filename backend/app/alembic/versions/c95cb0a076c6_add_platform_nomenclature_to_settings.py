"""add platform nomenclature to settings

Revision ID: c95cb0a076c6
Revises: 57ac4abbbad5
Create Date: 2026-04-21 22:39:33.554426

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c95cb0a076c6'
down_revision = '57ac4abbbad5'
branch_labels = None
depends_on = None


# Frozen snapshot — do not reference live model constants.
_NOMENCLATURE_TERMS = [
    "dashboard",
    "question_bank",
    "test_templates",
    "test_template",
    "tests",
    "test",
    "tag_management",
    "tags",
    "tag",
    "tag_types",
    "tag_type",
    "forms",
    "form",
    "certificates",
    "certificate",
    "entities",
    "entity",
    "users",
    "user",
]

_FROZEN_NOMENCLATURE_DEFAULT = {
    "mode": "default",
    "value": {term: "" for term in _NOMENCLATURE_TERMS},
}


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE organization_settings
            SET settings = settings
                || jsonb_build_object('platform_nomenclature', CAST(:nom AS JSONB))
                || jsonb_build_object('version', 2)
            """
        ).bindparams(nom=json.dumps(_FROZEN_NOMENCLATURE_DEFAULT))
    )


def downgrade():
    op.execute(
        """
        UPDATE organization_settings
        SET settings = (settings - 'platform_nomenclature')
            || jsonb_build_object('version', 1)
        """
    )
