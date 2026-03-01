"""Encrypt SSH passwords in servers table

Revision ID: f1e2d3c4b5a6
Revises: 363a3fc9ce31
Create Date: 2026-02-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, None] = '363a3fc9ce31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Изменяем поле ssh_password на ssh_password_encrypted
    и меняем тип с VARCHAR на TEXT для хранения зашифрованных данных
    """
    # Для SQLite переименование столбца требует пересоздания таблицы
    # Для PostgreSQL можно использовать ALTER TABLE RENAME COLUMN
    
    # Проверяем тип БД
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        # SQLite: пересоздаем таблицу
        with op.batch_alter_table('servers', schema=None) as batch_op:
            batch_op.add_column(sa.Column('ssh_password_encrypted', sa.Text(), nullable=True))
        
        # Копируем данные из старого поля в новое (без шифрования для обратной совместимости)
        # В production данные нужно будет зашифровать отдельным скриптом
        op.execute('UPDATE servers SET ssh_password_encrypted = ssh_password WHERE ssh_password IS NOT NULL')
        
        with op.batch_alter_table('servers', schema=None) as batch_op:
            batch_op.drop_column('ssh_password')
    else:
        # PostgreSQL: переименовываем и меняем тип
        op.alter_column('servers', 'ssh_password', 
                       new_column_name='ssh_password_encrypted',
                       type_=sa.Text(),
                       existing_type=sa.String(255))


def downgrade() -> None:
    """
    Откатываем изменения: возвращаем ssh_password
    """
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('servers', schema=None) as batch_op:
            batch_op.add_column(sa.Column('ssh_password', sa.String(255), nullable=True))
        
        op.execute('UPDATE servers SET ssh_password = ssh_password_encrypted WHERE ssh_password_encrypted IS NOT NULL')
        
        with op.batch_alter_table('servers', schema=None) as batch_op:
            batch_op.drop_column('ssh_password_encrypted')
    else:
        op.alter_column('servers', 'ssh_password_encrypted',
                       new_column_name='ssh_password',
                       type_=sa.String(255),
                       existing_type=sa.Text())
