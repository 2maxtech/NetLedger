"""add wireguard tunnel fields to routers

Revision ID: 008_wireguard
Revises: 007_multi_tenant
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = '008_wireguard'
down_revision = '007_multi_tenant'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('routers', sa.Column('wg_tunnel_ip', sa.String(45), nullable=True))
    op.add_column('routers', sa.Column('wg_peer_public_key', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('routers', 'wg_peer_public_key')
    op.drop_column('routers', 'wg_tunnel_ip')
