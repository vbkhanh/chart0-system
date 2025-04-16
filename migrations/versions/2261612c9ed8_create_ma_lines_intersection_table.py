"""create ma lines intersection table

Revision ID: 2261612c9ed8
Revises: ca3420ab8246
Create Date: 2024-12-30 16:01:32.650225

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '2261612c9ed8'
down_revision = 'ca3420ab8246'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ma_lines_intersection',
    sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
    sa.Column('line1_period', sa.Integer(), nullable=False),
    sa.Column('line2_period', sa.Integer(), nullable=False),
    sa.Column('bar_type', sa.String(length=255), nullable=False),
    sa.Column('points', sa.ARRAY(postgresql.JSONB(astext_type=sa.Text())), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('symbol_id', sa.BIGINT(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ma_lines_intersection')),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbol.id'], name=op.f('fk_ma_lines_intersection_symbol_id_symbol'))
    )
    op.create_index(op.f('ix_ma_lines_intersection_bar_type'), 'ma_lines_intersection', ['bar_type'], unique=False)
    op.create_index(op.f('ix_ma_lines_intersection_symbol_id'), 'ma_lines_intersection', ['symbol_id'], unique=False)


def downgrade():
    pass
