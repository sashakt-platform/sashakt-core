"""Initial migration

Revision ID: 489ffc816c1a
Revises:
Create Date: 2025-04-04 09:23:12.111714

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '489ffc816c1a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('country',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_country_name'), 'country', ['name'], unique=False)
    op.create_table('organization',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organization_name'), 'organization', ['name'], unique=False)
    op.create_table('permission',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('question',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('question', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_question_question'), 'question', ['question'], unique=False)
    op.create_table('role',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('label', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('role_permission',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('permission_id', 'role_id')
    )
    op.create_table('state',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('country_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['country_id'], ['country.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_state_name'), 'state', ['name'], unique=False)
    op.create_table('user',
    sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('phone', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('hashed_password', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('token', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('refresh_token', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_table('candidate',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('district',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('state_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['state_id'], ['state.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_district_name'), 'district', ['name'], unique=False)
    op.create_table('tagtype',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tagtype_name'), 'tagtype', ['name'], unique=False)
    op.create_table('test',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('start_time', sa.DateTime(), nullable=True),
    sa.Column('end_time', sa.DateTime(), nullable=True),
    sa.Column('time_limit', sa.Integer(), nullable=True),
    sa.Column('marks_level', sa.Enum('QUESTION', 'TEST', name='markslevelenum'), nullable=True),
    sa.Column('marks', sa.Integer(), nullable=True),
    sa.Column('completion_message', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('start_instructions', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('link', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('no_of_attempts', sa.Integer(), nullable=False),
    sa.Column('shuffle', sa.Boolean(), nullable=False),
    sa.Column('random_questions', sa.Boolean(), nullable=False),
    sa.Column('no_of_questions', sa.Integer(), nullable=False),
    sa.Column('question_pagination', sa.Integer(), nullable=False),
    sa.Column('is_template', sa.Boolean(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['test.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_test_name'), 'test', ['name'], unique=False)
    op.create_table('block',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('district_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['district_id'], ['district.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_block_name'), 'block', ['name'], unique=False)
    op.create_table('candidate_test',
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('candidate_id', sa.Integer(), nullable=False),
    sa.Column('device', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('consent', sa.Boolean(), nullable=False),
    sa.Column('start_time', sa.DateTime(), nullable=False),
    sa.Column('end_time', sa.DateTime(), nullable=False),
    sa.Column('is_submitted', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidate.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('test_id', 'candidate_id')
    )
    op.create_table('tag',
    sa.Column('tag_type_id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], ),
    sa.ForeignKeyConstraint(['tag_type_id'], ['tagtype.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tag_name'), 'tag', ['name'], unique=False)
    op.create_table('test_question',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('test_id', 'question_id')
    )
    op.create_table('test_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('state_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['state_id'], ['state.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('test_id', 'state_id')
    )
    op.create_table('candidate_test_answer',
    sa.Column('candidate_test_id', sa.Integer(), nullable=False),
    sa.Column('question_revision_id', sa.Integer(), nullable=False),
    sa.Column('response', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('visited', sa.Boolean(), nullable=False),
    sa.Column('time_spent', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('modified_date', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['candidate_test_id'], ['candidate_test.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['question_revision_id'], ['question.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('test_tag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_date', sa.DateTime(), nullable=True),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['test.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('test_id', 'tag_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('test_tag')
    op.drop_table('candidate_test_answer')
    op.drop_table('test_state')
    op.drop_table('test_question')
    op.drop_index(op.f('ix_tag_name'), table_name='tag')
    op.drop_table('tag')
    op.drop_table('candidate_test')
    op.drop_index(op.f('ix_block_name'), table_name='block')
    op.drop_table('block')
    op.drop_index(op.f('ix_test_name'), table_name='test')
    op.drop_table('test')
    op.drop_index(op.f('ix_tagtype_name'), table_name='tagtype')
    op.drop_table('tagtype')
    op.drop_index(op.f('ix_district_name'), table_name='district')
    op.drop_table('district')
    op.drop_table('candidate')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_state_name'), table_name='state')
    op.drop_table('state')
    op.drop_table('role_permission')
    op.drop_table('role')
    op.drop_index(op.f('ix_question_question'), table_name='question')
    op.drop_table('question')
    op.drop_table('permission')
    op.drop_index(op.f('ix_organization_name'), table_name='organization')
    op.drop_table('organization')
    op.drop_index(op.f('ix_country_name'), table_name='country')
    op.drop_table('country')
    # ### end Alembic commands ###
