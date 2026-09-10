"""add fulfillment_status to transaction (retail vertical)

Revision ID: d3e4f5a6b7c8
Revises: c7d8e9f0a1b2
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'd3e4f5a6b7c8'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'transaction',
        sa.Column('fulfillment_status', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f('ix_transaction_fulfillment_status'), 'transaction', ['fulfillment_status'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_transaction_fulfillment_status'), table_name='transaction')
    op.drop_column('transaction', 'fulfillment_status')
