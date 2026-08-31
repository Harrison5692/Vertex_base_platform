"""add email_opt_in field

Revision ID: 61c8d0719696
Revises: 5d07c0348d72
Create Date: 2026-08-31 16:34:03.475938

"""
from alembic import op
import sqlalchemy as sa


revision = '61c8d0719696'
down_revision = '5d07c0348d72'
branch_labels = None
depends_on = None


def upgrade():
    # server_default is required here: existing rows already have data,
    # and a NOT NULL column with no default has nothing to backfill
    # them with — Postgres would reject the ALTER TABLE outright.
    op.add_column(
        'account',
        sa.Column('email_opt_in', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade():
    op.drop_column('account', 'email_opt_in')
