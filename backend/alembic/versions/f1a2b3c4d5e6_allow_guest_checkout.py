"""allow guest checkout: nullable transaction.created_by, add guest_email

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'f1a2b3c4d5e6'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('transaction', 'created_by', existing_type=sa.Integer(), nullable=True)
    op.add_column(
        'transaction',
        sa.Column('guest_email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    )


def downgrade():
    op.drop_column('transaction', 'guest_email')
    # NOTE: reverting created_by to NOT NULL will fail here if any
    # guest-checkout rows (created_by IS NULL) exist by the time this
    # runs — that data has to be backfilled or removed first. Left as
    # a straight alter rather than silently deleting rows.
    op.alter_column('transaction', 'created_by', existing_type=sa.Integer(), nullable=False)
