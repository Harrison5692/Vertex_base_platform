"""add shipping fields to transaction (retail vertical)

Revision ID: b1c2d3e4f5a6
Revises: 7e6b1357cd37
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'b1c2d3e4f5a6'
down_revision = '7e6b1357cd37'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transaction', sa.Column('shipping_name', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True))
    op.add_column('transaction', sa.Column('shipping_line1', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('transaction', sa.Column('shipping_line2', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('transaction', sa.Column('shipping_city', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.add_column('transaction', sa.Column('shipping_state', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.add_column('transaction', sa.Column('shipping_postal_code', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True))
    op.add_column('transaction', sa.Column('shipping_country', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.add_column('transaction', sa.Column('shipping_phone', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=True))


def downgrade():
    op.drop_column('transaction', 'shipping_phone')
    op.drop_column('transaction', 'shipping_country')
    op.drop_column('transaction', 'shipping_postal_code')
    op.drop_column('transaction', 'shipping_state')
    op.drop_column('transaction', 'shipping_city')
    op.drop_column('transaction', 'shipping_line2')
    op.drop_column('transaction', 'shipping_line1')
    op.drop_column('transaction', 'shipping_name')
