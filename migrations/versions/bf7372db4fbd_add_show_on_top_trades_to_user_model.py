"""Add show_on_top_trades to User model

Revision ID: bf7372db4fbd
Revises: add_strategy_user_id
Create Date: 2024-01-11 11:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bf7372db4fbd'
down_revision = 'add_strategy_user_id'
branch_labels = None
depends_on = None


def upgrade():
    # Add show_on_top_trades column to user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('show_on_top_trades', sa.Boolean(), nullable=True, default=False))

    # Add foreign key constraint with proper name
    with op.batch_alter_table('strategy', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_strategy_user_id_user',  # Give the constraint a name
            'user',
            ['user_id'],
            ['id']
        )


def downgrade():
    # Remove foreign key constraint
    with op.batch_alter_table('strategy', schema=None) as batch_op:
        batch_op.drop_constraint('fk_strategy_user_id_user', type_='foreignkey')

    # Remove show_on_top_trades column
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('show_on_top_trades') 