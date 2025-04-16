"""add column Code to table Symbol

Revision ID: fb3875e89eff
Revises: 6970afc570cf
Create Date: 2025-01-14 10:41:56.001395

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb3875e89eff'
down_revision = '6970afc570cf'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('symbol', sa.Column('code', sa.String(length=30), unique=True, nullable=True, default=None))


def downgrade():
    op.drop_column('symbol', 'code')
