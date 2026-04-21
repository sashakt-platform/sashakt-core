"""add pause timer fields

Revision ID: aa4fc4afb4ff
Revises: 57ac4abbbad5
Create Date: 2026-04-21 18:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aa4fc4afb4ff"
down_revision: str | Sequence[str] | None = "57ac4abbbad5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test",
        sa.Column(
            "pause_timer_when_inactive",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "candidate_test",
        sa.Column(
            "active_time_spent_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "candidate_test",
        sa.Column("last_timer_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "candidate_test",
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_test", "last_heartbeat_at")
    op.drop_column("candidate_test", "last_timer_started_at")
    op.drop_column("candidate_test", "active_time_spent_seconds")
    op.drop_column("test", "pause_timer_when_inactive")
