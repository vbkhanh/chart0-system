"""create ma list table

Revision ID: ca3420ab8246
Revises: 19b63328dc0e
Create Date: 2024-12-30 15:37:34.943957

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'ca3420ab8246'
down_revision = '19b63328dc0e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ma_list',
    sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
    sa.Column('period', sa.Integer(), nullable=False),
    sa.Column('bar_type', sa.String(length=255), nullable=False),
    sa.Column('points', sa.ARRAY(postgresql.JSONB(astext_type=sa.Text())), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('symbol_id', sa.BIGINT(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ma_list')),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbol.id'], name=op.f('fk_ma_list_symbol_id_symbol'))
    )
    op.create_index(op.f('ix_ma_list_period'), 'ma_list', ['period'], unique=False)
    op.create_index(op.f('ix_ma_list_bar_type'), 'ma_list', ['bar_type'], unique=False)
    op.create_index(op.f('ix_ma_list_symbol_id'), 'ma_list', ['symbol_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ma_list_period'), table_name='ma_list')
    op.drop_index(op.f('ix_ma_list_bar_type'), table_name='ma_list')
    op.drop_index(op.f('ix_ma_list_symbol_id'), table_name='ma_list')
    op.drop_table('ma_list')
