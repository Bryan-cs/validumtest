from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index, Numeric, text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone, timedelta

COL_TZ = timezone(timedelta(hours=-5))   # Colombia UTC-5

def _utcnow():
    return datetime.now(timezone.utc)

def _col_now():
    """Hora actual en Colombia (UTC-5)."""
    return datetime.now(COL_TZ)

class Usuario(Base):
    __tablename__ = "usuarios"
    id          = Column(Integer, primary_key=True, index=True)
    nombre      = Column(String(120))
    username    = Column(String(60), unique=True, index=True)
    password    = Column(String(120), nullable=True)
    rol         = Column(String(20), default="empleado")   # admin | empleado | cliente
    cliente_ref = Column(String(120), nullable=True)       # para rol=cliente: valor de cliente_txt
    activo      = Column(Boolean, default=True)
    creado      = Column(DateTime, default=_utcnow)

class Afiliado(Base):
    __tablename__ = "afiliados"
    __table_args__ = (
        Index('ix_afiliado_activo_estado_srv', 'activo', 'estado_srv'),  # cobro: activo=True + estado_srv
        Index('ix_afiliado_cliente_estado',    'cliente_txt', 'estado'), # filtro cliente+estado
        # Covering index para get_cobro — soporta empresa/cliente/doc filters con Index-Only Scan
        Index('ix_afiliado_cobro_cobertura', 'activo', 'estado_srv', 'empresa', 'cliente_txt',
              postgresql_where=text("activo = TRUE")),
    )
    id              = Column(Integer, primary_key=True, index=True)
    nombre          = Column(String(150), index=True)
    tipo_doc        = Column(String(10), default="CC")
    doc             = Column(String(20), unique=True, index=True)
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
    municipio_code  = Column(String(5), nullable=True)   # DIVIPOLA 5 dígitos para PILA
    obs             = Column(Text)
    novedades       = Column(Text)
    detalle         = Column(Text)
    ibc             = Column(Numeric(15, 2), nullable=True)   # IBC individual (None = usar global)
    fecha_ingreso   = Column(String(10))
    fecha_afiliacion= Column(String(10))
    registrado_por  = Column(String(60))
    activo          = Column(Boolean, default=True)
    creado          = Column(DateTime, default=_utcnow)
    actualizado     = Column(DateTime, default=_utcnow, onupdate=_utcnow)

from sqlalchemy import UniqueConstraint

class Factura(Base):
    __tablename__ = "facturas"
    __table_args__ = (
        UniqueConstraint('doc', 'mes', 'anio', name='uq_factura_doc_mes_anio'),
        Index('ix_factura_cliente_estado', 'cliente', 'estado'),
        Index('ix_factura_anio_mes', 'anio', 'mes'),
    )
    id               = Column(Integer, primary_key=True, index=True)
    codigo           = Column(String(20), unique=True, index=True)
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
    pagado_en        = Column(DateTime, nullable=True)
    monto_pagado     = Column(Numeric(15, 2), default=0)   # acumulado de abonos parciales
    creado_por       = Column(String(60))
    creado           = Column(DateTime, default=_utcnow)
    actualizado      = Column(DateTime, default=_utcnow, onupdate=_utcnow)

class Retiro(Base):
    __tablename__ = "retiros"
    __table_args__ = (
        Index('ix_retiro_anio_mes', 'anio', 'mes'),
    )
    id              = Column(Integer, primary_key=True, index=True)
    nombre          = Column(String(150))
    doc             = Column(String(20), unique=True, index=True)
    empresa         = Column(String(80))
    fecha           = Column(String(10))
    motivo          = Column(String(50))
    obs             = Column(Text)
    mes             = Column(String(20))
    anio            = Column(String(4))
    registrado_por  = Column(String(60))
    creado          = Column(DateTime, default=_utcnow)

class Eliminado(Base):
    __tablename__ = "eliminados"
    id                  = Column(Integer, primary_key=True, index=True)
    nombre              = Column(String(150))
    doc                 = Column(String(20), index=True)
    empresa             = Column(String(80))
    datos_completos     = Column(Text)    # JSON snapshot del afiliado
    fecha_eliminacion   = Column(String(10))
    mes                 = Column(String(20))
    eliminado_por       = Column(String(60))
    creado              = Column(DateTime, default=_utcnow)

class Empleado(Base):
    __tablename__ = "empleados"
    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(String(150))
    doc           = Column(String(20))
    cargo         = Column(String(80))
    tel           = Column(String(20))
    email         = Column(String(100))
    usuario       = Column(String(60))     # username asignado
    nomina        = Column(Numeric(15, 2), default=0)
    activo        = Column(Boolean, default=True)
    fecha_ingreso = Column(String(10))
    creado        = Column(DateTime, default=_utcnow)

class Gasto(Base):
    __tablename__ = "gastos"
    __table_args__ = (
        Index('ix_gasto_anio_mes', 'anio', 'mes'),  # dashboard financiero
    )
    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120))
    valor  = Column(Numeric(15, 2), default=0)
    activo = Column(Boolean, default=True)
    mes    = Column(Integer)
    anio   = Column(Integer)
    creado = Column(DateTime, default=_utcnow)

class IngresoAdicional(Base):
    __tablename__ = "ingresos_adicionales"
    __table_args__ = (
        Index('ix_ingreso_adicional_anio_mes', 'anio', 'mes'),
    )
    id          = Column(Integer, primary_key=True, index=True)
    concepto    = Column(String(60))   # Comisión | Planilla verificable | Otro
    descripcion = Column(String(200), default="")
    valor       = Column(Numeric(15, 2), default=0)
    mes         = Column(Integer)
    anio        = Column(Integer)
    creado_por  = Column(String(60), default="")
    creado      = Column(DateTime, default=_utcnow)


class NominaMensual(Base):
    __tablename__ = "nomina_mensual"
    __table_args__ = (
        Index('ix_nomina_empleado_anio_mes', 'empleado_id', 'anio', 'mes'),
    )
    id          = Column(Integer, primary_key=True, index=True)
    empleado_id = Column(Integer, index=True)
    mes         = Column(Integer)
    anio        = Column(Integer)
    valor       = Column(Numeric(15, 2), default=0)

class Config(Base):
    __tablename__ = "config"
    id                 = Column(Integer, primary_key=True, default=1)
    ibc_global         = Column(Numeric(15, 2), default=1_950_905)
    porcentajes        = Column(Text)    # JSON dict
    plantilla_whatsapp = Column(Text)    # Plantilla del mensaje de WhatsApp
    cargo_adicional    = Column(Numeric(15, 2), default=2200)
    mes_inicio_cobro   = Column(Integer)  # Mes a partir del cual el módulo de cobro genera filas
    anio_inicio_cobro  = Column(Integer)  # Año correspondiente

class Lista(Base):
    __tablename__ = "listas"
    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(60), unique=True)
    items  = Column(Text)    # JSON list

class SolicitudNovedad(Base):
    __tablename__ = "solicitudes_novedad"
    id               = Column(Integer, primary_key=True, index=True)
    cliente_ref      = Column(String(120), index=True)
    username_cliente = Column(String(60), index=True)
    afiliado_doc     = Column(String(20))
    afiliado_nombre  = Column(String(150))
    tipo             = Column(String(80))
    descripcion      = Column(Text)
    estado           = Column(String(20), default="pendiente", index=True)  # pendiente | atendido
    respuesta        = Column(Text, nullable=True)
    creado           = Column(DateTime, default=_utcnow)


class NovedadPago(Base):
    __tablename__ = "novedades_pago"
    id               = Column(Integer, primary_key=True, index=True)
    cliente_ref      = Column(String(120), index=True)
    username_cliente = Column(String(60), index=True)
    mes              = Column(String(20))
    anio             = Column(String(4))
    afiliados_docs   = Column(Text)    # JSON list de docs
    afiliados_nombres= Column(Text)    # JSON list de nombres
    obs              = Column(Text, default="")
    estado           = Column(String(20), default="pendiente", index=True)  # pendiente | procesado
    respuesta        = Column(Text, nullable=True)
    creado           = Column(DateTime, default=_utcnow)


class SolicitudRetiro(Base):
    __tablename__ = "solicitudes_retiro"
    id               = Column(Integer, primary_key=True, index=True)
    cliente_ref      = Column(String(120), index=True)
    username_cliente = Column(String(60), index=True)
    afiliado_doc     = Column(String(20))
    afiliado_nombre  = Column(String(150))
    motivo           = Column(String(200))
    obs              = Column(Text, default="")
    estado           = Column(String(20), default="pendiente", index=True)  # pendiente | ejecutado | rechazado
    respuesta        = Column(Text, nullable=True)
    creado           = Column(DateTime, default=_utcnow)


class Actividad(Base):
    __tablename__ = "actividad"
    __table_args__ = (
        Index('ix_actividad_usuario_modulo', 'usuario', 'modulo'),
        Index('ix_actividad_fecha', 'fecha'),
    )
    id      = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(60))
    accion  = Column(String(200))
    modulo  = Column(String(60))
    detalle = Column(String(200))
    fecha   = Column(DateTime, default=_utcnow)

class Tarea(Base):
    __tablename__ = "tareas"
    __table_args__ = (
        Index('ix_tarea_estado_asignado', 'estado', 'asignado_a'),  # tareas activas por usuario
    )
    id            = Column(Integer, primary_key=True)
    titulo        = Column(String(200))
    descripcion   = Column(Text, default="")
    asignado_a    = Column(String(60), index=True)
    creado_por    = Column(String(60), index=True)
    estado        = Column(String(20), default="pendiente", index=True)  # pendiente|en_proceso|completada|finalizada
    fecha_limite  = Column(String(10), nullable=True)
    privada       = Column(Boolean, default=False)
    creado        = Column(DateTime, default=_utcnow)
    completado_en = Column(DateTime, nullable=True)
    finalizado_en = Column(DateTime, nullable=True)
    finalizado_por= Column(String(60), nullable=True)

class TareaComentario(Base):
    __tablename__ = "tarea_comentarios"
    id       = Column(Integer, primary_key=True)
    tarea_id = Column(Integer, index=True)
    usuario  = Column(String(60))
    texto    = Column(Text)
    creado   = Column(DateTime, default=_utcnow)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id             = Column(Integer, primary_key=True)
    ip             = Column(String(45), unique=True, index=True)
    count          = Column(Integer, default=0)
    last_attempt   = Column(Float, default=0.0)

class Notificacion(Base):
    __tablename__ = "notificaciones"
    __table_args__ = (
        Index('ix_notificacion_usuario_leida', 'usuario', 'leida'),  # no leídas por usuario
    )
    id       = Column(Integer, primary_key=True)
    usuario  = Column(String(60), index=True)
    mensaje  = Column(String(300))
    leida    = Column(Boolean, default=False, index=True)
    tarea_id = Column(Integer, nullable=True)
    creado   = Column(DateTime, default=_utcnow)

class PlanillaPago(Base):
    __tablename__ = "planillas_pago"
    __table_args__ = (
        Index('ix_planilla_cliente_anio_mes', 'cliente_ref', 'anio', 'mes'),
    )
    id           = Column(Integer, primary_key=True, index=True)
    cliente_ref  = Column(String(150), index=True)     # cliente_txt del afiliado
    mes          = Column(String(20))                   # "Enero", "Febrero"...
    anio         = Column(String(4))                    # "2026"
    observaciones= Column(Text, default="")
    subido_por   = Column(String(60))
    creado       = Column(DateTime, default=_utcnow)

class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (
        Index('ix_documento_contexto_id', 'contexto', 'contexto_id'),
    )
    id           = Column(Integer, primary_key=True, index=True)
    upload_id    = Column(String(36), unique=True, nullable=True, index=True)  # UUID idempotency key
    afiliado_doc = Column(String(20), index=True)       # doc del afiliado dueño
    nombre       = Column(String(200))                   # nombre original del archivo
    tipo         = Column(String(20))                    # extension: pdf, jpg, png, docx, xlsx
    ruta         = Column(String(500))                   # path relativo en backend/uploads/
    tamano       = Column(Integer, default=0)            # bytes
    subido_por   = Column(String(60))
    contexto     = Column(String(60), default="afiliado") # afiliado | tarea | novedad_portal
    contexto_id  = Column(Integer, nullable=True)        # id de tarea o solicitud si aplica
    creado       = Column(DateTime, default=_utcnow)

class Mensaje(Base):
    __tablename__ = "mensajes"
    __table_args__ = (
        Index('ix_mensaje_tipo_creado', 'tipo', 'creado'),
        Index('ix_mensaje_destinatario_leido', 'destinatario', 'leido'),
    )
    id               = Column(Integer, primary_key=True, index=True)
    tipo             = Column(String(10), index=True)      # "grupal" | "privado"
    remitente        = Column(String(60), index=True)      # username
    remitente_nombre = Column(String(120))
    destinatario     = Column(String(120), nullable=True)  # cliente_ref (solo privado)
    texto            = Column(Text)
    creado           = Column(DateTime, default=_utcnow, index=True)
    leido            = Column(Boolean, default=False)      # solo aplica a mensajes privados


class AvisoCliente(Base):
    """Avisos/comunicados que el admin envía a un cliente específico."""
    __tablename__ = "avisos_clientes"
    __table_args__ = (
        Index('ix_aviso_cliente_ref', 'cliente_ref'),
    )
    id          = Column(Integer, primary_key=True, index=True)
    cliente_ref = Column(String(120), index=True)   # destinatario (cliente_txt / cliente_ref)
    titulo      = Column(String(200))
    mensaje     = Column(Text)
    leido       = Column(Boolean, default=False)
    creado_por  = Column(String(60))
    creado      = Column(DateTime, default=_utcnow)


class TokenBlacklist(Base):
    """Refresh tokens invalidados explícitamente (logout o rotation)."""
    __tablename__ = "token_blacklist"
    id         = Column(Integer, primary_key=True, index=True)
    jti        = Column(String(64), unique=True, index=True)        # JWT ID único
    expires_at = Column(DateTime(timezone=True))                    # timezone=True evita bugs de comparación en PostgreSQL
    creado     = Column(DateTime(timezone=True), default=_utcnow)

class SeguimientoArl(Base):
    __tablename__ = "seguimiento_arl"
    __table_args__ = (
        Index('ix_seg_arl_cliente_estado', 'cliente', 'estado'),
    )
    id               = Column(Integer, primary_key=True, index=True)
    nombre           = Column(String(120), nullable=False)
    documento        = Column(String(30), nullable=False)
    cliente          = Column(String(150), index=True)
    empresa          = Column(String(120))
    fecha_afiliacion = Column(String(20))   # 'YYYY-MM-DD'
    nivel_arl        = Column(String(10), default='N/A')
    observaciones    = Column(Text, nullable=True)
    estado           = Column(String(20), default='activo')  # activo | retirar | retirado
    creado_en        = Column(DateTime, default=_utcnow)
