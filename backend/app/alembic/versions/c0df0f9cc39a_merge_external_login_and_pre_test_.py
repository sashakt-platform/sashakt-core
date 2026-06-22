"""merge external_login and pre_test_instructions heads

Revision ID: c0df0f9cc39a
Revises: 8d7a2c9f1b34, fe6a2f1b6886
Create Date: 2026-06-19 00:28:49.569706

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'c0df0f9cc39a'
down_revision = ('8d7a2c9f1b34', 'fe6a2f1b6886')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
