"""add consultas_externas table (multi-tenant)

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-09-19

Tabla ConsultaExterna: registro de cada consulta a una fuente oficial de
seguridad social (ADRES/BDUA, RUAF). Hace de cache (valido_hasta evita
repetir el captcha por 30 dias), de auditoria (quien consulto la afiliacion
en salud de quien — dato sensible bajo Ley 1581/2012) y de diagnostico
(los fallos guardan su motivo, para detectar cuando la fuente cambia).

Multi-tenant: `organizacion_id` NOT NULL con FK ON DELETE CASCADE, igual que
el resto de tablas tenant. El modelo entra en el auto-filtro de tenant.py, asi
que el cache queda acotado por organizacion: ninguna organizacion ve a quien
consulto otra ni reutiliza su resultado.

Idempotente: si la tabla o sus indices ya existen (porque
Base.metadata.create_all corrio antes que Alembic en el primer deploy),
se omiten esos pasos y la revision queda registrada en alembic_version
sin error. Mismo patron que q2r3s4t5u6v7.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 't4u5v6w7x8y9'
down_revision = 's3t4u5v6w7x8'
branch_labels = None
depends_on = None


TABLE = 'consultas_externas'
INDEXES = [
    ('ix_consultas_externas_id',              ['id']),
    ('ix_consultas_externas_organizacion_id', ['organizacion_id']),
    ('ix_consultas_externas_fuente',          ['fuente']),
    ('ix_consultas_externas_doc',             ['doc']),
    ('ix_consultas_externas_exito',           ['exito']),
    ('ix_consultas_externas_usuario',         ['usuario']),
    ('ix_consulta_org_fuente_doc',            ['organizacion_id', 'fuente', 'doc']),
]


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('organizacion_id', sa.Integer(), nullable=False),
            sa.Column('fuente', sa.String(length=20), nullable=False),
            sa.Column('tipo_doc', sa.String(length=10), nullable=True),
            sa.Column('doc', sa.String(length=20), nullable=False),
            sa.Column('exito', sa.Boolean(), nullable=True),
            sa.Column('nombre', sa.String(length=150), nullable=True),
            sa.Column('eps', sa.String(length=120), nullable=True),
            sa.Column('regimen', sa.String(length=60), nullable=True),
            sa.Column('estado_afil', sa.String(length=60), nullable=True),
            sa.Column('tipo_afiliado', sa.String(length=60), nullable=True),
            sa.Column('respuesta', sa.Text(), nullable=True),
            sa.Column('error_detalle', sa.Text(), nullable=True),
            sa.Column('usuario', sa.String(length=60), nullable=True),
            sa.Column('creado', sa.DateTime(timezone=True), nullable=True),
            sa.Column('valido_hasta', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['organizacion_id'], ['organizaciones.id'],
                                    ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )

    # Re-introspect — la tabla puede haberse creado arriba o pre-existir.
    inspector = inspect(bind)
    existing_indexes = {ix['name'] for ix in inspector.get_indexes(TABLE)}
    for name, cols in INDEXES:
        if name not in existing_indexes:
            op.create_index(name, TABLE, cols)


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE in inspector.get_table_names():
        existing_indexes = {ix['name'] for ix in inspector.get_indexes(TABLE)}
        for name, _ in INDEXES:
            if name in existing_indexes:
                op.drop_index(name, table_name=TABLE)
        op.drop_table(TABLE)
