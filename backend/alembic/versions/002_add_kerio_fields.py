"""add kerio_user_id and mac_address to customers

Revision ID: 002_kerio
Revises: 001
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = '002_kerio'
down_revision = 'ee5ce3a16489'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('kerio_user_id', sa.String(100), nullable=True))
    op.add_column('customers', sa.Column('mac_address', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'mac_address')
    op.drop_column('customers', 'kerio_user_id')
