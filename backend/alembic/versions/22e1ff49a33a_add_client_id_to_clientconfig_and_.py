"""add_client_id_to_clientconfig_and_subscription

Revision ID: 22e1ff49a33a
Revises: f1e2d3c4b5a6
Create Date: 2026-02-21 21:55:00.878261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22e1ff49a33a'
down_revision: Union[str, None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if tables already exist
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # Create vpn_clients table if it doesn't exist
    if 'vpn_clients' not in existing_tables:
        op.create_table('vpn_clients',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_vpn_clients_id'), 'vpn_clients', ['id'], unique=False)
        op.create_index(op.f('ix_vpn_clients_name'), 'vpn_clients', ['name'], unique=False)

    # Create subscription_plans table if it doesn't exist
    if 'subscription_plans' not in existing_tables:
        op.create_table('subscription_plans',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('duration_days', sa.Integer(), nullable=False),
            sa.Column('traffic_limit_gb', sa.Integer(), nullable=True),
            sa.Column('price', sa.Float(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_subscription_plans_id'), 'subscription_plans', ['id'], unique=False)

    # Add client_id to client_configs if it doesn't exist
    client_configs_columns = [col['name'] for col in inspector.get_columns('client_configs')]
    if 'client_id' not in client_configs_columns:
        op.add_column('client_configs', sa.Column('client_id', sa.Integer(), nullable=True))
        op.create_index('ix_client_configs_client_id', 'client_configs', ['client_id'], unique=False)
        try:
            op.create_index('idx_client_server', 'client_configs', ['client_id', 'server_id'], unique=False)
        except Exception:
            pass

    # Add missing columns to subscriptions
    subscriptions_columns = [col['name'] for col in inspector.get_columns('subscriptions')]
    if 'client_id' not in subscriptions_columns:
        op.add_column('subscriptions', sa.Column('client_id', sa.Integer(), nullable=True))
        op.create_index('ix_subscriptions_client_id', 'subscriptions', ['client_id'], unique=False)
        try:
            op.create_index('idx_client_active', 'subscriptions', ['client_id', 'is_active'], unique=False)
        except Exception:
            pass
    if 'config_id' not in subscriptions_columns:
        op.add_column('subscriptions', sa.Column('config_id', sa.Integer(), nullable=True))
        op.create_index('ix_subscriptions_config_id', 'subscriptions', ['config_id'], unique=False)
        try:
            op.create_index('idx_config_active', 'subscriptions', ['config_id', 'is_active'], unique=False)
        except Exception:
            pass
    if 'plan_id' not in subscriptions_columns:
        op.add_column('subscriptions', sa.Column('plan_id', sa.Integer(), nullable=True))

    # Drop user_id from subscriptions using direct SQL (SQLite compatible)
    # Re-check after potential add operations
    subscriptions_columns_now = [col['name'] for col in sa.inspect(bind).get_columns('subscriptions')]
    if 'user_id' in subscriptions_columns_now:
        # Use raw SQL to recreate subscriptions without user_id
        bind.execute(sa.text("""
            CREATE TABLE subscriptions_new AS
            SELECT id, subscription_type, subscription_start, subscription_end, is_active,
                   traffic_limit_gb, traffic_used_gb, created_at, updated_at,
                   client_id, config_id, plan_id
            FROM subscriptions
        """))
        bind.execute(sa.text("DROP TABLE subscriptions"))
        bind.execute(sa.text("ALTER TABLE subscriptions_new RENAME TO subscriptions"))
        # Recreate the primary key index
        bind.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_subscriptions_id ON subscriptions (id)"))
        bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_is_active ON subscriptions (is_active)"))
        bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_subscription_end ON subscriptions (subscription_end)"))
        bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_client_id ON subscriptions (client_id)"))
        bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_config_id ON subscriptions (config_id)"))
        bind.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_client_active ON subscriptions (client_id, is_active)"))
        bind.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_config_active ON subscriptions (config_id, is_active)"))


def downgrade() -> None:
    # Use batch operations for subscriptions
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key('subscriptions_user_id_fkey', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('idx_user_active', ['user_id', 'is_active'], unique=False)
        batch_op.create_index('ix_subscriptions_user_id', ['user_id'], unique=False)
        batch_op.drop_index('idx_config_active')
        batch_op.drop_index('idx_client_active')
        batch_op.drop_index('ix_subscriptions_config_id')
        batch_op.drop_index('ix_subscriptions_client_id')
        batch_op.drop_constraint('fk_subscriptions_plan_id', type_='foreignkey')
        batch_op.drop_constraint('fk_subscriptions_config_id', type_='foreignkey')
        batch_op.drop_constraint('fk_subscriptions_client_id', type_='foreignkey')
        batch_op.drop_column('plan_id')
        batch_op.drop_column('config_id')
        batch_op.drop_column('client_id')

    # Use batch operations for client_configs
    with op.batch_alter_table('client_configs', schema=None) as batch_op:
        batch_op.drop_index('idx_client_server')
        batch_op.drop_index('ix_client_configs_client_id')
        batch_op.drop_constraint('fk_client_configs_client_id', type_='foreignkey')
        batch_op.drop_column('client_id')

    # Drop tables
    op.drop_index(op.f('ix_subscription_plans_id'), table_name='subscription_plans')
    op.drop_table('subscription_plans')
    op.drop_index(op.f('ix_vpn_clients_name'), table_name='vpn_clients')
    op.drop_index(op.f('ix_vpn_clients_id'), table_name='vpn_clients')
    op.drop_table('vpn_clients')
