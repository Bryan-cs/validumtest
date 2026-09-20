"""la planilla PILA pasa a ser por afiliado, no por empresa

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-09-20

La primera version liquidaba una planilla por aportante con todos sus
cotizantes dentro, que es el caso de una empresa pagando su nomina. El negocio
funciona al reves: cada afiliado paga su propia planilla, con su numero y su
enlace de pago, y se liquida de a uno.

El aportante sigue en la cabecera porque la planilla tipo E lo exige, pero ya
no es la unidad de liquidacion. Por eso `planillas_liquidacion` gana:

- `afiliado_id`: FK a afiliados con ON DELETE SET NULL.
- `afiliado_doc` y `afiliado_nombre`: copia del documento y el nombre, para que
  una planilla siga siendo legible si el afiliado se elimina. Misma razon por
  la que `planillas_detalle` ya guardaba esa copia.

Y un indice por (organizacion, documento, periodo), que es como se consulta:
"la planilla de esta persona en este mes".

Las planillas que existan de antes quedan con `afiliado_id` en NULL. No se
migran: eran de prueba y su contenido —varios cotizantes en una sola planilla—
ya no corresponde al modelo.

Idempotente: introspecciona antes de agregar columnas e indices.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'w7x8y9z0a1b2'
down_revision = 'v6w7x8y9z0a1'
branch_labels = None
depends_on = None


TABLA = 'planillas_liquidacion'

COLUMNAS = [
    ('afiliado_id',     sa.Integer()),
    ('afiliado_doc',    sa.String(length=20)),
    ('afiliado_nombre', sa.String(length=150)),
]

INDICES = [
    ('ix_planillas_liquidacion_afiliado_id',  ['afiliado_id']),
    ('ix_planillas_liquidacion_afiliado_doc', ['afiliado_doc']),
    ('ix_liq_org_afiliado_periodo', ['organizacion_id', 'afiliado_doc', 'periodo_cotizacion']),
]

FK = 'fk_planillas_liquidacion_afiliado'


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLA not in inspector.get_table_names():
        return

    existentes = {c['name'] for c in inspector.get_columns(TABLA)}
    for nombre, tipo in COLUMNAS:
        if nombre not in existentes:
            op.add_column(TABLA, sa.Column(nombre, tipo, nullable=True))

    inspector = inspect(bind)
    indices = {ix['name'] for ix in inspector.get_indexes(TABLA)}
    for nombre, cols in INDICES:
        if nombre not in indices:
            op.create_index(nombre, TABLA, cols)

    # SQLite no admite agregar una FK a una tabla existente sin recrearla; en
    # dev la integridad la cubre el ORM y en Postgres si se crea.
    if bind.dialect.name != 'sqlite':
        fks = {fk.get('name') for fk in inspect(bind).get_foreign_keys(TABLA)}
        if FK not in fks:
            op.create_foreign_key(FK, TABLA, 'afiliados',
                                  ['afiliado_id'], ['id'], ondelete='SET NULL')


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLA not in inspector.get_table_names():
        return

    if bind.dialect.name != 'sqlite':
        fks = {fk.get('name') for fk in inspector.get_foreign_keys(TABLA)}
        if FK in fks:
            op.drop_constraint(FK, TABLA, type_='foreignkey')

    indices = {ix['name'] for ix in inspector.get_indexes(TABLA)}
    for nombre, _ in INDICES:
        if nombre in indices:
            op.drop_index(nombre, table_name=TABLA)

    existentes = {c['name'] for c in inspector.get_columns(TABLA)}
    for nombre, _ in COLUMNAS:
        if nombre in existentes:
            op.drop_column(TABLA, nombre)
