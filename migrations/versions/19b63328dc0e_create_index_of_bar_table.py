"""create index of bar table

Revision ID: 19b63328dc0e
Revises: c6897bbed0ec
Create Date: 2024-12-18 14:38:12.169060

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '19b63328dc0e'
down_revision = 'c6897bbed0ec'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_bar_symbol_id'), 'bar', ['symbol_id'], unique=False)
    op.create_index(op.f('ix_bar_type'), 'bar', ['type'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_bar_symbol_id'), table_name='bar')
    op.drop_index(op.f('ix_bar_type'), table_name='bar')
