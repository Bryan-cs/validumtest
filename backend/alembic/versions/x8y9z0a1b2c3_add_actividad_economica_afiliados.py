"""add actividad_economica to afiliados

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-09-20

El campo 98 del registro tipo 2 lleva la actividad economica sobre la que se
cotiza a riesgos laborales, y su primer digito es la clase de riesgo: 1661401
es clase 1 y 5960901 es clase 5 (Decreto 1607 de 2002).

Hasta ahora se escribia la actividad principal del aportante para todos sus
cotizantes. Eso funciona mientras todos compartan clase de riesgo, y deja de
funcionar en cuanto uno no la comparte: el operador devuelve "El codigo
registrado en el campo de actividad economica para ARL no coincide con la
clase de riesgo del cotizante".

Nullable: quien no la tenga sigue heredando la del aportante, que es el caso
de la mayoria.

Idempotente, como las anteriores: si la columna ya existe se omite y la
revision queda registrada sin error.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'x8y9z0a1b2c3'
down_revision = 'w7x8y9z0a1b2'
branch_labels = None
depends_on = None

TABLE = 'afiliados'
COLUMN = 'actividad_economica'


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN not in columnas:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=7), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN in columnas:
        op.drop_column(TABLE, COLUMN)
