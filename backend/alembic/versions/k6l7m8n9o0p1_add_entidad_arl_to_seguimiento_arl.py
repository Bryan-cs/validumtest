"""add entidad_arl to seguimiento_arl

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-05-04

Nueva columna entidad_arl (SURA | POSITIVA) en seguimiento_arl.
Default 'SURA' para filas existentes.
"""
from alembic import op
import sqlalchemy as sa

revision = 'k6l7m8n9o0p1'
down_revision = 'j5k6l7m8n9o0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seguimiento_arl") as batch_op:
        batch_op.add_column(
            sa.Column('entidad_arl', sa.String(20), nullable=True, server_default='SURA')
        )


def downgrade():
    with op.batch_alter_table("seguimiento_arl") as batch_op:
        batch_op.drop_column('entidad_arl')
