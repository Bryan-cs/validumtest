"""add unique index to empleados.doc

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-05-03

Previene registro duplicado de documentos de empleados.
ADVERTENCIA INFRA2-B3: si existen empleados con el mismo número de documento
en prod, esta migración fallará con un error de unicidad.
Verificar antes: SELECT doc, COUNT(*) FROM empleados WHERE doc IS NOT NULL
AND doc != '' GROUP BY doc HAVING COUNT(*) > 1;
"""
from alembic import op
import sqlalchemy as sa


revision = 'i4j5k6l7m8n9'
down_revision = 'h3i4j5k6l7m8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("empleados") as batch_op:
        batch_op.create_index('ix_empleados_doc', ['doc'])
        batch_op.create_unique_constraint('uq_empleado_doc', ['doc'])


def downgrade():
    with op.batch_alter_table("empleados") as batch_op:
        batch_op.drop_constraint('uq_empleado_doc', type_='unique')
        batch_op.drop_index('ix_empleados_doc')
