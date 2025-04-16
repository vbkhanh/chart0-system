"""Add index to_time of bar table

Revision ID: 29c64af036e5
Revises: c87408d11c6a
Create Date: 2025-02-04 15:58:57.117899

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29c64af036e5'
down_revision = 'c87408d11c6a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_bar_to_time'), 'bar', ['to_time'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_bar_to_time'), table_name='bar')
