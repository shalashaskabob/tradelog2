"""Add last_seen field to User model

Revision ID: add_last_seen_to_user
Revises: add_tags_and_trade_tags
Create Date: 2025-07-01 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_last_seen_to_user'
down_revision = 'add_tags_and_trade_tags'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('user', sa.Column('last_seen', sa.DateTime(), nullable=True))
    op.execute('UPDATE "user" SET last_seen = CURRENT_TIMESTAMP WHERE last_seen IS NULL')

def downgrade():
    op.drop_column('user', 'last_seen') 