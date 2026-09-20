"""add PILA tables and afiliado PILA fields (multi-tenant)

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-09-19

Base de datos para liquidar planillas PILA dentro del sistema, en vez de
guardar solo los archivos que alguien sube a mano (eso seguira haciendolo
`planillas_pago`, que no se toca).

Estructura tomada del Anexo Tecnico 2 de la Resolucion 2388 de 2016, version 30
del 24-07-2026 (modificada por la Resolucion 1529 de 2026, que agrego el tipo
de aportante 17, los tipos de cotizante 74/75/76 y la planilla W).

Cuatro tablas:

- `pila_codigos`: catalogo normativo (EPS, AFP, CCF, ARL, tipos de cotizante,
  departamentos, municipios). Global, SIN organizacion_id: lo define la norma,
  no el cliente. Queda fuera del auto-filtro de tenant.py.
- `aportantes_pila`: la empresa aportante con NIT, digito de verificacion, tipo
  y clase de aportante, codigo ARL y sucursal. Hoy el aportante es texto libre
  en `afiliados.empresa` / `afiliados.cliente_txt`, y de un string no sale un
  encabezado valido. `cliente_ref` es el puente con esos datos.
- `planillas_liquidacion`: cabecera por periodo + aportante + tipo de planilla.
- `planillas_detalle`: un registro tipo 2 por cotizante, congelado. Guarda copia
  del nombre, documento y administradoras para que una planilla ya liquidada
  siga mostrando lo que se reporto, aunque el afiliado cambie despues.

Y las columnas PILA en `afiliados`: nombre partido en cuatro (el registro tipo 2
los exige separados), tipo y subtipo de cotizante, codigos de administradoras
(los campos eps/afp/ccf/arl existentes son texto para mostrar, no sirven para el
archivo), ubicacion laboral DANE y datos de salario. Todas nullable: las filas
ya cargadas no los tienen y se completan por backfill; la liquidacion valida que
esten presentes antes de generar.

Idempotente: introspecciona antes de crear tablas, indices y columnas, por si
`Base.metadata.create_all` corrio antes que Alembic. Mismo patron que
q2r3s4t5u6v7 y t4u5v6w7x8y9.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'u5v6w7x8y9z0'
down_revision = 't4u5v6w7x8y9'
branch_labels = None
depends_on = None


# ── Columnas PILA que se agregan a `afiliados` ───────────────────────────────
AFILIADO_COLS = [
    ('primer_apellido',              sa.String(length=20)),
    ('segundo_apellido',             sa.String(length=30)),
    ('primer_nombre',                sa.String(length=20)),
    ('segundo_nombre',               sa.String(length=30)),
    ('fecha_nacimiento',             sa.String(length=10)),
    ('sexo',                         sa.String(length=1)),
    ('tipo_cotizante',               sa.String(length=2)),
    ('subtipo_cotizante',            sa.String(length=2)),
    ('extranjero_no_pension',        sa.Boolean()),
    ('colombiano_exterior',          sa.Boolean()),
    ('cod_depto_labor',              sa.String(length=2)),
    ('cod_municipio_labor',          sa.String(length=3)),
    ('cod_eps',                      sa.String(length=6)),
    ('cod_afp',                      sa.String(length=6)),
    ('cod_ccf',                      sa.String(length=6)),
    ('cod_arl',                      sa.String(length=6)),
    ('clase_riesgo',                 sa.String(length=1)),
    ('tarifa_arl',                   sa.Numeric(precision=7, scale=5)),
    ('tipo_salario',                 sa.String(length=1)),
    ('salario_basico',               sa.Numeric(precision=15, scale=2)),
    ('centro_trabajo',               sa.String(length=9)),
    ('cotizante_principal_tipo_doc', sa.String(length=2)),
    ('cotizante_principal_doc',      sa.String(length=16)),
    ('horas_laboradas',              sa.Integer()),
]

AFILIADO_INDEXES = [
    ('ix_afiliados_tipo_cotizante', ['tipo_cotizante']),
]

INDEXES = {
    'pila_codigos': [
        ('ix_pila_codigos_id',          ['id']),
        ('ix_pila_codigos_tipo',        ['tipo']),
        ('ix_pila_codigos_codigo',      ['codigo']),
        ('ix_pila_codigos_padre',       ['padre']),
        ('ix_pila_codigos_vigente',     ['vigente']),
        ('ix_pila_codigo_tipo_vigente', ['tipo', 'vigente']),
    ],
    'aportantes_pila': [
        ('ix_aportantes_pila_id',              ['id']),
        ('ix_aportantes_pila_organizacion_id', ['organizacion_id']),
        ('ix_aportantes_pila_cliente_ref',     ['cliente_ref']),
        ('ix_aportantes_pila_num_doc',         ['num_doc']),
        ('ix_aportantes_pila_activo',          ['activo']),
        ('ix_aportante_org_doc',               ['organizacion_id', 'num_doc']),
    ],
    'planillas_liquidacion': [
        ('ix_planillas_liquidacion_id',              ['id']),
        ('ix_planillas_liquidacion_organizacion_id', ['organizacion_id']),
        ('ix_planillas_liquidacion_aportante_id',    ['aportante_id']),
        ('ix_planillas_liquidacion_cliente_ref',     ['cliente_ref']),
        ('ix_planillas_liquidacion_estado',          ['estado']),
        ('ix_planillas_liquidacion_numero_planilla', ['numero_planilla']),
        ('ix_liq_org_aportante_periodo',             ['organizacion_id', 'aportante_id',
                                                      'periodo_cotizacion']),
        ('ix_liq_org_estado',                        ['organizacion_id', 'estado']),
    ],
    'planillas_detalle': [
        ('ix_planillas_detalle_id',              ['id']),
        ('ix_planillas_detalle_organizacion_id', ['organizacion_id']),
        ('ix_planillas_detalle_liquidacion_id',  ['liquidacion_id']),
        ('ix_planillas_detalle_doc',             ['doc']),
        ('ix_detalle_liq_doc',                   ['liquidacion_id', 'doc']),
    ],
}

TABLES = ['pila_codigos', 'aportantes_pila', 'planillas_liquidacion', 'planillas_detalle']


def _crear_pila_codigos():
    op.create_table(
        'pila_codigos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=24), nullable=False),
        sa.Column('codigo', sa.String(length=10), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('padre', sa.String(length=10), nullable=True),
        sa.Column('vigente', sa.Boolean(), nullable=True),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tipo', 'codigo', name='uq_pila_codigo_tipo_codigo'),
    )


def _crear_aportantes_pila():
    op.create_table(
        'aportantes_pila',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organizacion_id', sa.Integer(), nullable=False),
        sa.Column('cliente_ref', sa.String(length=150), nullable=False),
        sa.Column('razon_social', sa.String(length=200), nullable=False),
        sa.Column('tipo_doc', sa.String(length=2), nullable=True),
        sa.Column('num_doc', sa.String(length=16), nullable=False),
        sa.Column('dv', sa.String(length=1), nullable=True),
        sa.Column('tipo_persona', sa.String(length=1), nullable=True),
        sa.Column('tipo_aportante', sa.String(length=2), nullable=True),
        sa.Column('clase_aportante', sa.String(length=1), nullable=True),
        sa.Column('cod_arl', sa.String(length=6), nullable=True),
        sa.Column('clase_riesgo', sa.String(length=1), nullable=True),
        sa.Column('actividad_economica', sa.String(length=7), nullable=True),
        sa.Column('cod_depto', sa.String(length=2), nullable=True),
        sa.Column('cod_municipio', sa.String(length=3), nullable=True),
        sa.Column('cod_sucursal', sa.String(length=10), nullable=True),
        sa.Column('nombre_sucursal', sa.String(length=40), nullable=True),
        sa.Column('exonerado_parafiscales', sa.Boolean(), nullable=True),
        sa.Column('direccion', sa.String(length=200), nullable=True),
        sa.Column('telefono', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=True),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actualizado', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organizacion_id'], ['organizaciones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organizacion_id', 'cliente_ref', name='uq_aportante_org_cliente'),
    )


def _crear_planillas_liquidacion():
    op.create_table(
        'planillas_liquidacion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organizacion_id', sa.Integer(), nullable=False),
        sa.Column('aportante_id', sa.Integer(), nullable=False),
        sa.Column('cliente_ref', sa.String(length=150), nullable=True),
        sa.Column('tipo_planilla', sa.String(length=1), nullable=False),
        sa.Column('periodo_cotizacion', sa.String(length=7), nullable=False),
        sa.Column('periodo_pago', sa.String(length=7), nullable=False),
        sa.Column('fecha_limite_pago', sa.String(length=10), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=True),
        sa.Column('operador', sa.String(length=30), nullable=True),
        sa.Column('numero_planilla', sa.String(length=20), nullable=True),
        sa.Column('planilla_corregida', sa.String(length=20), nullable=True),
        sa.Column('link_pago', sa.Text(), nullable=True),
        sa.Column('respuesta_operador', sa.Text(), nullable=True),
        sa.Column('total_cotizantes', sa.Integer(), nullable=True),
        sa.Column('total_pension', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_salud', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_arl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_ccf', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_sena', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_icbf', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_esap', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_men', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_fsp', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_general', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('archivo_ruta', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('generado_por', sa.String(length=60), nullable=True),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actualizado', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organizacion_id'], ['organizaciones.id'], ondelete='CASCADE'),
        # RESTRICT: borrar un aportante con planillas liquidadas destruiria el
        # historial de lo que se pago. Se desactiva, no se borra.
        sa.ForeignKeyConstraint(['aportante_id'], ['aportantes_pila.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )


def _crear_planillas_detalle():
    op.create_table(
        'planillas_detalle',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organizacion_id', sa.Integer(), nullable=False),
        sa.Column('liquidacion_id', sa.Integer(), nullable=False),
        sa.Column('afiliado_id', sa.Integer(), nullable=True),
        sa.Column('secuencia', sa.Integer(), nullable=True),
        sa.Column('tipo_doc', sa.String(length=2), nullable=True),
        sa.Column('doc', sa.String(length=16), nullable=True),
        sa.Column('primer_apellido', sa.String(length=20), nullable=True),
        sa.Column('segundo_apellido', sa.String(length=30), nullable=True),
        sa.Column('primer_nombre', sa.String(length=20), nullable=True),
        sa.Column('segundo_nombre', sa.String(length=30), nullable=True),
        sa.Column('tipo_cotizante', sa.String(length=2), nullable=True),
        sa.Column('subtipo_cotizante', sa.String(length=2), nullable=True),
        sa.Column('cod_depto_labor', sa.String(length=2), nullable=True),
        sa.Column('cod_municipio_labor', sa.String(length=3), nullable=True),
        sa.Column('cod_afp', sa.String(length=6), nullable=True),
        sa.Column('cod_eps', sa.String(length=6), nullable=True),
        sa.Column('cod_ccf', sa.String(length=6), nullable=True),
        sa.Column('dias_pension', sa.Integer(), nullable=True),
        sa.Column('dias_salud', sa.Integer(), nullable=True),
        sa.Column('dias_arl', sa.Integer(), nullable=True),
        sa.Column('dias_ccf', sa.Integer(), nullable=True),
        sa.Column('salario_basico', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tipo_salario', sa.String(length=1), nullable=True),
        sa.Column('ibc_pension', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('ibc_salud', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('ibc_arl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('ibc_ccf', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('ibc_otros_parafiscales', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_pension', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('cot_pension', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('aporte_vol_afiliado', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('aporte_vol_aportante', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_pension', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('fsp_solidaridad', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('fsp_subsistencia', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_salud', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('cot_salud', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('valor_adres', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_arl', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('centro_trabajo', sa.String(length=9), nullable=True),
        sa.Column('cot_arl', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_ccf', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('valor_ccf', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_sena', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('valor_sena', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_icbf', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('valor_icbf', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_esap', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('valor_esap', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('tarifa_men', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('valor_men', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('novedades', sa.Text(), nullable=True),
        sa.Column('fechas_novedades', sa.Text(), nullable=True),
        sa.Column('horas_laboradas', sa.Integer(), nullable=True),
        sa.Column('cotizante_principal_tipo_doc', sa.String(length=2), nullable=True),
        sa.Column('cotizante_principal_doc', sa.String(length=16), nullable=True),
        sa.Column('linea_plana', sa.Text(), nullable=True),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organizacion_id'], ['organizaciones.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['liquidacion_id'], ['planillas_liquidacion.id'],
                                ondelete='CASCADE'),
        # SET NULL: si el afiliado se elimina, el detalle liquidado sobrevive con
        # su copia de nombre y documento.
        sa.ForeignKeyConstraint(['afiliado_id'], ['afiliados.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


CREADORES = {
    'pila_codigos':          _crear_pila_codigos,
    'aportantes_pila':       _crear_aportantes_pila,
    'planillas_liquidacion': _crear_planillas_liquidacion,
    'planillas_detalle':     _crear_planillas_detalle,
}


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existentes = set(inspector.get_table_names())

    # Orden fijo: liquidacion referencia aportantes, detalle referencia liquidacion.
    for tabla in TABLES:
        if tabla not in existentes:
            CREADORES[tabla]()

    inspector = inspect(bind)
    for tabla in TABLES:
        indices = {ix['name'] for ix in inspector.get_indexes(tabla)}
        for nombre, cols in INDEXES[tabla]:
            if nombre not in indices:
                op.create_index(nombre, tabla, cols)

    # Columnas PILA en afiliados.
    cols_afiliado = {c['name'] for c in inspector.get_columns('afiliados')}
    for nombre, tipo in AFILIADO_COLS:
        if nombre not in cols_afiliado:
            op.add_column('afiliados', sa.Column(nombre, tipo, nullable=True))

    inspector = inspect(bind)
    indices_afiliado = {ix['name'] for ix in inspector.get_indexes('afiliados')}
    for nombre, cols in AFILIADO_INDEXES:
        if nombre not in indices_afiliado:
            op.create_index(nombre, 'afiliados', cols)


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    indices_afiliado = {ix['name'] for ix in inspector.get_indexes('afiliados')}
    for nombre, _ in AFILIADO_INDEXES:
        if nombre in indices_afiliado:
            op.drop_index(nombre, table_name='afiliados')

    cols_afiliado = {c['name'] for c in inspector.get_columns('afiliados')}
    for nombre, _ in AFILIADO_COLS:
        if nombre in cols_afiliado:
            op.drop_column('afiliados', nombre)

    existentes = set(inspector.get_table_names())
    # Inverso al alta: primero las que dependen de otras.
    for tabla in reversed(TABLES):
        if tabla in existentes:
            indices = {ix['name'] for ix in inspector.get_indexes(tabla)}
            for nombre, _ in INDEXES[tabla]:
                if nombre in indices:
                    op.drop_index(nombre, table_name=tabla)
            op.drop_table(tabla)
