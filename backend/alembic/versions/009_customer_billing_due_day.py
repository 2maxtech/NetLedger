"""add billing_due_day to customers

Revision ID: 009_billing_due_day
Revises: 008_wireguard
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = '009_billing_due_day'
down_revision = '008_wireguard'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('billing_due_day', sa.Integer(), nullable=True, server_default='15'))


def downgrade() -> None:
    op.drop_column('customers', 'billing_due_day')
