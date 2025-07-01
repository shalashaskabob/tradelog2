"""Reset last_seen to NULL for existing users

Revision ID: reset_last_seen_for_existing_users
Revises: add_last_seen_to_user
Create Date: 2025-07-01 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'reset_last_seen_for_existing_users'
down_revision = 'add_last_seen_to_user'
branch_labels = None
depends_on = None

def upgrade():
    # Reset last_seen to NULL for all existing users
    # This ensures only users who actually log in and use the app show as "online"
    op.execute('UPDATE "user" SET last_seen = NULL')

def downgrade():
    # Set last_seen back to current timestamp for all users
    op.execute('UPDATE "user" SET last_seen = CURRENT_TIMESTAMP WHERE last_seen IS NULL') 