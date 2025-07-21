"""Add app_settings table

Revision ID: 2025_06_14_add_app_settings_table
Revises: 
Create Date: 2025-06-14 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2025_06_14_add_app_settings_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create app_settings table
    op.create_table('app_settings',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('setting_key', sa.String(50), nullable=False, unique=True),
        sa.Column('setting_value', sa.String(255), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create index on setting_key for faster lookups
    op.create_index(op.f('ix_app_settings_setting_key'), 'app_settings', ['setting_key'], unique=True)
    
    # Add initial team_updates_locked setting
    op.execute("""
        INSERT INTO app_settings (setting_key, setting_value, description)
        VALUES ('team_updates_locked', 'false', 'Whether team updates are locked (true/false)')
    """)

def downgrade():
    op.drop_index(op.f('ix_app_settings_setting_key'), table_name='app_settings')
    op.drop_table('app_settings')
