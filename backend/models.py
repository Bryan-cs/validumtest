from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Usuario(Base):
    __tablename__ = "usuarios"
    id       = Column(Integer, primary_key=True, index=True)
    nombre   = Column(String(120))
    username = Column(String(60), unique=True, index=True)
    password = Column(String(120), nullable=True)
    rol      = Column(String(20), default="empleado")   # admin | empleado
    activo   = Column(Boolean, default=True)
    creado   = Column(DateTime, default=datetime.utcnow)

class Afiliado(Base):
    __tablename__ = "afiliados"
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
    subtipo         = Column(String(10), index=True)       # índice para filtros frecuentes
    estado          = Column(String(30), default="ACTIVO", index=True)
    estado_srv      = Column(String(50), default="ACTIVO", index=True)
    servicios       = Column(Text, default="[]")     # JSON list
    tel             = Column(String(20))
    email           = Column(String(100))
    dir             = Column(String(200))
    obs             = Column(Text)
    novedades       = Column(Text)
    ibc             = Column(Float, nullable=True)   # IBC individual (None = usar global)
    fecha_ingreso   = Column(String(10))
    fecha_afiliacion= Column(String(10))
    registrado_por  = Column(String(60))
    activo          = Column(Boolean, default=True)
    creado          = Column(DateTime, default=datetime.utcnow)
    actualizado     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Factura(Base):
    __tablename__ = "facturas"
    id               = Column(Integer, primary_key=True, index=True)
    codigo           = Column(String(20), unique=True, index=True)
    nombre_afiliado  = Column(String(150), index=True)
    doc              = Column(String(20), index=True)   # doc del afiliado
    cliente          = Column(String(120), index=True)
    anio             = Column(String(4), index=True)
    mes              = Column(String(20), index=True)
    periodo          = Column(String(5))
    estado           = Column(String(20), default="pendiente", index=True)  # índice para filtros
    banco            = Column(String(60))
    ingresos         = Column(Float, default=0)
    costos           = Column(Float, default=0)
    costo_adm        = Column(Float, default=0)
    conceptos_extra  = Column(Float, default=0)
    utilidad         = Column(Float, default=0)
    novedades        = Column(Text)
    servicios_detalle= Column(Text, default="[]")   # JSON
    conceptos_detalle= Column(Text, default="[]")   # JSON
    afiliado_eliminado = Column(Boolean, default=False)
    creado_por       = Column(String(60))
    creado           = Column(DateTime, default=datetime.utcnow)
    actualizado      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Retiro(Base):
    __tablename__ = "retiros"
    id              = Column(Integer, primary_key=True, index=True)
    nombre          = Column(String(150))
    doc             = Column(String(20), index=True)
    empresa         = Column(String(80))
    fecha           = Column(String(10))
    motivo          = Column(String(50))
    obs             = Column(Text)
    mes             = Column(String(20))
    anio            = Column(String(4))
    registrado_por  = Column(String(60))
    creado          = Column(DateTime, default=datetime.utcnow)

class Eliminado(Base):
    __tablename__ = "eliminados"
    id                  = Column(Integer, primary_key=True, index=True)
    nombre              = Column(String(150))
    doc                 = Column(String(20))
    empresa             = Column(String(80))
    datos_completos     = Column(Text)    # JSON snapshot del afiliado
    fecha_eliminacion   = Column(String(10))
    mes                 = Column(String(20))
    eliminado_por       = Column(String(60))
    creado              = Column(DateTime, default=datetime.utcnow)

class Empleado(Base):
    __tablename__ = "empleados"
    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(String(150))
    doc           = Column(String(20))
    cargo         = Column(String(80))
    tel           = Column(String(20))
    email         = Column(String(100))
    usuario       = Column(String(60))     # username asignado
    nomina        = Column(Float, default=0)
    activo        = Column(Boolean, default=True)
    fecha_ingreso = Column(String(10))
    creado        = Column(DateTime, default=datetime.utcnow)

class Gasto(Base):
    __tablename__ = "gastos"
    id      = Column(Integer, primary_key=True, index=True)
    nombre  = Column(String(120))
    valor   = Column(Float, default=0)
    activo  = Column(Boolean, default=True)
    creado  = Column(DateTime, default=datetime.utcnow)

class Config(Base):
    __tablename__ = "config"
    id                 = Column(Integer, primary_key=True, default=1)
    ibc_global         = Column(Float, default=1_950_905)
    porcentajes        = Column(Text)    # JSON dict
    plantilla_whatsapp = Column(Text)    # Plantilla del mensaje de WhatsApp

class Lista(Base):
    __tablename__ = "listas"
    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(60), unique=True)
    items  = Column(Text)    # JSON list

class Actividad(Base):
    __tablename__ = "actividad"
    id      = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(60))
    accion  = Column(String(200))
    modulo  = Column(String(60))
    detalle = Column(String(200))
    fecha   = Column(DateTime, default=datetime.utcnow)

class Tarea(Base):
    __tablename__ = "tareas"
    id            = Column(Integer, primary_key=True)
    titulo        = Column(String(200))
    descripcion   = Column(Text, default="")
    asignado_a    = Column(String(60), index=True)
    creado_por    = Column(String(60))
    estado        = Column(String(20), default="pendiente", index=True)
    creado        = Column(DateTime, default=datetime.utcnow)
    completado_en = Column(DateTime, nullable=True)

class TareaComentario(Base):
    __tablename__ = "tarea_comentarios"
    id       = Column(Integer, primary_key=True)
    tarea_id = Column(Integer, index=True)
    usuario  = Column(String(60))
    texto    = Column(Text)
    creado   = Column(DateTime, default=datetime.utcnow)

class Notificacion(Base):
    __tablename__ = "notificaciones"
    id       = Column(Integer, primary_key=True)
    usuario  = Column(String(60), index=True)
    mensaje  = Column(String(300))
    leida    = Column(Boolean, default=False)
    tarea_id = Column(Integer, nullable=True)
    creado   = Column(DateTime, default=datetime.utcnow)
