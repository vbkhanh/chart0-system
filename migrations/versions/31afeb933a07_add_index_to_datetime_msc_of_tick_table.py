"""Add index to datetime_msc of tick table

Revision ID: 31afeb933a07
Revises: d91f5bd93aa1
Create Date: 2025-01-23 15:12:25.943354

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '31afeb933a07'
down_revision = 'd91f5bd93aa1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_tick_datetime_msc'), 'tick', ['datetime_msc'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tick_datetime_msc'), table_name='tick')
