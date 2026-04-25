"""drop_municipio_code_from_afiliados

Revision ID: 9a8b7c6d5e4f
Revises: b2c3d4e5f6a7
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa


revision = '9a8b7c6d5e4f'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('afiliados', schema=None) as batch_op:
        batch_op.drop_column('municipio_code')


def downgrade():
    with op.batch_alter_table('afiliados', schema=None) as batch_op:
        batch_op.add_column(sa.Column('municipio_code', sa.String(length=5), nullable=True))
