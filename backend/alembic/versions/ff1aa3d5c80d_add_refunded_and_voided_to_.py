"""add refunded and voided to transactiontype enum

Revision ID: ff1aa3d5c80d
Revises: d37b1048ac2d
Create Date: 2026-08-26 20:20:20.344195

"""
from alembic import op


revision = 'ff1aa3d5c80d'
down_revision = 'd37b1048ac2d'
branch_labels = None
depends_on = None


def upgrade():
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in
    # Postgres — autocommit_block() steps outside Alembic's normal
    # transactional DDL wrapper just for this statement.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'refunded'")
        op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'voided'")


def downgrade():
    # Postgres has no ALTER TYPE ... DROP VALUE — removing an enum
    # value requires rebuilding the type from scratch (rename old type,
    # create new one without the value, migrate the column, drop old
    # type). Not implemented here since it's destructive and rarely
    # needed in practice; if you must roll back, do it manually.
    pass
