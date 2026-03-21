from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class AfiliadoCreate(BaseModel):
    nombre: str
    tipo_doc: str = "CC"
    doc: str
    empresa: str = ""
    cargo: str = ""
    cliente_txt: str = ""
    eps: str = ""
    arl: str = ""
    ccf: str = ""
    afp: str = ""
    subtipo: str = "0"
    estado: str = "ACTIVO"
    estado_srv: str = "ACTIVO"
    servicios: List[str] = []
    tel: str = ""
    email: str = ""
    dir: str = ""
    obs: str = ""
    novedades: str = ""
    ibc: Optional[float] = None
    fecha_ingreso: str = ""
    fecha_afiliacion: str = ""
    registrado_por: str = ""

class FacturaCreate(BaseModel):
    codigo: str = ""
    nombre_afiliado: str = ""
    doc: str = ""
    cliente: str = ""
    anio: str = ""
    mes: str = ""
    periodo: str = "30"
    estado: str = "pendiente"
    banco: str = ""
    ingresos: float = 0
    costos: float = 0
    costo_adm: float = 0
    conceptos_extra: float = 0
    utilidad: float = 0
    novedades: str = ""
    servicios_detalle: List[Any] = []
    conceptos_detalle: List[Any] = []
    creado_por: str = ""

class FacturaUpdate(BaseModel):
    cliente: Optional[str] = None
    mes: Optional[str] = None
    anio: Optional[str] = None
    periodo: Optional[str] = None
    estado: Optional[str] = None
    banco: Optional[str] = None
    ingresos: Optional[float] = None
    costos: Optional[float] = None
    costo_adm: Optional[float] = None
    conceptos_extra: Optional[float] = None
    utilidad: Optional[float] = None
    novedades: Optional[str] = None
    servicios_detalle: Optional[List[Any]] = None
    conceptos_detalle: Optional[List[Any]] = None

class RetiroCreate(BaseModel):
    doc: str
    fecha: str
    motivo: str
    obs: str = ""
    registrado_por: str = ""

class EmpleadoCreate(BaseModel):
    nombre: str
    doc: str = ""
    cargo: str = ""
    tel: str = ""
    email: str = ""
    usuario: str = ""
    nomina: float = 0
    activo: bool = True
    fecha_ingreso: str = ""

class NominaUpdate(BaseModel):
    nomina: float

class GastoCreate(BaseModel):
    nombre: str
    valor: float

class UsuarioCreate(BaseModel):
    nombre: str
    username: str
    password: str
    rol: str = "empleado"

    @field_validator('password')
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

class ConfigUpdate(BaseModel):
    ibc_global: Optional[float] = None
    porcentajes: Optional[dict] = None
    plantilla_whatsapp: Optional[str] = None

class ListaUpdate(BaseModel):
    items: List[str]

class TareaCreate(BaseModel):
    titulo: str
    descripcion: str = ""
    asignado_a: str
    creado_por: str = ""

class TareaComentarioCreate(BaseModel):
    texto: str
    usuario: str = ""
