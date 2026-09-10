"""add returns/restock tracking (retail vertical)

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'e5f6a7b8c9d0'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('item', sa.Column('parent_item_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_item_parent_item_id', 'item', 'item', ['parent_item_id'], ['id']
    )
    op.create_index(op.f('ix_item_parent_item_id'), 'item', ['parent_item_id'], unique=False)

    op.create_table(
        'return_request',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('refund_transaction_id', sa.Integer(), nullable=False),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['refund_transaction_id'], ['transaction.id']),
        sa.ForeignKeyConstraint(['created_by'], ['account.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_return_request_refund_transaction_id'),
        'return_request', ['refund_transaction_id'], unique=False,
    )
    op.create_index(
        op.f('ix_return_request_created_by'), 'return_request', ['created_by'], unique=False
    )
    op.create_index(
        op.f('ix_return_request_created_at'), 'return_request', ['created_at'], unique=False
    )

    op.create_table(
        'return_line',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('return_request_id', sa.Integer(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('discount_item_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['item.id']),
        sa.ForeignKeyConstraint(['return_request_id'], ['return_request.id']),
        sa.ForeignKeyConstraint(['discount_item_id'], ['item.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['account.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_return_line_item_id'), 'return_line', ['item_id'], unique=False)
    op.create_index(
        op.f('ix_return_line_return_request_id'), 'return_line', ['return_request_id'], unique=False
    )
    op.create_index(op.f('ix_return_line_status'), 'return_line', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_return_line_status'), table_name='return_line')
    op.drop_index(op.f('ix_return_line_return_request_id'), table_name='return_line')
    op.drop_index(op.f('ix_return_line_item_id'), table_name='return_line')
    op.drop_table('return_line')

    op.drop_index(op.f('ix_return_request_created_at'), table_name='return_request')
    op.drop_index(op.f('ix_return_request_created_by'), table_name='return_request')
    op.drop_index(op.f('ix_return_request_refund_transaction_id'), table_name='return_request')
    op.drop_table('return_request')

    op.drop_index(op.f('ix_item_parent_item_id'), table_name='item')
    op.drop_constraint('fk_item_parent_item_id', 'item', type_='foreignkey')
    op.drop_column('item', 'parent_item_id')
