"""native Postgres enum types for fulfillment/refund/return status columns

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-07

The migrations that added transaction.fulfillment_status,
refund_approval.status and return_line.status created them as plain
VARCHAR, but the models declare them as Python Enums — which
SQLAlchemy binds as native Postgres enum types (fulfillmentstatus,
refundapprovalstatus, returnlinestatus). On a database built purely
from migrations those types never existed, so every insert that set
one of these columns failed with 'type "fulfillmentstatus" does not
exist': online checkout, refund requests, returns. This brings the
schema in line with the models, the same way transactiontype and
paymentmethod already work.

Safe on any existing database: CREATE TYPE is skipped if the type is
already there, and the column conversion casts through text, so it
works whether the column is currently VARCHAR or already the enum.
Existing values are kept (they're the same strings).
"""
from alembic import op

revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None

_COLUMNS = [
    ('transaction', 'fulfillment_status', 'fulfillmentstatus',
     ['pending', 'processing', 'shipped', 'delivered', 'cancelled']),
    ('refund_approval', 'status', 'refundapprovalstatus',
     ['pending', 'approved', 'denied']),
    ('return_line', 'status', 'returnlinestatus',
     ['pending_inspection', 'restocked', 'restocked_discounted', 'discarded']),
]


def upgrade() -> None:
    for table, column, type_name, values in _COLUMNS:
        labels = ', '.join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {type_name} AS ENUM ({labels}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        )
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN {column} '
            f'TYPE {type_name} USING {column}::text::{type_name}'
        )


def downgrade() -> None:
    for table, column, type_name, _ in _COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN {column} TYPE VARCHAR USING {column}::text'
        )
        op.execute(f'DROP TYPE IF EXISTS {type_name}')
