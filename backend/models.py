from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index, Numeric, text, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone, timedelta

COL_TZ = timezone(timedelta(hours=-5))   # Colombia UTC-5

def _utcnow():
    return datetime.now(timezone.utc)

def _col_now():
    """Hora actual en Colombia (UTC-5)."""
    return datetime.now(COL_TZ)


def _org_fk(nullable=False):
    """Columna organizacion_id estándar (tenant). Multi-tenant: aísla los datos por organización."""
    return Column(Integer, ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True, nullable=nullable)


class Organizacion(Base):
    """Inquilino (tenant) del SaaS. Cada organización tiene sus propios datos aislados."""
    __tablename__ = "organizaciones"
    id      = Column(Integer, primary_key=True, index=True)
    nombre  = Column(String(150), nullable=False)
    slug    = Column(String(80), unique=True, index=True)   # identificador legible/único
    activo  = Column(Boolean, default=True)
    precio_afiliado = Column(Numeric(12, 2), default=30_000)  # COP cobrados por afiliado activo/mes
    creado  = Column(DateTime(timezone=True), default=_utcnow)


class IngresoMensualOrg(Base):
    """Snapshot mensual de facturación del SaaS por organización (afiliados activos × precio).
    El mes en curso se refresca al consultar Ingresos; los meses pasados quedan congelados.
    Tabla de nivel superadmin: NO entra en el auto-filtro tenant (se consulta sin organización activa)."""
    __tablename__ = "ingresos_mensuales_org"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'anio', 'mes', name='uq_ing_mensual_org_anio_mes'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True, nullable=False)
    anio            = Column(Integer, nullable=False, index=True)
    mes             = Column(Integer, nullable=False)            # 1-12
    afiliados       = Column(Integer, default=0)                 # afiliados facturables ese mes
    precio          = Column(Numeric(12, 2), default=30_000)     # precio vigente al snapshot
    ingreso         = Column(Numeric(15, 2), default=0)          # afiliados × precio
    actualizado     = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class FacturaOrg(Base):
    """Factura del SaaS hacia una organización: cierre de un mes (afiliados × precio).
    Una por organización/mes. Tabla de nivel superadmin: fuera del auto-filtro tenant."""
    __tablename__ = "facturas_org"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'anio', 'mes', name='uq_factura_org_periodo'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = Column(Integer, ForeignKey("organizaciones.id", ondelete="CASCADE"), index=True, nullable=False)
    anio            = Column(Integer, nullable=False, index=True)
    mes             = Column(Integer, nullable=False)              # 1-12
    afiliados       = Column(Integer, default=0)                   # afiliados facturados
    precio          = Column(Numeric(12, 2), default=30_000)
    monto           = Column(Numeric(15, 2), default=0)            # afiliados × precio
    estado          = Column(String(15), default="pendiente", index=True)  # pendiente | pagada
    creado          = Column(DateTime(timezone=True), default=_utcnow)
    pagada_en       = Column(DateTime(timezone=True), nullable=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id          = Column(Integer, primary_key=True, index=True)
    nombre      = Column(String(120))
    username    = Column(String(60), unique=True, index=True)  # único global (login sin selector de org)
    password    = Column(String(120), nullable=True)
    rol         = Column(String(20), default="empleado")   # superadmin | admin | empleado | cliente
    organizacion_id = _org_fk(nullable=True)               # NULL solo para superadmin (sin organización)
    cliente_ref = Column(String(120), nullable=True)       # para rol=cliente: valor de cliente_txt
    ver_detalle = Column(Boolean, default=False)           # portal: puede ver la columna "Detalle" de afiliados
    activo      = Column(Boolean, default=True)
    creado      = Column(DateTime(timezone=True), default=_utcnow)

class Afiliado(Base):
    __tablename__ = "afiliados"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'doc', name='uq_afiliado_org_doc'),
        Index('ix_afiliado_org_activo_estado_srv', 'organizacion_id', 'activo', 'estado_srv'),  # cobro: activo=True + estado_srv
        Index('ix_afiliado_org_cliente_estado', 'organizacion_id', 'cliente_txt', 'estado'), # filtro cliente+estado
        # Covering index para get_cobro — soporta empresa/cliente/doc filters con Index-Only Scan
        Index('ix_afiliado_cobro_cobertura', 'organizacion_id', 'activo', 'estado_srv', 'empresa', 'cliente_txt',
              postgresql_where=text("activo = TRUE")),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    nombre          = Column(String(150), index=True)
    tipo_doc        = Column(String(10), default="CC")
    doc             = Column(String(20), index=True)
    empresa         = Column(String(80), index=True)       # índice para filtros frecuentes
    cargo           = Column(String(80))
    cliente_txt     = Column(String(120), index=True)      # índice para filtros frecuentes
    eps             = Column(String(80))
    arl             = Column(String(10))
    ccf             = Column(String(80))
    afp             = Column(String(80))
    subtipo         = Column(String(50), index=True)       # índice para filtros frecuentes
    estado          = Column(String(30), default="ACTIVO", index=True)
    estado_srv      = Column(String(50), default="ACTIVO", index=True)
    servicios       = Column(Text, default="[]")     # JSON list
    tel             = Column(String(20))
    email           = Column(String(100))
    dir             = Column(String(200))
    ciudad          = Column(String(100))
    novedades       = Column(Text)
    detalle         = Column(Text)
    ibc             = Column(Numeric(15, 2), nullable=True)   # IBC individual (None = usar global)
    fecha_ingreso   = Column(String(10))
    fecha_afiliacion= Column(String(10))

    # ── Campos PILA (Anexo Técnico 2 v30, registro tipo 2) ───────────────────
    # Nullable a propósito: los afiliados ya cargados no los tienen y se
    # completan por backfill. La liquidación valida que estén antes de generar.
    # El nombre va partido en cuatro porque el registro tipo 2 los exige
    # separados (campos 11-14), no como el `nombre` completo que ya existe.
    primer_apellido  = Column(String(20))
    segundo_apellido = Column(String(30))
    primer_nombre    = Column(String(20))
    segundo_nombre   = Column(String(30))
    fecha_nacimiento = Column(String(10))    # AAAA-MM-DD
    sexo             = Column(String(1))     # M | F
    # Tipo y subtipo definen a qué subsistemas está obligado el cotizante.
    tipo_cotizante    = Column(String(2), index=True)
    subtipo_cotizante = Column(String(2))
    extranjero_no_pension = Column(Boolean, default=False)
    colombiano_exterior   = Column(Boolean, default=False)
    cod_depto_labor     = Column(String(2))   # DANE
    cod_municipio_labor = Column(String(3))   # DANE
    # Códigos PILA de las administradoras. Los campos `eps`/`afp`/`ccf`/`arl`
    # de arriba son texto libre y sirven para mostrar; estos son los que van
    # al archivo plano y deben existir en `pila_codigos`.
    cod_eps = Column(String(6))
    cod_afp = Column(String(6))
    cod_ccf = Column(String(6))
    cod_arl = Column(String(6))
    clase_riesgo = Column(String(1))          # 1..5
    tarifa_arl   = Column(Numeric(7, 5))      # p.ej. 0.00522 para riesgo 1
    tipo_salario   = Column(String(1))        # F fijo | V variable | I integral
    salario_basico = Column(Numeric(15, 2))
    centro_trabajo = Column(String(9))
    # Para beneficiarios que cotizan a través de un cotizante principal.
    cotizante_principal_tipo_doc = Column(String(2))
    cotizante_principal_doc      = Column(String(16))
    horas_laboradas = Column(Integer)         # solo cotizantes de tiempo parcial
    fecha_expedicion= Column(String(10))   # dd/mm/aaaa — RUAF la exige para consultar

    # ── Campos PILA (Anexo Técnico 2 v30, registro tipo 2) ───────────────────
    # Nullable a propósito: los afiliados ya cargados no los tienen y se
    # completan por backfill. La liquidación valida que estén antes de generar.
    # El nombre va partido en cuatro porque el registro tipo 2 los exige
    # separados (campos 11-14), no como el `nombre` completo que ya existe.
    primer_apellido  = Column(String(20))
    segundo_apellido = Column(String(30))
    primer_nombre    = Column(String(20))
    segundo_nombre   = Column(String(30))
    fecha_nacimiento = Column(String(10))    # AAAA-MM-DD
    sexo             = Column(String(1))     # M | F
    # Tipo y subtipo definen a qué subsistemas está obligado el cotizante.
    tipo_cotizante    = Column(String(2), index=True)
    subtipo_cotizante = Column(String(2))
    extranjero_no_pension = Column(Boolean, default=False)
    colombiano_exterior   = Column(Boolean, default=False)
    cod_depto_labor     = Column(String(2))   # DANE
    cod_municipio_labor = Column(String(3))   # DANE
    # Códigos PILA de las administradoras. Los campos `eps`/`afp`/`ccf`/`arl`
    # de arriba son texto libre y sirven para mostrar; estos son los que van
    # al archivo plano y deben existir en `pila_codigos`.
    cod_eps = Column(String(6))
    cod_afp = Column(String(6))
    cod_ccf = Column(String(6))
    cod_arl = Column(String(6))
    clase_riesgo = Column(String(1))          # 1..5
    tarifa_arl   = Column(Numeric(7, 5))      # p.ej. 0.00522 para riesgo 1
    tipo_salario   = Column(String(1))        # F fijo | V variable | I integral
    salario_basico = Column(Numeric(15, 2))
    centro_trabajo = Column(String(9))
    # Para beneficiarios que cotizan a través de un cotizante principal.
    cotizante_principal_tipo_doc = Column(String(2))
    cotizante_principal_doc      = Column(String(16))
    horas_laboradas = Column(Integer)         # solo cotizantes de tiempo parcial
    registrado_por  = Column(String(60))
    activo          = Column(Boolean, default=True)
    creado          = Column(DateTime(timezone=True), default=_utcnow)
    actualizado     = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

class Factura(Base):
    __tablename__ = "facturas"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'doc', 'mes', 'anio', name='uq_factura_org_doc_mes_anio'),
        UniqueConstraint('organizacion_id', 'codigo', name='uq_factura_org_codigo'),
        Index('ix_factura_org_cliente_estado', 'organizacion_id', 'cliente', 'estado'),
        Index('ix_factura_org_anio_mes', 'organizacion_id', 'anio', 'mes'),
    )
    id               = Column(Integer, primary_key=True, index=True)
    organizacion_id  = _org_fk()
    codigo           = Column(String(20), index=True)
    nombre_afiliado  = Column(String(150), index=True)
    doc              = Column(String(20), index=True)   # doc del afiliado
    cliente          = Column(String(120), index=True)
    anio             = Column(String(4), index=True)
    mes              = Column(String(20), index=True)
    periodo          = Column(String(5))
    estado           = Column(String(20), default="pendiente", index=True)  # índice para filtros
    banco            = Column(String(60), index=True)
    ingresos         = Column(Numeric(15, 2), default=0)
    costos           = Column(Numeric(15, 2), default=0)
    costo_adm        = Column(Numeric(15, 2), default=0)
    conceptos_extra  = Column(Numeric(15, 2), default=0)
    utilidad         = Column(Numeric(15, 2), default=0)
    novedades        = Column(Text)
    servicios_detalle= Column(Text, default="[]")   # JSON
    conceptos_detalle= Column(Text, default="[]")   # JSON
    afiliado_eliminado = Column(Boolean, default=False)
    pagado_en        = Column(DateTime(timezone=True), nullable=True)
    monto_pagado     = Column(Numeric(15, 2), default=0)   # acumulado de abonos parciales
    creado_por       = Column(String(60))
    creado           = Column(DateTime(timezone=True), default=_utcnow)
    actualizado      = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

class Retiro(Base):
    __tablename__ = "retiros"
    __table_args__ = (
        Index('ix_retiro_org_anio_mes', 'organizacion_id', 'anio', 'mes'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    nombre          = Column(String(150))
    doc             = Column(String(20), index=True)
    empresa         = Column(String(80))
    fecha           = Column(String(10))
    motivo          = Column(String(50))
    obs             = Column(Text)
    mes             = Column(String(20))
    anio            = Column(String(4))
    registrado_por  = Column(String(60))
    creado          = Column(DateTime(timezone=True), default=_utcnow)

class Eliminado(Base):
    __tablename__ = "eliminados"
    id                  = Column(Integer, primary_key=True, index=True)
    organizacion_id     = _org_fk()
    nombre              = Column(String(150))
    doc                 = Column(String(20), index=True)
    empresa             = Column(String(80))
    datos_completos     = Column(Text)    # JSON snapshot del afiliado
    fecha_eliminacion   = Column(String(10))
    mes                 = Column(String(20))
    eliminado_por       = Column(String(60))
    estado_planilla     = Column(String(30), nullable=True)  # retiro_pendiente / planilla_hecha / planilla_pagada
    creado              = Column(DateTime(timezone=True), default=_utcnow)

class Empleado(Base):
    __tablename__ = "empleados"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'doc', name='uq_empleado_org_doc'),
    )
    id            = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    nombre        = Column(String(150))
    doc           = Column(String(20), index=True)
    cargo         = Column(String(80))
    tel           = Column(String(20))
    email         = Column(String(100))
    usuario       = Column(String(60))     # username asignado
    nomina        = Column(Numeric(15, 2), default=0)
    activo        = Column(Boolean, default=True)
    fecha_ingreso = Column(String(10))
    creado        = Column(DateTime(timezone=True), default=_utcnow)

class Gasto(Base):
    __tablename__ = "gastos"
    __table_args__ = (
        Index('ix_gasto_org_anio_mes', 'organizacion_id', 'anio', 'mes'),  # dashboard financiero
    )
    id     = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    nombre = Column(String(120))
    valor  = Column(Numeric(15, 2), default=0)
    activo = Column(Boolean, default=True)
    mes    = Column(Integer)
    anio   = Column(Integer)
    creado = Column(DateTime(timezone=True), default=_utcnow)

class IngresoAdicional(Base):
    __tablename__ = "ingresos_adicionales"
    __table_args__ = (
        Index('ix_ingreso_adicional_org_anio_mes', 'organizacion_id', 'anio', 'mes'),
    )
    id          = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    concepto    = Column(String(60))   # Comisión | Planilla verificable | Otro
    descripcion = Column(String(200), default="")
    valor       = Column(Numeric(15, 2), default=0)
    mes         = Column(Integer)
    anio        = Column(Integer)
    creado_por  = Column(String(60), default="")
    creado      = Column(DateTime(timezone=True), default=_utcnow)


class NominaMensual(Base):
    __tablename__ = "nomina_mensual"
    __table_args__ = (
        Index('ix_nomina_org_empleado_anio_mes', 'organizacion_id', 'empleado_id', 'anio', 'mes'),
        UniqueConstraint('organizacion_id', 'empleado_id', 'mes', 'anio', name='uq_nomina_org_emp_mes_anio'),
    )
    id          = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    empleado_id = Column(Integer, index=True)
    mes         = Column(Integer)
    anio        = Column(Integer)
    valor       = Column(Numeric(15, 2), default=0)

class Config(Base):
    __tablename__ = "config"
    __table_args__ = (
        UniqueConstraint('organizacion_id', name='uq_config_org'),   # una config por organización
    )
    id                 = Column(Integer, primary_key=True)
    organizacion_id    = _org_fk()
    ibc_global         = Column(Numeric(15, 2), default=1_750_905)
    porcentajes        = Column(Text)    # JSON dict
    plantilla_whatsapp = Column(Text)    # Plantilla del mensaje de WhatsApp
    cargo_adicional    = Column(Numeric(15, 2), default=2200)
    mes_inicio_cobro   = Column(Integer)  # Mes a partir del cual el módulo de cobro genera filas
    anio_inicio_cobro  = Column(Integer)  # Año correspondiente

class Lista(Base):
    __tablename__ = "listas"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'nombre', name='uq_lista_org_nombre'),
    )
    id     = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    nombre = Column(String(60))
    items  = Column(Text)    # JSON list

class SolicitudNovedad(Base):
    __tablename__ = "solicitudes_novedad"
    id               = Column(Integer, primary_key=True, index=True)
    organizacion_id  = _org_fk()
    cliente_ref      = Column(String(120), index=True)
    username_cliente = Column(String(60), index=True)
    afiliado_doc     = Column(String(20))
    afiliado_nombre  = Column(String(150))
    tipo             = Column(String(80))
    descripcion      = Column(Text)
    estado           = Column(String(20), default="pendiente", index=True)  # pendiente | atendido
    respuesta        = Column(Text, nullable=True)
    creado           = Column(DateTime(timezone=True), default=_utcnow)


class NovedadPago(Base):
    __tablename__ = "novedades_pago"
    id               = Column(Integer, primary_key=True, index=True)
    organizacion_id  = _org_fk()
    cliente_ref      = Column(String(120), index=True)
    username_cliente = Column(String(60), index=True)
    mes              = Column(String(20))
    anio             = Column(String(4))
    afiliados_docs   = Column(Text)    # JSON list de docs
    afiliados_nombres= Column(Text)    # JSON list de nombres
    obs              = Column(Text, default="")
    estado           = Column(String(20), default="pendiente", index=True)  # pendiente | procesado
    respuesta        = Column(Text, nullable=True)
    creado           = Column(DateTime(timezone=True), default=_utcnow)


class SolicitudRetiro(Base):
    __tablename__ = "solicitudes_retiro"
    id               = Column(Integer, primary_key=True, index=True)
    organizacion_id  = _org_fk()
    cliente_ref      = Column(String(120), index=True)
    username_cliente = Column(String(60), index=True)
    afiliado_doc     = Column(String(20))
    afiliado_nombre  = Column(String(150))
    motivo           = Column(String(200))
    obs              = Column(Text, default="")
    estado           = Column(String(20), default="pendiente", index=True)  # pendiente | ejecutado | rechazado
    respuesta        = Column(Text, nullable=True)
    creado           = Column(DateTime(timezone=True), default=_utcnow)


class Actividad(Base):
    __tablename__ = "actividad"
    __table_args__ = (
        Index('ix_actividad_org_usuario_modulo', 'organizacion_id', 'usuario', 'modulo'),
        Index('ix_actividad_org_fecha', 'organizacion_id', 'fecha'),
    )
    id      = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    usuario = Column(String(60))
    accion  = Column(String(200))
    modulo  = Column(String(60))
    detalle = Column(String(200))
    fecha   = Column(DateTime(timezone=True), default=_utcnow)

class Tarea(Base):
    __tablename__ = "tareas"
    __table_args__ = (
        Index('ix_tarea_org_estado_asignado', 'organizacion_id', 'estado', 'asignado_a'),  # tareas activas por usuario
    )
    id            = Column(Integer, primary_key=True)
    organizacion_id = _org_fk()
    titulo        = Column(String(200))
    descripcion   = Column(Text, default="")
    asignado_a    = Column(String(60), index=True)
    creado_por    = Column(String(60), index=True)
    estado        = Column(String(20), default="pendiente", index=True)  # pendiente|en_proceso|completada|finalizada
    fecha_limite  = Column(String(10), nullable=True)
    privada       = Column(Boolean, default=False)
    creado        = Column(DateTime(timezone=True), default=_utcnow)
    completado_en = Column(DateTime(timezone=True), nullable=True)
    finalizado_en = Column(DateTime(timezone=True), nullable=True)
    finalizado_por= Column(String(60), nullable=True)

class TareaComentario(Base):
    __tablename__ = "tarea_comentarios"
    id       = Column(Integer, primary_key=True)
    organizacion_id = _org_fk()
    tarea_id = Column(Integer, index=True)
    usuario  = Column(String(60))
    texto    = Column(Text)
    creado   = Column(DateTime(timezone=True), default=_utcnow)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id             = Column(Integer, primary_key=True)
    ip             = Column(String(45), unique=True, index=True)
    count          = Column(Integer, default=0)
    last_attempt   = Column(Float, default=0.0)

class Notificacion(Base):
    __tablename__ = "notificaciones"
    __table_args__ = (
        Index('ix_notificacion_org_usuario_leida', 'organizacion_id', 'usuario', 'leida'),  # no leídas por usuario
    )
    id       = Column(Integer, primary_key=True)
    organizacion_id = _org_fk()
    usuario  = Column(String(60), index=True)
    mensaje  = Column(Text)  # texto libre: puede incluir notas largas del administrador
    leida    = Column(Boolean, default=False, index=True)
    tarea_id = Column(Integer, nullable=True)
    creado   = Column(DateTime(timezone=True), default=_utcnow)

class PlanillaPago(Base):
    __tablename__ = "planillas_pago"
    __table_args__ = (
        Index('ix_planilla_org_cliente_anio_mes', 'organizacion_id', 'cliente_ref', 'anio', 'mes'),
    )
    id           = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    cliente_ref  = Column(String(150), index=True)
    mes          = Column(String(20))
    anio         = Column(String(4))
    observaciones= Column(Text, default="")

    subido_por   = Column(String(60))
    creado       = Column(DateTime(timezone=True), default=_utcnow)

class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (
        Index('ix_documento_org_contexto_id', 'organizacion_id', 'contexto', 'contexto_id'),
    )
    id           = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    upload_id    = Column(String(36), unique=True, nullable=True, index=True)  # UUID idempotency key
    afiliado_doc = Column(String(20), index=True)       # doc del afiliado dueño
    nombre       = Column(String(200))                   # nombre original del archivo
    tipo         = Column(String(20))                    # extension: pdf, jpg, png, docx, xlsx
    ruta         = Column(String(500))                   # path relativo en backend/uploads/
    tamano       = Column(Integer, default=0)            # bytes
    subido_por   = Column(String(60))
    contexto     = Column(String(60), default="afiliado") # afiliado | tarea | novedad_portal
    contexto_id  = Column(Integer, nullable=True)        # id de tarea o solicitud si aplica
    creado       = Column(DateTime(timezone=True), default=_utcnow)


class AvisoCliente(Base):
    """Avisos/comunicados que el admin envía a un cliente específico."""
    __tablename__ = "avisos_clientes"
    __table_args__ = (
        Index('ix_aviso_org_cliente_ref', 'organizacion_id', 'cliente_ref'),
    )
    id          = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    cliente_ref = Column(String(120), index=True)   # destinatario (cliente_txt / cliente_ref)
    titulo      = Column(String(200))
    mensaje     = Column(Text)
    leido       = Column(Boolean, default=False)
    creado_por  = Column(String(60))
    creado      = Column(DateTime(timezone=True), default=_utcnow)


class TokenBlacklist(Base):
    """Refresh tokens invalidados explícitamente (logout o rotation)."""
    __tablename__ = "token_blacklist"
    id         = Column(Integer, primary_key=True, index=True)
    jti        = Column(String(64), unique=True, index=True)        # JWT ID único
    expires_at = Column(DateTime(timezone=True))                    # timezone=True evita bugs de comparación en PostgreSQL
    creado     = Column(DateTime(timezone=True), default=_utcnow)

class CredencialPortal(Base):
    __tablename__ = "credenciales_portales"
    __table_args__ = (
        Index('ix_cred_org_portal_tipo', 'organizacion_id', 'portal'),
        Index('ix_cred_org_doc', 'organizacion_id', 'numero_doc'),
    )
    id             = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    tipo_doc       = Column(String(10), default="NIT")   # NIT | CC
    numero_doc     = Column(String(40), nullable=False)
    titular        = Column(String(150), default="")
    portal         = Column(String(40), nullable=False)  # EPS | CCF | Aportes en Línea | Pago Simple | Asopagos
    entidad        = Column(String(100), default="")     # Sura EPS, Compensar, etc.
    usuario_portal = Column(String(150), nullable=False)
    clave_portal   = Column(Text, nullable=False)        # encriptada con Fernet
    obs            = Column(Text, default="")
    creado_por     = Column(String(60), default="")
    creado         = Column(DateTime(timezone=True), default=_utcnow)
    actualizado    = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SeguimientoArl(Base):
    __tablename__ = "seguimiento_arl"
    __table_args__ = (
        Index('ix_seg_arl_org_cliente_estado', 'organizacion_id', 'cliente', 'estado'),
    )
    id               = Column(Integer, primary_key=True, index=True)
    organizacion_id  = _org_fk()
    nombre           = Column(String(120), nullable=False)
    documento        = Column(String(30), nullable=False)
    cliente          = Column(String(150), index=True)
    empresa          = Column(String(120))
    fecha_afiliacion = Column(String(20))   # 'YYYY-MM-DD'
    entidad_arl      = Column(String(20), default='SURA')    # SURA | POSITIVA
    nivel_arl        = Column(String(10), default='N/A')
    tipo_afiliado    = Column(String(15), default='dependiente')  # dependiente | independiente
    observaciones    = Column(Text, nullable=True)
    estado           = Column(String(20), default='activo')  # activo | retirar | retirado
    creado_en        = Column(DateTime(timezone=True), default=_utcnow)
    ultima_alerta_en = Column(DateTime(timezone=True), nullable=True)


class ConsultaExterna(Base):
    """Registro de cada consulta a una fuente oficial (ADRES, RUAF...).

    Cumple tres funciones a la vez:
      - cache: `valido_hasta` evita repetir la consulta (y el captcha) por 30 dias
      - auditoria: quien consulto la afiliacion en salud de quien, y cuando.
        Dato sensible bajo Ley 1581/2012, asi que aqui NO se suprime al admin.
      - diagnostico: los fallos quedan con su motivo para detectar cuando la
        fuente cambio de forma.

    Multi-tenant: lleva `organizacion_id` y entra en el auto-filtro de tenant.py.
    El cache es POR ORGANIZACION a proposito — una organizacion no puede ver a
    quien consulto otra, ni reutilizar un resultado que obtuvo otra con la
    autorizacion de su propio titular. Repetir el documento desde otra
    organizacion cuesta un captcha nuevo, y esta bien que asi sea.
    """
    __tablename__ = "consultas_externas"
    __table_args__ = (
        Index('ix_consulta_org_fuente_doc', 'organizacion_id', 'fuente', 'doc'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    fuente          = Column(String(20), nullable=False, index=True)  # adres | ruaf
    tipo_doc        = Column(String(10), default="CC")
    doc             = Column(String(20), nullable=False, index=True)
    exito           = Column(Boolean, default=False, index=True)
    nombre          = Column(String(150))
    eps             = Column(String(120))
    regimen         = Column(String(60))
    estado_afil     = Column(String(60))
    tipo_afiliado   = Column(String(60))
    respuesta       = Column(Text)              # JSON completo normalizado
    error_detalle   = Column(Text)
    usuario         = Column(String(60), index=True)
    creado          = Column(DateTime(timezone=True), default=_utcnow)
    valido_hasta    = Column(DateTime(timezone=True), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# PILA — Planilla Integrada de Liquidación de Aportes
# Estructura según el Anexo Técnico 2 de la Resolución 2388 de 2016,
# versión 30 (24-07-2026, modificada por la Resolución 1529 de 2026).
# ─────────────────────────────────────────────────────────────────────────────


class PilaCodigo(Base):
    """Catálogo normativo de códigos PILA. Global: no lleva organizacion_id
    porque la tabla la define la norma, no el cliente, y es idéntica para todas
    las organizaciones. Por eso queda fuera del auto-filtro de tenant.py.

    `tipo` agrupa el catálogo: EPS, AFP, CCF, ARL, TIPO_COTIZANTE,
    SUBTIPO_COTIZANTE, TIPO_APORTANTE, TIPO_PLANILLA, TIPO_DOC, DEPTO, MUNICIPIO.
    """
    __tablename__ = "pila_codigos"
    __table_args__ = (
        UniqueConstraint('tipo', 'codigo', name='uq_pila_codigo_tipo_codigo'),
        Index('ix_pila_codigo_tipo_vigente', 'tipo', 'vigente'),
    )
    id      = Column(Integer, primary_key=True, index=True)
    tipo    = Column(String(24), nullable=False, index=True)
    codigo  = Column(String(10), nullable=False, index=True)
    nombre  = Column(String(200), nullable=False)
    # Contexto del código: el departamento al que pertenece un municipio, o la
    # clase de riesgo por defecto de una actividad económica.
    padre   = Column(String(10), nullable=True, index=True)
    vigente = Column(Boolean, default=True, index=True)
    creado  = Column(DateTime(timezone=True), default=_utcnow)


class AportantePila(Base):
    """Empresa aportante con los datos que exige el registro tipo 1 (encabezado).

    Hoy el aportante vive como texto libre en `Afiliado.empresa` / `Afiliado.cliente_txt`.
    Ninguna planilla sale de un string: el encabezado necesita NIT con dígito de
    verificación, tipo y clase de aportante, código ARL y sucursal. `cliente_ref`
    es el puente con lo que ya existe (coincide con `Afiliado.cliente_txt`).
    """
    __tablename__ = "aportantes_pila"
    __table_args__ = (
        UniqueConstraint('organizacion_id', 'cliente_ref', name='uq_aportante_org_cliente'),
        Index('ix_aportante_org_doc', 'organizacion_id', 'num_doc'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    cliente_ref     = Column(String(150), nullable=False, index=True)

    razon_social = Column(String(200), nullable=False)
    tipo_doc     = Column(String(2), default="NI")   # NI | CC | CE | TI | PA
    num_doc      = Column(String(16), nullable=False, index=True)
    dv           = Column(String(1))                 # dígito de verificación del NIT
    tipo_persona = Column(String(1), default="J")    # J jurídica | N natural

    tipo_aportante  = Column(String(2))   # 01..17 (17 = pagador recicladores, Res. 1529/2026)
    clase_aportante = Column(String(1))

    cod_arl             = Column(String(6))
    clase_riesgo        = Column(String(1))   # 1..5
    actividad_economica = Column(String(7))   # CIIU + clase de riesgo

    cod_depto       = Column(String(2))   # DANE
    cod_municipio   = Column(String(3))   # DANE
    cod_sucursal    = Column(String(10))
    nombre_sucursal = Column(String(40))

    # Artículo 114-1 ET: exonera de SENA, ICBF y salud patronal a los cotizantes
    # con IBC bajo 10 SMLMV. Cambia el cálculo, no solo el reporte.
    exonerado_parafiscales = Column(Boolean, default=False)

    direccion = Column(String(200))
    telefono  = Column(String(20))
    email     = Column(String(100))

    activo      = Column(Boolean, default=True, index=True)
    creado      = Column(DateTime(timezone=True), default=_utcnow)
    actualizado = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class PlanillaLiquidacion(Base):
    """Cabecera de una liquidación PILA: un período, un aportante, un tipo de planilla.

    Distinta de `PlanillaPago`, que solo guarda archivos subidos a mano. Esta es la
    planilla que el sistema liquida y, más adelante, envía al operador.

    `periodo_cotizacion` y `periodo_pago` van separados a propósito: en PILA no
    siempre coinciden, y el propio módulo de ADAX los trata como campos distintos.
    """
    __tablename__ = "planillas_liquidacion"
    __table_args__ = (
        Index('ix_liq_org_aportante_periodo', 'organizacion_id', 'aportante_id', 'periodo_cotizacion'),
        Index('ix_liq_org_estado', 'organizacion_id', 'estado'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    aportante_id    = Column(Integer, ForeignKey("aportantes_pila.id", ondelete="RESTRICT"),
                             index=True, nullable=False)
    cliente_ref     = Column(String(150), index=True)

    tipo_planilla      = Column(String(1), nullable=False)   # E | Y | I | A | N | M | K | J | S | W
    periodo_cotizacion = Column(String(7), nullable=False)   # AAAA-MM
    periodo_pago       = Column(String(7), nullable=False)   # AAAA-MM
    fecha_limite_pago  = Column(String(10))                  # AAAA-MM-DD

    # borrador → generada → enviada → numerada → pagada | anulada
    estado = Column(String(20), default="borrador", index=True)

    operador           = Column(String(30))            # pago_simple | aportes_en_linea
    numero_planilla    = Column(String(20), index=True)  # lo asigna el operador
    planilla_corregida = Column(String(20))            # para tipo N: la planilla que corrige
    link_pago          = Column(Text)
    respuesta_operador = Column(Text)                  # JSON crudo, para diagnóstico

    total_cotizantes = Column(Integer, default=0)
    total_pension    = Column(Numeric(15, 2), default=0)
    total_salud      = Column(Numeric(15, 2), default=0)
    total_arl        = Column(Numeric(15, 2), default=0)
    total_ccf        = Column(Numeric(15, 2), default=0)
    total_sena       = Column(Numeric(15, 2), default=0)
    total_icbf       = Column(Numeric(15, 2), default=0)
    total_esap       = Column(Numeric(15, 2), default=0)
    total_men        = Column(Numeric(15, 2), default=0)
    total_fsp        = Column(Numeric(15, 2), default=0)
    total_general    = Column(Numeric(15, 2), default=0)

    archivo_ruta  = Column(Text)          # ruta en R2 del plano generado
    observaciones = Column(Text, default="")
    generado_por  = Column(String(60))
    creado        = Column(DateTime(timezone=True), default=_utcnow)
    actualizado   = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class PlanillaDetalle(Base):
    """Un registro tipo 2 por cotizante: la liquidación congelada.

    Copia nombre, documento y administradoras en vez de depender del afiliado: si
    mañana el trabajador cambia de EPS o se retira, la planilla ya liquidada debe
    seguir mostrando lo que se reportó y se pagó ese mes.

    `linea_plana` conserva el registro tal como salió en el archivo. Es la única
    forma de auditar contra lo que recibió el operador sin volver a calcular.
    """
    __tablename__ = "planillas_detalle"
    __table_args__ = (
        Index('ix_detalle_liq_doc', 'liquidacion_id', 'doc'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    organizacion_id = _org_fk()
    liquidacion_id  = Column(Integer, ForeignKey("planillas_liquidacion.id", ondelete="CASCADE"),
                             index=True, nullable=False)
    afiliado_id     = Column(Integer, ForeignKey("afiliados.id", ondelete="SET NULL"), nullable=True)

    secuencia = Column(Integer)   # consecutivo dentro de la planilla
    tipo_doc  = Column(String(2))
    doc       = Column(String(16), index=True)
    # Longitudes del anexo: campos 11-14 son 20, 30, 20 y 30 caracteres.
    primer_apellido  = Column(String(20))
    segundo_apellido = Column(String(30))
    primer_nombre    = Column(String(20))
    segundo_nombre   = Column(String(30))

    tipo_cotizante      = Column(String(2))
    subtipo_cotizante   = Column(String(2))
    cod_depto_labor     = Column(String(2))
    cod_municipio_labor = Column(String(3))

    cod_afp = Column(String(6))
    cod_eps = Column(String(6))
    cod_ccf = Column(String(6))

    # Los cuatro pueden diferir en un mismo cotizante.
    dias_pension = Column(Integer, default=0)
    dias_salud   = Column(Integer, default=0)
    dias_arl     = Column(Integer, default=0)
    dias_ccf     = Column(Integer, default=0)

    salario_basico = Column(Numeric(15, 2), default=0)
    tipo_salario   = Column(String(1))
    ibc_pension    = Column(Numeric(15, 2), default=0)
    ibc_salud      = Column(Numeric(15, 2), default=0)
    ibc_arl        = Column(Numeric(15, 2), default=0)
    ibc_ccf        = Column(Numeric(15, 2), default=0)
    ibc_otros_parafiscales = Column(Numeric(15, 2), default=0)

    tarifa_pension       = Column(Numeric(7, 5), default=0)
    cot_pension          = Column(Numeric(15, 2), default=0)
    aporte_vol_afiliado  = Column(Numeric(15, 2), default=0)
    aporte_vol_aportante = Column(Numeric(15, 2), default=0)
    total_pension        = Column(Numeric(15, 2), default=0)
    fsp_solidaridad      = Column(Numeric(15, 2), default=0)
    fsp_subsistencia     = Column(Numeric(15, 2), default=0)

    tarifa_salud = Column(Numeric(7, 5), default=0)
    cot_salud    = Column(Numeric(15, 2), default=0)
    valor_adres  = Column(Numeric(15, 2), default=0)   # UPC adicional o contribución solidaria

    tarifa_arl     = Column(Numeric(7, 5), default=0)
    centro_trabajo = Column(String(9))
    cot_arl        = Column(Numeric(15, 2), default=0)

    tarifa_ccf  = Column(Numeric(7, 5), default=0)
    valor_ccf   = Column(Numeric(15, 2), default=0)
    tarifa_sena = Column(Numeric(7, 5), default=0)
    valor_sena  = Column(Numeric(15, 2), default=0)
    tarifa_icbf = Column(Numeric(7, 5), default=0)
    valor_icbf  = Column(Numeric(15, 2), default=0)
    tarifa_esap = Column(Numeric(7, 5), default=0)
    valor_esap  = Column(Numeric(15, 2), default=0)
    tarifa_men  = Column(Numeric(7, 5), default=0)
    valor_men   = Column(Numeric(15, 2), default=0)

    # Banderas ING, RET, TDE, TAE, TDP, TAP, VSP, VST, SLN, IGE, LMA, VAC-LR,
    # AVP, VCT, IRL y sus fechas de inicio/fin. JSON porque son 16 banderas y 14
    # fechas que se reportan juntas o no se reportan: como columnas serían 30
    # nulos en la mayoría de las filas.
    novedades        = Column(Text, default="{}")
    fechas_novedades = Column(Text, default="{}")

    horas_laboradas              = Column(Integer)
    cotizante_principal_tipo_doc = Column(String(2))
    cotizante_principal_doc      = Column(String(16))

    linea_plana = Column(Text)   # el registro tipo 2 exacto que se escribió
    creado      = Column(DateTime(timezone=True), default=_utcnow)
