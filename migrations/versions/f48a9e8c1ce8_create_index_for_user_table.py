"""Create Index for User table

Revision ID: f48a9e8c1ce8
Revises: 2261612c9ed8
Create Date: 2025-01-09 11:40:17.356492

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f48a9e8c1ce8'
down_revision = '2261612c9ed8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_user_full_name'), 'user', ['full_name'], unique=False)
    op.create_index(op.f('ix_user_date_of_birth'), 'user', ['date_of_birth'], unique=False)
    op.create_index(op.f('ix_user_phone_number'), 'user', ['phone_number'], unique=False)
    op.create_index(op.f('ix_user_role'), 'user', ['role'], unique=False)
    op.create_index(op.f('ix_user_status'), 'user', ['status'], unique=False)
    op.create_index(op.f('ix_user_state'), 'user', ['state'], unique=False)
    op.create_index(op.f('ix_user_is_verified'), 'user', ['is_verified'], unique=False)
    op.create_index(op.f('ix_user_created_at'), 'user', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_full_name'), table_name='user')
    op.drop_index(op.f('ix_user_date_of_birth'), table_name='user')
    op.drop_index(op.f('ix_user_phone_number'), table_name='user')
    op.drop_index(op.f('ix_user_role'), table_name='user')
    op.drop_index(op.f('ix_user_status'), table_name='user')
    op.drop_index(op.f('ix_user_state'), table_name='user')
    op.drop_index(op.f('ix_user_is_verified'), table_name='user')
    op.drop_index(op.f('ix_user_created_at'), table_name='user')
