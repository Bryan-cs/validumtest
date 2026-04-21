"""add_municipio_code_to_afiliados

Revision ID: c804bec2074b
Revises: d4e5f6a7b8c9
Create Date: 2026-04-20 21:11:04.106944

"""
from alembic import op
import sqlalchemy as sa


revision = 'c804bec2074b'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('afiliados', schema=None) as batch_op:
        batch_op.add_column(sa.Column('municipio_code', sa.String(length=5), nullable=True))


def downgrade():
    with op.batch_alter_table('afiliados', schema=None) as batch_op:
        batch_op.drop_column('municipio_code')
