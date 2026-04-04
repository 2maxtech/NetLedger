"""rename kerio_user_id to mikrotik_secret_id, add mikrotik_queue_id

Revision ID: 003_mikrotik
Revises: 002_kerio
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = '003_mikrotik'
down_revision = '002_kerio'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('customers', 'kerio_user_id', new_column_name='mikrotik_secret_id')
    op.add_column('customers', sa.Column('mikrotik_queue_id', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'mikrotik_queue_id')
    op.alter_column('customers', 'mikrotik_secret_id', new_column_name='kerio_user_id')
