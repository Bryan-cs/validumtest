"""fix token_blacklist timezone and access token duration

Revision ID: c9f4a2b8d1e7
Revises: b7e3f1a9c2d8
Create Date: 2026-04-15

Cambia expires_at y creado en token_blacklist de TIMESTAMP a TIMESTAMPTZ
para evitar bugs de comparación con datetime timezone-aware en PostgreSQL.
En SQLite esto no tiene efecto (siempre text), pero en PostgreSQL resuelve
la discrepancia entre datetime.now(timezone.utc) y TIMESTAMP WITHOUT TIME ZONE.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9f4a2b8d1e7'
down_revision = 'b7e3f1a9c2d8'
branch_labels = None
depends_on = None


def upgrade():
    # En PostgreSQL: convierte TIMESTAMP → TIMESTAMPTZ
    # En SQLite: no hace nada (dialect no soporta ALTER COLUMN, se ignora)
    with op.batch_alter_table("token_blacklist") as batch_op:
        batch_op.alter_column(
            "expires_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("token_blacklist") as batch_op:
        batch_op.alter_column(
            "expires_at",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
