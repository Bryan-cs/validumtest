"""add ultima_alerta_en to seguimiento_arl

Revision ID: p1q2r3s4t5u6
Revises: l7m8n9o0p1q2
Create Date: 2026-05-22

Campo ultima_alerta_en registra cuándo se envió la última alerta automática
por inactividad en SeguimientoARL. NULL = nunca alertado.
"""
from alembic import op
import sqlalchemy as sa

revision = 'p1q2r3s4t5u6'
down_revision = 'l7m8n9o0p1q2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seguimiento_arl") as batch_op:
        batch_op.add_column(
            sa.Column('ultima_alerta_en', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("seguimiento_arl") as batch_op:
        batch_op.drop_column('ultima_alerta_en')
