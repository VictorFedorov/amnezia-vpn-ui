"""add is_default to subscription_plans

Revision ID: a1b2c3d4e5f6
Revises: 22e1ff49a33a
Create Date: 2026-02-22 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '22e1ff49a33a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('subscription_plans') as batch_op:
        batch_op.add_column(sa.Column('is_default', sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('subscription_plans') as batch_op:
        batch_op.drop_column('is_default')
