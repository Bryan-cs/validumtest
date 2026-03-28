"""add composite indexes for facturas

Revision ID: 12fdddca51c6
Revises: e32a093a2292
Create Date: 2026-03-26 20:56:27.425475

"""
from alembic import op
import sqlalchemy as sa


revision = '12fdddca51c6'
down_revision = 'e32a093a2292'
branch_labels = None
depends_on = None


def upgrade():
    # Índices compuestos para queries frecuentes
    # if_not_exists para DBs donde create_all ya los creó
    op.create_index('ix_factura_anio_mes', 'facturas', ['anio', 'mes'], unique=False, if_not_exists=True)
    op.create_index('ix_factura_cliente_estado', 'facturas', ['cliente', 'estado'], unique=False, if_not_exists=True)
    # UNIQUE constraint y retiros index ya aplicados en migración anterior
    try:
        op.create_unique_constraint('uq_factura_doc_mes_anio', 'facturas', ['doc', 'mes', 'anio'])
    except Exception:
        pass
    try:
        op.drop_index(op.f('ix_retiros_doc'), table_name='retiros')
        op.create_index(op.f('ix_retiros_doc'), 'retiros', ['doc'], unique=True)
    except Exception:
        pass


def downgrade():
    op.drop_index(op.f('ix_retiros_doc'), table_name='retiros')
    op.create_index(op.f('ix_retiros_doc'), 'retiros', ['doc'], unique=False)
    op.drop_constraint('uq_factura_doc_mes_anio', 'facturas', type_='unique')
    op.drop_index('ix_factura_cliente_estado', table_name='facturas')
    op.drop_index('ix_factura_anio_mes', table_name='facturas')
