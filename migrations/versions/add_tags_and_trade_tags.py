"""add tags and trade_tags association table

Revision ID: add_tags_and_trade_tags
Revises: bf7372db4fbd
Create Date: 2024-07-01 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_tags_and_trade_tags'
down_revision = 'bf7372db4fbd'
branch_labels = None
depends_on = None

def upgrade():
    # Create tag table
    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    # Create trade_tags association table
    op.create_table(
        'trade_tags',
        sa.Column('trade_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['trade_id'], ['trade.id'], ),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
        sa.PrimaryKeyConstraint('trade_id', 'tag_id')
    )

def downgrade():
    op.drop_table('trade_tags')
    op.drop_table('tag') 