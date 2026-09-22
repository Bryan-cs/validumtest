"""add clave_api to credenciales_portales

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-09-21

La clave de API del operador (Pago Simple / SuAporte) es distinta de la
contraseña del portal. Cada empresa puede tener la suya; sin esta columna
todo el despliegue comparte PAGOSIMPLE_API_KEY.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'y9z0a1b2c3d4'
down_revision = 'x8y9z0a1b2c3'
branch_labels = None
depends_on = None

TABLE = 'credenciales_portales'
COLUMN = 'clave_api'


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN not in columnas:
        op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN in columnas:
        op.drop_column(TABLE, COLUMN)
