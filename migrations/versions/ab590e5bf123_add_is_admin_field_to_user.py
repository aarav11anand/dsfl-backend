"""Add is_admin field to User

Revision ID: ab590e5bf123
Revises: 54c3347ca87a
Create Date: 2025-06-15 15:19:50.261717

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab590e5bf123'
down_revision = '54c3347ca87a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=True))
    op.execute("UPDATE user SET is_admin = 0 WHERE is_admin IS NULL")
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('is_admin', nullable=False)


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
