"""Add screenshot field to Trade model

Revision ID: add_trade_screenshot_field
Revises: add_admin_field
Create Date: 2025-01-28 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_trade_screenshot_field'
down_revision = 'add_admin_field'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('trade', sa.Column('screenshot', sa.String(length=256), nullable=True))

def downgrade():
    op.drop_column('trade', 'screenshot') 