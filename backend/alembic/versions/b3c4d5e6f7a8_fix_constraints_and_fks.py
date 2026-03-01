"""fix_constraints_and_fks

Revision ID: b3c4d5e6f7a8
Revises: a722e84a94b3
Create Date: 2026-03-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a722e84a94b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Recreate `subscriptions` with proper PK and FK constraints ──
    # The original migration used CREATE TABLE AS SELECT which loses
    # PRIMARY KEY, FOREIGN KEY, and column type constraints in SQLite.

    bind = op.get_bind()

    # Backup existing data
    bind.execute(sa.text(
        "CREATE TABLE _subscriptions_backup AS SELECT * FROM subscriptions"
    ))

    # Drop all indexes on subscriptions first, then the table
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_id"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_is_active"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_subscription_end"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_client_id"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_config_id"))
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_client_active"))
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_config_active"))
    bind.execute(sa.text("DROP TABLE subscriptions"))

    # Recreate with proper constraints
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('config_id', sa.Integer(), nullable=True),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('subscription_type', sa.Enum(
            'TRIAL', 'MONTHLY', 'QUARTERLY', 'YEARLY', 'LIFETIME',
            name='subscriptiontype',
        ), nullable=True),
        sa.Column('subscription_start', sa.DateTime(), nullable=False),
        sa.Column('subscription_end', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('traffic_limit_gb', sa.Integer(), nullable=True),
        sa.Column('traffic_used_gb', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['vpn_clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['config_id'], ['client_configs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id']),
    )

    # Restore data
    bind.execute(sa.text("""
        INSERT INTO subscriptions (
            id, client_id, config_id, plan_id,
            subscription_type, subscription_start, subscription_end,
            is_active, traffic_limit_gb, traffic_used_gb,
            created_at, updated_at
        )
        SELECT
            id, client_id, config_id, plan_id,
            subscription_type, subscription_start, subscription_end,
            is_active, traffic_limit_gb, traffic_used_gb,
            created_at, updated_at
        FROM _subscriptions_backup
    """))

    bind.execute(sa.text("DROP TABLE _subscriptions_backup"))

    # Recreate indexes
    op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_subscriptions_is_active'), 'subscriptions', ['is_active'], unique=False)
    op.create_index(op.f('ix_subscriptions_subscription_end'), 'subscriptions', ['subscription_end'], unique=False)
    op.create_index(op.f('ix_subscriptions_client_id'), 'subscriptions', ['client_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_config_id'), 'subscriptions', ['config_id'], unique=False)
    op.create_index('idx_client_active', 'subscriptions', ['client_id', 'is_active'], unique=False)
    op.create_index('idx_config_active', 'subscriptions', ['config_id', 'is_active'], unique=False)

    # ── 2. Add FK on client_configs.client_id → vpn_clients.id ──
    with op.batch_alter_table('client_configs', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_client_configs_client_id',
            'vpn_clients',
            ['client_id'],
            ['id'],
            ondelete='CASCADE',
        )


def downgrade() -> None:
    # ── Remove FK from client_configs.client_id ──
    with op.batch_alter_table('client_configs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_client_configs_client_id', type_='foreignkey')

    # ── Revert subscriptions to version without explicit FK constraints ──
    # (matches the state after migration 22e1ff49a33a)
    bind = op.get_bind()

    bind.execute(sa.text(
        "CREATE TABLE _subscriptions_backup AS SELECT * FROM subscriptions"
    ))

    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_id"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_is_active"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_subscription_end"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_client_id"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_subscriptions_config_id"))
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_client_active"))
    bind.execute(sa.text("DROP INDEX IF EXISTS idx_config_active"))
    bind.execute(sa.text("DROP TABLE subscriptions"))

    # Recreate WITHOUT foreign keys (as CREATE TABLE AS SELECT would have done)
    bind.execute(sa.text("""
        CREATE TABLE subscriptions (
            id INTEGER,
            client_id INTEGER,
            config_id INTEGER,
            plan_id INTEGER,
            subscription_type VARCHAR(9),
            subscription_start DATETIME NOT NULL,
            subscription_end DATETIME NOT NULL,
            is_active BOOLEAN,
            traffic_limit_gb INTEGER,
            traffic_used_gb FLOAT,
            created_at DATETIME,
            updated_at DATETIME
        )
    """))

    bind.execute(sa.text("""
        INSERT INTO subscriptions
        SELECT * FROM _subscriptions_backup
    """))

    bind.execute(sa.text("DROP TABLE _subscriptions_backup"))

    # Recreate indexes
    bind.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_subscriptions_id ON subscriptions (id)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_is_active ON subscriptions (is_active)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_subscription_end ON subscriptions (subscription_end)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_client_id ON subscriptions (client_id)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_subscriptions_config_id ON subscriptions (config_id)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_client_active ON subscriptions (client_id, is_active)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_config_active ON subscriptions (config_id, is_active)"))
