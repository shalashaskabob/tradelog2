"""Make strategies user-specific by adding user_id and unique constraint

Revision ID: add_strategy_user_id
Revises: add_trade_screenshot_field
Create Date: 2025-01-28 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_strategy_user_id'
down_revision = 'add_trade_screenshot_field'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('strategy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('_user_strategy_uc', ['name', 'user_id'])
    # If you want to set user_id for existing strategies, you can do it here (e.g., assign to admin or null user)
    # For now, leave as nullable, then alter to non-nullable after manual data migration if needed

def downgrade():
    with op.batch_alter_table('strategy', schema=None) as batch_op:
        batch_op.drop_constraint('_user_strategy_uc', type_='unique')
        batch_op.drop_column('user_id') 