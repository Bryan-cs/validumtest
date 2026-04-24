"""chore: drop obs column from afiliados — never had UI or data in production

Revision ID: b2c3d4e5f6a7
Revises: a9b1c2d3e4f5
Create Date: 2026-04-24

La columna obs de afiliados nunca tuvo interfaz ni datos reales.
Se reemplaza con novedades y detalle para anotaciones.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a9b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('afiliados', 'obs')


def downgrade():
    op.add_column('afiliados',
        sa.Column('obs', sa.Text(), nullable=True)
    )
