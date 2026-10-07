"""add shipping_amount to transaction (retail vertical)

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-07

"""
import sqlalchemy as sa
from alembic import op

revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, no backfill: existing orders were charged no shipping,
    # and a walk-in POS sale never has any.
    op.add_column('transaction', sa.Column('shipping_amount', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('transaction', 'shipping_amount')
