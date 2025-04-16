"""Add Index to Columns

Revision ID: d91f5bd93aa1
Revises: 9831b6a87ae7
Create Date: 2025-01-21 11:34:07.901862

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd91f5bd93aa1'
down_revision = '9831b6a87ae7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_bar_from_time'), 'bar', ['from_time'], unique=False)
    op.create_index(op.f('ix_watchlist_user_id'), 'watchlist', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_bar_from_time'), table_name='bar')
    op.drop_index(op.f('ix_watchlist_user_id'), table_name='watchlist')
