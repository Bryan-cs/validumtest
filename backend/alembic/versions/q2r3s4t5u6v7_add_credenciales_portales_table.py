"""add credenciales_portales table

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-05-28

Tabla CredencialPortal almacena credenciales de portales externos
(EPS, CCF, Aportes en Línea, Pago Simple, Asopagos). La clave_portal
se guarda cifrada con Fernet (AES-128) — la clave de cifrado se deriva
de SECRET_KEY. NO rotar SECRET_KEY sin re-cifrar primero esta tabla.
"""
from alembic import op
import sqlalchemy as sa


revision = 'q2r3s4t5u6v7'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'credenciales_portales',
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
    op.create_index('ix_credenciales_portales_id', 'credenciales_portales', ['id'])
    op.create_index('ix_cred_portal_tipo', 'credenciales_portales', ['portal'])
    op.create_index('ix_cred_doc', 'credenciales_portales', ['numero_doc'])


def downgrade():
    op.drop_index('ix_cred_doc', table_name='credenciales_portales')
    op.drop_index('ix_cred_portal_tipo', table_name='credenciales_portales')
    op.drop_index('ix_credenciales_portales_id', table_name='credenciales_portales')
    op.drop_table('credenciales_portales')
