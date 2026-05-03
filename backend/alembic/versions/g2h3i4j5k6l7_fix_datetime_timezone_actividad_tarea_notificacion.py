"""fix datetime timezone actividad tarea notificacion

Revision ID: g2h3i4j5k6l7
Revises: a1c2e3f4b5d6
Create Date: 2026-05-02

Cambia fecha/creado en actividad, tareas, tarea_comentarios y notificaciones
de TIMESTAMP a TIMESTAMPTZ — igual que fix_token_blacklist_timezone (c9f4a2b8d1e7).
Evita discrepancia con datetime.now(timezone.utc) aware en scheduler y queries.
"""
from alembic import op
import sqlalchemy as sa


revision = 'g2h3i4j5k6l7'
down_revision = 'a1c2e3f4b5d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("actividad") as batch_op:
        batch_op.alter_column(
            "fecha",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table("tareas") as batch_op:
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "completado_en",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "finalizado_en",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table("tarea_comentarios") as batch_op:
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table("notificaciones") as batch_op:
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("actividad") as batch_op:
        batch_op.alter_column(
            "fecha",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    with op.batch_alter_table("tareas") as batch_op:
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "completado_en",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "finalizado_en",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    with op.batch_alter_table("tarea_comentarios") as batch_op:
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    with op.batch_alter_table("notificaciones") as batch_op:
        batch_op.alter_column(
            "creado",
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
