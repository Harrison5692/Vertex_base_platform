"""add discount_code table + discount fields on transaction (retail vertical)

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-07

"""
import sqlalchemy as sa
from alembic import op

revision = 'a8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'discount_code',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        # Native enum — matches how the model binds it (see the
        # f7a8b9c0d1e2 migration for what happens when these disagree).
        sa.Column('kind', sa.Enum('percent', 'fixed', name='discountkind'), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('min_subtotal', sa.Float(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('uses_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('account.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('value > 0', name='ck_discount_code_value_positive'),
        sa.CheckConstraint(
            "kind != 'percent' OR value <= 100", name='ck_discount_code_percent_max_100'
        ),
    )
    op.create_index('ix_discount_code_code', 'discount_code', ['code'], unique=True)
    op.add_column('transaction', sa.Column('discount_code', sa.String(length=50), nullable=True))
    op.add_column('transaction', sa.Column('discount_amount', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('transaction', 'discount_amount')
    op.drop_column('transaction', 'discount_code')
    op.drop_index('ix_discount_code_code', table_name='discount_code')
    op.drop_table('discount_code')
    op.execute('DROP TYPE IF EXISTS discountkind')
