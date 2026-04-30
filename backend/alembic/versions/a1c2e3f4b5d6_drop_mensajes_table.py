"""drop mensajes table — modelo huérfano, 0 filas, 0 endpoints, 0 frontend

Revision ID: a1c2e3f4b5d6
Revises: 9a8b7c6d5e4f
Create Date: 2026-04-30

Motivo: tabla mensajes nunca tuvo uso real. 0 filas en producción,
ningún router la referencia, ningún frontend la consume. 7 índices
desperdiciados (136 kB). La funcionalidad de comunicación está
cubierta por avisos_clientes + notificaciones.
"""
from alembic import op

revision = 'a1c2e3f4b5d6'
down_revision = '9a8b7c6d5e4f'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('mensajes')


def downgrade():
    import sqlalchemy as sa
    op.create_table(
        'mensajes',
        sa.Column('id',               sa.Integer(),     nullable=False),
        sa.Column('tipo',             sa.String(10),    nullable=True),
        sa.Column('remitente',        sa.String(60),    nullable=True),
        sa.Column('remitente_nombre', sa.String(120),   nullable=True),
        sa.Column('destinatario',     sa.String(120),   nullable=True),
        sa.Column('texto',            sa.Text(),        nullable=True),
        sa.Column('creado',           sa.DateTime(),    nullable=True),
        sa.Column('leido',            sa.Boolean(),     nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
