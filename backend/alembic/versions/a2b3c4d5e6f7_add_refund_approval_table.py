"""add refund_approval table (retail vertical)

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'refund_approval',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_transaction_id', sa.Integer(), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column('requested_amount', sa.Float(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('requested_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column('resulting_transaction_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['original_transaction_id'], ['transaction.id']),
        sa.ForeignKeyConstraint(['requested_by'], ['account.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['account.id']),
        sa.ForeignKeyConstraint(['resulting_transaction_id'], ['transaction.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_refund_approval_original_transaction_id'),
        'refund_approval', ['original_transaction_id'], unique=False,
    )
    op.create_index(
        op.f('ix_refund_approval_status'), 'refund_approval', ['status'], unique=False
    )
    op.create_index(
        op.f('ix_refund_approval_requested_by'), 'refund_approval', ['requested_by'], unique=False
    )
    op.create_index(
        op.f('ix_refund_approval_created_at'), 'refund_approval', ['created_at'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_refund_approval_created_at'), table_name='refund_approval')
    op.drop_index(op.f('ix_refund_approval_requested_by'), table_name='refund_approval')
    op.drop_index(op.f('ix_refund_approval_status'), table_name='refund_approval')
    op.drop_index(
        op.f('ix_refund_approval_original_transaction_id'), table_name='refund_approval'
    )
    op.drop_table('refund_approval')
