"""add tracking_number to transaction (retail vertical)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'transaction',
        sa.Column('tracking_number', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
    )


def downgrade():
    op.drop_column('transaction', 'tracking_number')
