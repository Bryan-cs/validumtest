from pydantic import BaseModel, field_validator
from typing import Optional, List, Any, Literal
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = True

class AfiliadoCreate(BaseModel):
    nombre: str
    tipo_doc: str = "CC"
    doc: str

    @field_validator('doc', mode='before')
    @classmethod
    def doc_no_vacio(cls, v):
        if not v or not str(v).strip():
            raise ValueError('Documento es requerido')
        return str(v).strip()
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
    ciudad: str = ""
    novedades: str = ""
    detalle: str = ""
    ibc: Optional[float] = None
    fecha_ingreso: str = ""

    @field_validator('ibc', mode='before')
    @classmethod
    def ibc_positivo(cls, v):
        if v is not None and float(v) <= 0:
            raise ValueError('IBC debe ser mayor a 0')
        SMMLV_VALUE = 1_300_000
        if v is not None and float(v) > 0 and float(v) < SMMLV_VALUE:
            raise ValueError(f'IBC no puede ser menor al SMMLV')
        return v
    fecha_afiliacion: str
    registrado_por: str = ""

    @field_validator('empresa', 'cargo', 'cliente_txt', 'eps', 'arl', 'ccf', 'afp',
                     'subtipo', 'tel', 'email', 'dir', 'novedades', 'detalle',
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
        if v is not None and v != 'pendiente':
            raise ValueError('Estado en creación debe ser "pendiente"')
        return 'pendiente'

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
        if v is not None and v not in ('pendiente', 'pagado', 'planilla_pagada'):
            raise ValueError('Estado debe ser "pendiente", "pagado" o "planilla_pagada"')
        return v

class RetiroCreate(BaseModel):
    doc: str
    fecha: str
    motivo: str
    obs: str = ""
    registrado_por: str = ""

    @field_validator('fecha', mode='before')
    @classmethod
    def fecha_formato(cls, v):
        if not v or not str(v).strip():
            raise ValueError('Fecha es requerida')
        return str(v).strip()

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

class IngresoAdicionalCreate(BaseModel):
    concepto: str
    descripcion: str = ""
    valor: float
    mes: int
    anio: int


class GastoCreate(BaseModel):
    nombre: str
    valor: float
    mes: int
    anio: int

class GastoUpdate(BaseModel):
    nombre: Optional[str] = None
    valor: Optional[float] = None
    mes: Optional[int] = None
    anio: Optional[int] = None

class NominaItemUpdate(BaseModel):
    valor: float

class CopiarMesRequest(BaseModel):
    mes_origen: int
    anio_origen: int
    mes_destino: int
    anio_destino: int

class UsuarioPasswordUpdate(BaseModel):
    password: str

    @field_validator('password')
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v


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
    mes_inicio_cobro: Optional[int] = None
    anio_inicio_cobro: Optional[int] = None

    @field_validator('ibc_global', 'cargo_adicional', mode='before')
    @classmethod
    def no_negativos(cls, v):
        if v is not None and v < 0:
            raise ValueError('El valor no puede ser negativo')
        return v

    @field_validator('ibc_global', mode='before')
    @classmethod
    def validar_ibc_global(cls, v):
        SMMLV_VALUE = 1_300_000
        if v is not None and 0 < v < SMMLV_VALUE:
            raise ValueError(f'ibc_global no puede ser menor al SMMLV ({SMMLV_VALUE:,})')
        return v

    @field_validator('porcentajes', mode='before')
    @classmethod
    def validar_porcentajes(cls, v):
        if v is None:
            return v
        TOPES = {
            "EPS":   0.125,
            "AFP":   0.16,
            "CCF":   0.04,
            "ARL 1": 0.00522,
            "ARL 2": 0.01044,
            "ARL 3": 0.02436,
            "ARL 4": 0.04350,
            "ARL 5": 0.06960,
        }
        ELIMINADAS = {"FSP", "SENA", "ICBF"}
        errores = []
        for clave, valor in v.items():
            clave_upper = clave.strip().upper()
            if clave_upper in ELIMINADAS:
                errores.append(f"'{clave}' ya no es un porcentaje válido")
                continue
            if clave_upper not in TOPES:
                errores.append(f"Clave desconocida: '{clave}'")
                continue
            tope = TOPES[clave_upper]
            if valor < 0 or valor > tope:
                errores.append(f"{clave_upper} debe estar entre 0 y {tope} (recibido: {valor})")
        if errores:
            raise ValueError('; '.join(errores))
        return v

class ListaUpdate(BaseModel):
    items: List[str]

class TareaCreate(BaseModel):
    titulo: str
    descripcion: str = ""
    asignado_a: str
    creado_por: str = ""
    fecha_limite: str = ""
    privada: bool = False

class TareaUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_limite: Optional[str] = None
    asignado_a: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None

class TareaComentarioCreate(BaseModel):
    texto: str
    usuario: str = ""

class EstadoSolicitudBody(BaseModel):
    estado: Literal["pendiente", "procesado", "atendido", "ejecutado", "rechazado"]
    respuesta: Optional[str] = None

class AvisoClienteCreate(BaseModel):
    cliente_ref: str
    titulo: str
    mensaje: str

class SeguimientoArlCreate(BaseModel):
    nombre: str
    documento: str
    cliente: str = ""
    empresa: str = ""
    fecha_afiliacion: str = ""   # 'YYYY-MM-DD'
    entidad_arl: str = "SURA"   # SURA | POSITIVA
    nivel_arl: str = "N/A"
    observaciones: Optional[str] = None

class SeguimientoArlUpdate(BaseModel):
    nombre: Optional[str] = None
    documento: Optional[str] = None
    cliente: Optional[str] = None
    empresa: Optional[str] = None
    fecha_afiliacion: Optional[str] = None
    entidad_arl: Optional[str] = None
    nivel_arl: Optional[str] = None
    observaciones: Optional[str] = None
    estado: Optional[str] = None

class BulkEstadoBody(BaseModel):
    ids: List[int]
    estado: str

class CredencialCreate(BaseModel):
    tipo_doc: str = "NIT"
    numero_doc: str = ""
    titular: str = ""
    portal: str
    entidad: str = ""
    usuario_portal: str
    clave_portal: str
    obs: str = ""

    @field_validator('usuario_portal', 'clave_portal', 'portal', mode='before')
    @classmethod
    def no_vacio(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f'{info.field_name} es requerido')
        return str(v).strip()

class CredencialUpdate(BaseModel):
    tipo_doc: Optional[str] = None
    numero_doc: Optional[str] = None
    titular: Optional[str] = None
    portal: Optional[str] = None
    entidad: Optional[str] = None
    usuario_portal: Optional[str] = None
    clave_portal: Optional[str] = None
    obs: Optional[str] = None
