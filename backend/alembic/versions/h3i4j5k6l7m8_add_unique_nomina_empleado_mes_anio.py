"""add unique constraint to nomina_mensual (empleado_id, mes, anio)

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-05-03

Previene duplicados de nómina para el mismo empleado en el mismo período.
ADVERTENCIA INFRA2-B2: si existen filas duplicadas en prod para la misma
combinación (empleado_id, mes, anio) esta migración fallará.
Verificar antes: SELECT empleado_id, mes, anio, COUNT(*) FROM nomina_mensual
GROUP BY empleado_id, mes, anio HAVING COUNT(*) > 1;
"""
from alembic import op
import sqlalchemy as sa


revision = 'h3i4j5k6l7m8'
down_revision = 'g2h3i4j5k6l7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("nomina_mensual") as batch_op:
        batch_op.create_unique_constraint(
            'uq_nomina_emp_mes_anio',
            ['empleado_id', 'mes', 'anio']
        )


def downgrade():
    with op.batch_alter_table("nomina_mensual") as batch_op:
        batch_op.drop_constraint('uq_nomina_emp_mes_anio', type_='unique')
