"""perf: Numeric types for financial fields + partial indexes for cobro

Revision ID: f1a2b3c4d5e6
Revises: c804bec2074b
Create Date: 2026-04-23

Cambios:
1. Float → NUMERIC(15,2) en campos financieros (Afiliado.ibc, Factura.*, Gasto.valor,
   IngresoAdicional.valor, NominaMensual.valor, Empleado.nomina, Config.ibc_global/cargo_adicional)
2. Índice parcial ix_afiliado_cobro_cobertura (activo=TRUE) para Index-Only Scans en get_cobro
3. Índice parcial ix_factura_pendiente en facturas (estado='pendiente')
4. Índice ix_actividad_fecha_desc para paginación de actividad
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'c804bec2074b'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Índices parciales (no requieren downtime, se crean CONCURRENTLY en prod) ──
    # Nota: CREATE INDEX IF NOT EXISTS no soporta CONCURRENTLY — usar try/except en app
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_afiliado_cobro_cobertura
        ON afiliados (activo, estado_srv, empresa, cliente_txt)
        WHERE activo = TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_factura_pendiente
        ON facturas (anio, mes, cliente)
        WHERE estado = 'pendiente'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_actividad_fecha_desc
        ON actividad (fecha DESC)
        """
    )

    # ── 2. Float → NUMERIC(15,2) en campos financieros ──
    # PostgreSQL: ALTER COLUMN TYPE requiere USING para la conversión
    financial_alterations = [
        ("afiliados",          "ibc"),
        ("facturas",           "ingresos"),
        ("facturas",           "costos"),
        ("facturas",           "costo_adm"),
        ("facturas",           "conceptos_extra"),
        ("facturas",           "utilidad"),
        ("gastos",             "valor"),
        ("ingresos_adicionales","valor"),
        ("nomina_mensual",     "valor"),
        ("empleados",          "nomina"),
        ("config",             "ibc_global"),
        ("config",             "cargo_adicional"),
    ]
    for table, col in financial_alterations:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{col}" '
            f'TYPE NUMERIC(15,2) USING "{col}"::NUMERIC(15,2)'
        )


def downgrade():
    # Revertir índices
    op.execute('DROP INDEX IF EXISTS ix_afiliado_cobro_cobertura')
    op.execute('DROP INDEX IF EXISTS ix_factura_pendiente')
    op.execute('DROP INDEX IF EXISTS ix_actividad_fecha_desc')

    # Revertir NUMERIC → FLOAT
    financial_alterations = [
        ("afiliados",          "ibc"),
        ("facturas",           "ingresos"),
        ("facturas",           "costos"),
        ("facturas",           "costo_adm"),
        ("facturas",           "conceptos_extra"),
        ("facturas",           "utilidad"),
        ("gastos",             "valor"),
        ("ingresos_adicionales","valor"),
        ("nomina_mensual",     "valor"),
        ("empleados",          "nomina"),
        ("config",             "ibc_global"),
        ("config",             "cargo_adicional"),
    ]
    for table, col in financial_alterations:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{col}" '
            f'TYPE FLOAT USING "{col}"::FLOAT'
        )
