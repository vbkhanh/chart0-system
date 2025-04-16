"""Add index to category of symbol table

Revision ID: 026bd90c7a6d
Revises: 31afeb933a07
Create Date: 2025-01-23 18:07:11.716630

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026bd90c7a6d'
down_revision = '31afeb933a07'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_symbol_category'), 'symbol', ['category'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_symbol_category'), table_name='symbol')
