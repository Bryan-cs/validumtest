"""fix naive DateTime columns to TIMESTAMPTZ

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-06-20

Convierte 17 columnas DateTime naive (TIMESTAMP WITHOUT TIME ZONE) a
TIMESTAMPTZ en 15 tablas. Los valores existentes se interpretan como UTC
(correcto: _utcnow() siempre guardó UTC). Idempotente: salta columnas
que ya son TIMESTAMPTZ.
"""
from alembic import op
import sqlalchemy as sa

revision = 's3t4u5v6w7x8'
down_revision = 'r2s3t4u5v6w7'
branch_labels = None
depends_on = None

# (tabla, columna, nullable)
COLUMNS = [
    ('usuarios',              'creado',      False),
    ('afiliados',             'creado',      False),
    ('afiliados',             'actualizado', False),
    ('facturas',              'creado',      False),
    ('facturas',              'actualizado', False),
    ('retiros',               'creado',      False),
    ('eliminados',            'creado',      False),
    ('empleados',             'creado',      False),
    ('gastos',                'creado',      False),
    ('ingresos_adicionales',  'creado',      False),
    ('solicitudes_novedad',   'creado',      False),
    ('novedades_pago',        'creado',      False),
    ('solicitudes_retiro',    'creado',      False),
    ('planillas_pago',        'creado',      False),
    ('documentos',            'creado',      False),
    ('avisos_clientes',       'creado',      False),
    ('seguimiento_arl',       'creado_en',   False),
]


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    for table_name, col_name, nullable in COLUMNS:
        if table_name not in existing_tables:
            continue

        cols = {c['name']: c for c in insp.get_columns(table_name)}
        if col_name not in cols:
            continue

        # Skip if already timezone-aware (idempotente en PostgreSQL)
        if getattr(cols[col_name]['type'], 'timezone', False):
            continue

        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                col_name,
                type_=sa.DateTime(timezone=True),
                existing_type=sa.DateTime(),
                existing_nullable=nullable,
            )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    for table_name, col_name, nullable in COLUMNS:
        if table_name not in existing_tables:
            continue

        cols = {c['name']: c for c in insp.get_columns(table_name)}
        if col_name not in cols:
            continue

        if not getattr(cols[col_name]['type'], 'timezone', False):
            continue

        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                col_name,
                type_=sa.DateTime(),
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=nullable,
            )
