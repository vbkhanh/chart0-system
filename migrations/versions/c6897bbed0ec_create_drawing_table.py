"""create drawing table

Revision ID: c6897bbed0ec
Revises: fa5a516ddcf2
Create Date: 2024-12-18 13:38:11.844480

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c6897bbed0ec'
down_revision = 'fa5a516ddcf2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('drawing',
    sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('symbol_id', sa.BIGINT(), nullable=False),
    sa.Column('user_id', sa.BIGINT(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['symbol_id'], ['symbol.id'], name=op.f('fk_drawing_symbol_id_symbol')),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_drawing_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_drawing'))
    )
    op.create_index(op.f('ix_drawing_symbol_id'), 'drawing', ['symbol_id'], unique=False)
    op.create_index(op.f('ix_drawing_user_id'), 'drawing', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_drawing_symbol_id'), table_name='drawing')
    op.drop_index(op.f('ix_drawing_user_id'), table_name='drawing')
    op.drop_table('drawing')
