"""add fecha_expedicion to afiliados

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-09-19

RUAF exige la fecha de expedicion del documento para consultar las afiliaciones
(ADRES no la pide). Se guarda en el afiliado para no volver a preguntarla en
cada consulta.

Formato dd/mm/aaaa, el mismo que espera el datepicker de RUAF. Nullable: los
afiliados ya cargados no la tienen y se completa cuando haga falta.

Va despues de la migracion PILA (u5v6w7x8y9z0), que tambien agrega columnas
a `afiliados` pero ninguna se llama igual.

Idempotente: si la columna ya existe (porque _ensure_columns corrio antes que
Alembic), se omite y la revision queda registrada sin error.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'v6w7x8y9z0a1'
down_revision = 'u5v6w7x8y9z0'
branch_labels = None
depends_on = None

TABLE = 'afiliados'
COLUMN = 'fecha_expedicion'


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN not in columnas:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=10), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    columnas = {c['name'] for c in inspector.get_columns(TABLE)}
    if COLUMN in columnas:
        op.drop_column(TABLE, COLUMN)
