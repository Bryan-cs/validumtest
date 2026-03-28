"""add ciudad, privada, documentos table

Revision ID: a1b2c3d4e5f6
Revises: 12fdddca51c6
Create Date: 2026-03-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '12fdddca51c6'
branch_labels = None
depends_on = None


def upgrade():
    # Add ciudad column to afiliados
    op.add_column('afiliados', sa.Column('ciudad', sa.String(100), nullable=True))

    # Add privada column to tareas
    op.add_column('tareas', sa.Column('privada', sa.Boolean(), nullable=True, server_default='0'))

    # Create documentos table
    op.create_table(
        'documentos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('afiliado_doc', sa.String(20), nullable=True, index=True),
        sa.Column('nombre', sa.String(200), nullable=True),
        sa.Column('tipo', sa.String(20), nullable=True),
        sa.Column('ruta', sa.String(500), nullable=True),
        sa.Column('tamano', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('subido_por', sa.String(60), nullable=True),
        sa.Column('contexto', sa.String(60), nullable=True, server_default='afiliado'),
        sa.Column('contexto_id', sa.Integer(), nullable=True),
        sa.Column('creado', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('documentos')
    op.drop_column('tareas', 'privada')
    op.drop_column('afiliados', 'ciudad')
