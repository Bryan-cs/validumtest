"""fix retiro.doc remove unique and factura.pagado_en add timezone

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-05-03

Fix 1: Retiro.doc tenía unique=True — bloqueaba re-retiro del mismo afiliado.
Fix 2: Factura.pagado_en sin timezone=True — inconsistente con PostgreSQL TIMESTAMPTZ.

NOTA: batch_alter_table en PostgreSQL emite DDL directo; try/except dentro del
bloque no atrapa errores de DROP CONSTRAINT. Solución: DO block que encuentra y
elimina dinámicamente cualquier constraint/índice unique en retiros.doc sin
asumir nombre específico (varía según creación via create_all vs migración).
"""
from alembic import op
import sqlalchemy as sa

revision = 'j5k6l7m8n9o0'
down_revision = 'i4j5k6l7m8n9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        # DO block: elimina cualquier unique constraint/índice en retiros.doc
        # sin asumir el nombre exacto (que varía según cómo se creó la tabla).
        op.execute(sa.text("""
            DO $$
            DECLARE
                v_con RECORD;
                v_idx RECORD;
            BEGIN
                -- 1. Drop any named unique constraint on retiros.doc
                FOR v_con IN
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_attribute att
                        ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
                    WHERE rel.relname = 'retiros'
                      AND att.attname = 'doc'
                      AND con.contype = 'u'
                LOOP
                    EXECUTE 'ALTER TABLE retiros DROP CONSTRAINT '
                            || quote_ident(v_con.conname);
                END LOOP;

                -- 2. Drop any unique index on retiros.doc (uniqueness via index)
                FOR v_idx IN
                    SELECT c.relname AS idxname
                    FROM pg_index i
                    JOIN pg_class c ON c.oid = i.indexrelid
                    JOIN pg_class t ON t.oid = i.indrelid
                    JOIN pg_attribute a
                        ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey)
                    WHERE t.relname = 'retiros'
                      AND a.attname = 'doc'
                      AND i.indisunique = true
                      AND NOT i.indisprimary
                LOOP
                    EXECUTE 'DROP INDEX IF EXISTS ' || quote_ident(v_idx.idxname);
                END LOOP;

                -- 3. Recrear como índice no-unique si no existe
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'retiros' AND indexname = 'ix_retiros_doc'
                ) THEN
                    CREATE INDEX ix_retiros_doc ON retiros(doc);
                END IF;
            END $$;
        """))
    else:
        # SQLite: batch_alter_table usa recreación de tabla
        with op.batch_alter_table("retiros") as batch_op:
            try:
                batch_op.drop_constraint('retiros_doc_key', type_='unique')
            except Exception:
                pass

    # Fix 2: pagado_en → TIMESTAMPTZ
    with op.batch_alter_table("facturas") as batch_op:
        batch_op.alter_column(
            'pagado_en',
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("facturas") as batch_op:
        batch_op.alter_column(
            'pagado_en',
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS retiros_doc_key ON retiros(doc)"
        ))
    else:
        with op.batch_alter_table("retiros") as batch_op:
            batch_op.create_unique_constraint('retiros_doc_key', ['doc'])
