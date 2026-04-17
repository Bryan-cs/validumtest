"""add upload_id to documentos

Revision ID: d4e5f6a7b8c9
Revises: c9f4a2b8d1e7
Create Date: 2026-04-16

Añade columna upload_id (UUID idempotency key) a la tabla documentos.
Permite que reintentos de subida detecten un upload ya completado y retornen
el registro existente en vez de crear un duplicado.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c9f4a2b8d1e7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documentos', sa.Column('upload_id', sa.String(36), nullable=True))
    op.create_index('ix_documentos_upload_id', 'documentos', ['upload_id'], unique=True)


def downgrade():
    op.drop_index('ix_documentos_upload_id', table_name='documentos')
    op.drop_column('documentos', 'upload_id')
