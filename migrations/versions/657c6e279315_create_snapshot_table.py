"""create snapshot table

Revision ID: 657c6e279315
Revises: b0752ebe1a84
Create Date: 2024-12-16 16:53:41.532231

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '657c6e279315'
down_revision = 'b0752ebe1a84'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('snapshot',
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('url', sa.String(length=255), nullable=False),
    sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BIGINT(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_snapshot_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_snapshot'))
    )
    op.create_index(op.f('ix_snapshot_user_id'), 'snapshot', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_snapshot_user_id'), table_name='snapshot')
    op.drop_table('snapshot')
