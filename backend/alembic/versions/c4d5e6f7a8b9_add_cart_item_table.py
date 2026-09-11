"""add cart_item table (retail vertical)

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cart_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['account.id']),
        sa.ForeignKeyConstraint(['item_id'], ['item.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cart_item_account_id'), 'cart_item', ['account_id'], unique=False)
    op.create_index(op.f('ix_cart_item_item_id'), 'cart_item', ['item_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_cart_item_item_id'), table_name='cart_item')
    op.drop_index(op.f('ix_cart_item_account_id'), table_name='cart_item')
    op.drop_table('cart_item')
