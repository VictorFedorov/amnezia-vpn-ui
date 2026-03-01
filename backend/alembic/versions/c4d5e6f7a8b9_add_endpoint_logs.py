"""add_endpoint_logs

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'endpoint_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('endpoint_ip', sa.String(length=45), nullable=False),
        sa.Column('seen_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['config_id'], ['client_configs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_endpoint_logs_id'), 'endpoint_logs', ['id'], unique=False)
    op.create_index(op.f('ix_endpoint_logs_config_id'), 'endpoint_logs', ['config_id'], unique=False)
    op.create_index('idx_endpoint_config_ip_seen', 'endpoint_logs', ['config_id', 'endpoint_ip', 'seen_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_endpoint_config_ip_seen', table_name='endpoint_logs')
    op.drop_index(op.f('ix_endpoint_logs_config_id'), table_name='endpoint_logs')
    op.drop_index(op.f('ix_endpoint_logs_id'), table_name='endpoint_logs')
    op.drop_table('endpoint_logs')
