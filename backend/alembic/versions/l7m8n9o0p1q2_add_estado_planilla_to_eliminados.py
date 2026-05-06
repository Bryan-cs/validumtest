"""add_estado_planilla_to_eliminados

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-05-06

Agrega columna estado_planilla (nullable String(30)) a la tabla eliminados.
Valores esperados: retiro_pendiente | planilla_hecha | planilla_pagada
"""
from alembic import op
import sqlalchemy as sa

revision = 'l7m8n9o0p1q2'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("eliminados") as batch_op:
        batch_op.add_column(
            sa.Column('estado_planilla', sa.String(30), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("eliminados") as batch_op:
        batch_op.drop_column('estado_planilla')
