"""add newsletter_signup table (retail vertical)

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'c7d8e9f0a1b2'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'newsletter_signup',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_newsletter_signup_email'), 'newsletter_signup', ['email'], unique=True)
    op.create_index(op.f('ix_newsletter_signup_created_at'), 'newsletter_signup', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_newsletter_signup_created_at'), table_name='newsletter_signup')
    op.drop_index(op.f('ix_newsletter_signup_email'), table_name='newsletter_signup')
    op.drop_table('newsletter_signup')
