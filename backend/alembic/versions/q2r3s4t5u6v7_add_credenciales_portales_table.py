"""add credenciales_portales table

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-05-28

Tabla CredencialPortal almacena credenciales de portales externos
(EPS, CCF, Aportes en Línea, Pago Simple, Asopagos). La clave_portal
se guarda cifrada con Fernet (AES-128). Desde sesión 58 la clave
de cifrado se lee de FERNET_KEY (independiente de SECRET_KEY), con
fallback a SECRET_KEY para retrocompatibilidad.

Idempotente: si la tabla o sus índices ya existen (porque
Base.metadata.create_all corrió antes que Alembic en el primer
deploy), se omiten esos pasos y la revisión queda registrada
en alembic_version sin error.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'q2r3s4t5u6v7'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None


TABLE = 'credenciales_portales'
INDEXES = [
    ('ix_credenciales_portales_id', ['id']),
    ('ix_cred_portal_tipo',         ['portal']),
    ('ix_cred_doc',                 ['numero_doc']),
]


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    if TABLE not in inspector.get_table_names():
        op.create_table(
            TABLE,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tipo_doc', sa.String(length=10), nullable=True),
            sa.Column('numero_doc', sa.String(length=40), nullable=False),
            sa.Column('titular', sa.String(length=150), nullable=True),
            sa.Column('portal', sa.String(length=40), nullable=False),
            sa.Column('entidad', sa.String(length=100), nullable=True),
            sa.Column('usuario_portal', sa.String(length=150), nullable=False),
            sa.Column('clave_portal', sa.Text(), nullable=False),
            sa.Column('obs', sa.Text(), nullable=True),
            sa.Column('creado_por', sa.String(length=60), nullable=True),
            sa.Column('creado', sa.DateTime(timezone=True), nullable=True),
            sa.Column('actualizado', sa.DateTime(timezone=True), nullable=True),
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
