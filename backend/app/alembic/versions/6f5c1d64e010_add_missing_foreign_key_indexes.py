"""add missing foreign key indexes

Revision ID: 6f5c1d64e010
Revises: cc398777935d
Create Date: 2026-07-09 03:25:51.361437

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '6f5c1d64e010'
down_revision = 'cc398777935d'
branch_labels = None
depends_on = None


# (table_name, column_name) — index name is ix_<table>_<column>.
# Only single-column FKs that are not already covered by an explicit
# index=True flag or the leftmost column of a UniqueConstraint.
FK_INDEXES: list[tuple[str, str]] = [
    ("candidate", "user_id"),
    ("candidate", "organization_id"),
    ("candidate_test", "candidate_id"),
    ("candidate_test", "admin_id"),
    ("candidate_test_answer", "candidate_test_id"),
    ("candidate_test_answer", "question_revision_id"),
    ("candidate_test_profile", "entity_id"),
    ("test", "created_by_id"),
    ("test", "organization_id"),
    ("test", "template_id"),
    ("test", "certificate_id"),
    ("test", "form_id"),
    ("test_question", "question_set_id"),
    ("question", "organization_id"),
    ("question_revision", "question_id"),
    ("question_revision", "created_by_id"),
    ("user", "organization_id"),
    ("user", "created_by_id"),
    ("tag", "tag_type_id"),
    ("tag", "organization_id"),
    ("tag", "created_by_id"),
    ("entity", "entity_type_id"),
    ("entity", "state_id"),
    ("entity", "district_id"),
    ("entity", "block_id"),
    ("entity", "created_by_id"),
    ("form", "organization_id"),
    ("form", "created_by_id"),
    ("certificate", "organization_id"),
    ("certificate", "created_by_id"),
]


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction, so we need
    # an autocommit block. IF NOT EXISTS keeps the migration idempotent if
    # a prior run failed partway through.
    with op.get_context().autocommit_block():
        for table, column in FK_INDEXES:
            op.execute(
                f'CREATE INDEX CONCURRENTLY IF NOT EXISTS '
                f'"ix_{table}_{column}" ON "{table}" ("{column}")'
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for table, column in reversed(FK_INDEXES):
            op.execute(
                f'DROP INDEX CONCURRENTLY IF EXISTS "ix_{table}_{column}"'
            )
