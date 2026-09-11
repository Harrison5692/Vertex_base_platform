"""add item variants and gallery images (retail vertical)

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('item', sa.Column('variant_parent_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_item_variant_parent_id', 'item', 'item', ['variant_parent_id'], ['id']
    )
    op.create_index(
        op.f('ix_item_variant_parent_id'), 'item', ['variant_parent_id'], unique=False
    )
    op.add_column(
        'item',
        sa.Column('variant_label', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    )

    op.create_table(
        'item_image',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('url', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['item.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_item_image_item_id'), 'item_image', ['item_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_item_image_item_id'), table_name='item_image')
    op.drop_table('item_image')

    op.drop_column('item', 'variant_label')
    op.drop_index(op.f('ix_item_variant_parent_id'), table_name='item')
    op.drop_constraint('fk_item_variant_parent_id', 'item', type_='foreignkey')
    op.drop_column('item', 'variant_parent_id')
