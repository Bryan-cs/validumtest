"""add seguimiento_arl table

Revision ID: b7e3f1a9c2d8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = 'b7e3f1a9c2d8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Inspect the current DB state so we can skip DDL that already exists.
    # This handles the case where create_all() already created the table in
    # a previous deploy, which would otherwise raise a duplicate-type error
    # on PostgreSQL (pg_type_typname_nsp_index constraint violation).
    bind = op.get_bind()
    insp = Inspector.from_engine(bind)
    existing_tables = insp.get_table_names()

    if 'seguimiento_arl' not in existing_tables:
        op.create_table(
            'seguimiento_arl',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('nombre', sa.String(120), nullable=False),
            sa.Column('documento', sa.String(30), nullable=False),
            sa.Column('cliente', sa.String(150), nullable=True),
            sa.Column('empresa', sa.String(120), nullable=True),
            sa.Column('fecha_afiliacion', sa.String(20), nullable=True),
            sa.Column('nivel_arl', sa.String(10), nullable=True, server_default='N/A'),
            sa.Column('observaciones', sa.Text(), nullable=True),
            sa.Column('estado', sa.String(20), nullable=True, server_default='activo'),
            sa.Column('creado_en', sa.DateTime(), nullable=True),
        )

    # Create indexes — use IF NOT EXISTS so this is always safe to run,
    # regardless of whether the table was just created or already existed.
    try:
        op.create_index(
            'ix_seguimiento_arl_cliente',
            'seguimiento_arl',
            ['cliente'],
            unique=False,
            if_not_exists=True,
        )
    except Exception:
        pass

    try:
        op.create_index(
            'ix_seg_arl_cliente_estado',
            'seguimiento_arl',
            ['cliente', 'estado'],
            unique=False,
            if_not_exists=True,
        )
    except Exception:
        pass

    try:
        op.create_index(
            'ix_seguimiento_arl_id',
            'seguimiento_arl',
            ['id'],
            unique=False,
            if_not_exists=True,
        )
    except Exception:
        pass


def downgrade():
    try:
        op.drop_index('ix_seg_arl_cliente_estado', table_name='seguimiento_arl')
    except Exception:
        pass
    try:
        op.drop_index('ix_seguimiento_arl_cliente', table_name='seguimiento_arl')
    except Exception:
        pass
    try:
        op.drop_index('ix_seguimiento_arl_id', table_name='seguimiento_arl')
    except Exception:
        pass
    op.drop_table('seguimiento_arl')
