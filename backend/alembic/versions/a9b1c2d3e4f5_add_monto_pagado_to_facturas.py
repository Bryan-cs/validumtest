"""feat: add monto_pagado to facturas for partial payments

Revision ID: a9b1c2d3e4f5
Revises: f1a2b3c4d5e6
Create Date: 2026-04-23

Permite registrar abonos parciales en facturas.
Estado 'parcial' = factura con abono(s) pero aún sin completar.
monto_pagado acumula los abonos; al igualar ingresos → estado 'pagado'.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a9b1c2d3e4f5'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('facturas',
        sa.Column('monto_pagado', sa.Numeric(15, 2), nullable=True, server_default='0')
    )


def downgrade():
    op.drop_column('facturas', 'monto_pagado')
