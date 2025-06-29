"""Add is_admin field to User model

Revision ID: add_admin_field
Revises: 1a2b3c4d5e6f
Create Date: 2025-01-28 19:12:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_admin_field'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_admin column to user table
    op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=True, default=False))


def downgrade():
    # Remove is_admin column from user table
    op.drop_column('user', 'is_admin') 