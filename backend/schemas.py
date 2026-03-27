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
    detalle: str = ""
    ibc: Optional[float] = None
    fecha_ingreso: str = ""
    fecha_afiliacion: str = ""
    registrado_por: str = ""

    @field_validator('empresa', 'cargo', 'cliente_txt', 'eps', 'arl', 'ccf', 'afp',
                     'subtipo', 'tel', 'email', 'dir', 'obs', 'novedades', 'detalle',
                     'fecha_ingreso', 'fecha_afiliacion', 'registrado_por', mode='before')
    @classmethod
    def none_to_str(cls, v):
        return v if v is not None else ""

class FacturaCreate(BaseModel):
    codigo: str = ""
    nombre_afiliado: str = ""
    doc: str
    cliente: str = ""
    anio: str = ""
    mes: str

    @field_validator('doc', 'mes', mode='before')
    @classmethod
    def no_vacio(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f'{info.field_name} es requerido y no puede estar vacío')
        return v
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

    @field_validator('ingresos', 'costos', 'costo_adm', 'conceptos_extra', mode='before')
    @classmethod
    def no_negativos(cls, v):
        if v is not None and v < 0:
            raise ValueError('El valor no puede ser negativo')
        return v or 0

    @field_validator('estado', mode='before')
    @classmethod
    def estado_valido(cls, v):
        if v is not None and v not in ('pendiente', 'pagado'):
            raise ValueError('Estado debe ser "pendiente" o "pagado"')
        return v or 'pendiente'

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

    @field_validator('ingresos', 'costos', 'costo_adm', 'conceptos_extra', mode='before')
    @classmethod
    def no_negativos(cls, v):
        if v is not None and v < 0:
            raise ValueError('El valor no puede ser negativo')
        return v

    @field_validator('estado', mode='before')
    @classmethod
    def estado_valido(cls, v):
        if v is not None and v not in ('pendiente', 'pagado'):
            raise ValueError('Estado debe ser "pendiente" o "pagado"')
        return v

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
    cliente_ref: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

    @field_validator('rol')
    @classmethod
    def rol_valido(cls, v):
        if v not in ('admin', 'empleado', 'cliente'):
            raise ValueError('Rol debe ser admin, empleado o cliente')
        return v


class SolicitudNovedadCreate(BaseModel):
    afiliado_doc: str
    tipo: str
    descripcion: str


class NovedadPagoCreate(BaseModel):
    mes: str
    anio: str
    afiliados_docs: List[str]
    obs: str = ""


class SolicitudRetiroCreate(BaseModel):
    afiliado_doc: str
    motivo: str
    obs: str = ""

class ConfigUpdate(BaseModel):
    ibc_global: Optional[float] = None
    porcentajes: Optional[dict] = None
    plantilla_whatsapp: Optional[str] = None
    cargo_adicional: Optional[float] = None

class ListaUpdate(BaseModel):
    items: List[str]

class TareaCreate(BaseModel):
    titulo: str
    descripcion: str = ""
    asignado_a: str
    creado_por: str = ""
    fecha_limite: str = ""

class TareaComentarioCreate(BaseModel):
    texto: str
    usuario: str = ""
