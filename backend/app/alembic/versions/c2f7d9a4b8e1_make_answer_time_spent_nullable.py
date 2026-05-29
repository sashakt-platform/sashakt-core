"""make answer time spent nullable

Revision ID: c2f7d9a4b8e1
Revises: b3e9f2a1c047
Create Date: 2026-05-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f7d9a4b8e1"
down_revision: str | Sequence[str] | None = "b3e9f2a1c047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "candidate_test_answer",
        "time_spent",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
    )
    op.execute("UPDATE candidate_test_answer SET time_spent = NULL WHERE time_spent = 0")


def downgrade() -> None:
    op.execute("UPDATE candidate_test_answer SET time_spent = 0 WHERE time_spent IS NULL")
