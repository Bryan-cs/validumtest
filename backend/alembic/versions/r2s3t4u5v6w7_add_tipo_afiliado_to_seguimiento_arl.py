"""add tipo_afiliado to seguimiento_arl

Revision ID: r2s3t4u5v6w7
Revises: q2r3s4t5u6v7
Create Date: 2026-06-16

Campo tipo_afiliado distingue si el afiliado en seguimiento ARL es
dependiente (vinculado a empresa) o independiente. Default 'dependiente'.
Idempotente: solo agrega la columna si no existe (safety net de primer deploy).
"""
from alembic import op
import sqlalchemy as sa

revision = 'r2s3t4u5v6w7'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


def upgrade():
    cols = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('seguimiento_arl')]
    if 'tipo_afiliado' not in cols:
        with op.batch_alter_table("seguimiento_arl") as batch_op:
            batch_op.add_column(
                sa.Column('tipo_afiliado', sa.String(length=15),
                          nullable=True, server_default='dependiente')
            )


def downgrade():
    cols = [c['name'] for c in sa.inspect(op.get_bind()).get_columns('seguimiento_arl')]
    if 'tipo_afiliado' in cols:
        with op.batch_alter_table("seguimiento_arl") as batch_op:
            batch_op.drop_column('tipo_afiliado')
