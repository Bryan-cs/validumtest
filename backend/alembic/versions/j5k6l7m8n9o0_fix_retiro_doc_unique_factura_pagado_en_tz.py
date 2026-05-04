"""fix retiro.doc remove unique and factura.pagado_en add timezone

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-05-03

Fix 1: Retiro.doc tenía unique=True — bloqueaba re-retiro del mismo afiliado.
Fix 2: Factura.pagado_en sin timezone=True — inconsistente con PostgreSQL TIMESTAMPTZ.
"""
from alembic import op
import sqlalchemy as sa

revision = 'j5k6l7m8n9o0'
down_revision = 'i4j5k6l7m8n9'
branch_labels = None
depends_on = None


def upgrade():
    # Fix 1: remover unique constraint de retiros.doc
    with op.batch_alter_table("retiros") as batch_op:
        try:
            batch_op.drop_constraint('retiros_doc_key', type_='unique')
        except Exception:
            pass  # SQLite no tiene named constraints

    # Fix 2: cambiar pagado_en a TIMESTAMPTZ
    with op.batch_alter_table("facturas") as batch_op:
        batch_op.alter_column(
            'pagado_en',
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("facturas") as batch_op:
        batch_op.alter_column(
            'pagado_en',
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    with op.batch_alter_table("retiros") as batch_op:
        batch_op.create_unique_constraint('retiros_doc_key', ['doc'])
