"""add valor_mensual to organizaciones

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
Create Date: 2026-10-06

El cobro del SaaS a cada organización deja de calcularse (antes: utilidad neta
de la empresa) y pasa a ser un valor mensual fijo que el superadmin pone a mano.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'z0a1b2c3d4e5'
down_revision = 'y9z0a1b2c3d4'
branch_labels = None
depends_on = None

TABLE = 'organizaciones'
COLUMN = 'valor_mensual'


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN not in columnas:
        op.add_column(TABLE, sa.Column(COLUMN, sa.Numeric(15, 2), nullable=True, server_default='0'))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN in columnas:
        op.drop_column(TABLE, COLUMN)
