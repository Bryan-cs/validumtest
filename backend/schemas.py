from pydantic import BaseModel, field_validator, model_validator
from typing import ClassVar
from functools import lru_cache
from typing import Optional, List, Any, Literal
from datetime import datetime
import re as _re

_DATE_RE = _re.compile(r'^\d{4}-\d{2}-\d{2}$')


@lru_cache(maxsize=None)
def _largos_columna(modelo: str) -> dict:
    """Largo maximo de cada columna String del modelo SQLAlchemy indicado.

    Se lee del modelo en vez de repetir max_length campo por campo: asi la
    validacion no se desincroniza si alguien cambia una columna.
    """
    import models
    tabla = getattr(models, modelo).__table__
    return {c.name: c.type.length for c in tabla.columns
            if getattr(c.type, "length", None)}


class LargosDeColumna(BaseModel):
    """Rechaza strings mas largos que su columna, con 422 y mensaje preciso.

    Sin esto el valor viajaba hasta Postgres y volvia como DataError, que el
    handler global de main.py convierte en un 422 generico ("algun valor excede
    el largo permitido"). Aca se sabe QUE campo y CUANTO sobra.
    """
    _MODELO: ClassVar[str] = ""

    @model_validator(mode="after")
    def _verificar_largos(self):
        if not self._MODELO:
            return self
        limites = _largos_columna(self._MODELO)
        for campo, valor in self.__dict__.items():
            tope = limites.get(campo)
            if tope and isinstance(valor, str) and len(valor) > tope:
                raise ValueError(
                    f"{campo}: maximo {tope} caracteres (recibidos {len(valor)})")
        return self

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = True

class AfiliadoCreate(LargosDeColumna):
    _MODELO: ClassVar[str] = "Afiliado"
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
    fecha_expedicion: str = ""

    # ── Datos PILA (Anexo Tecnico 2, registro tipo 2) ────────────────────────
    # Todos opcionales y sin default util a proposito: el formulario viejo no
    # los manda, y si llegaran con "" el update los escribiria igual y borraria
    # los codigos de quien ya los tiene. `update_afiliado` solo aplica los que
    # vengan de verdad en el payload.
    primer_apellido: Optional[str] = None
    segundo_apellido: Optional[str] = None
    primer_nombre: Optional[str] = None
    segundo_nombre: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    sexo: Optional[str] = None
    tipo_cotizante: Optional[str] = None
    subtipo_cotizante: Optional[str] = None
    extranjero_no_pension: Optional[bool] = None
    colombiano_exterior: Optional[bool] = None
    cod_depto_labor: Optional[str] = None
    cod_municipio_labor: Optional[str] = None
    cod_eps: Optional[str] = None
    cod_afp: Optional[str] = None
    cod_ccf: Optional[str] = None
    cod_arl: Optional[str] = None
    clase_riesgo: Optional[str] = None
    tarifa_arl: Optional[float] = None
    tipo_salario: Optional[str] = None
    salario_basico: Optional[float] = None
    centro_trabajo: Optional[str] = None
    cotizante_principal_tipo_doc: Optional[str] = None
    cotizante_principal_doc: Optional[str] = None
    horas_laboradas: Optional[int] = None

    @field_validator('ibc', mode='before')
    @classmethod
    def ibc_positivo(cls, v):
        if v is None:
            return v
        # float() sobre list/dict lanza TypeError, y Pydantic v2 solo traduce
        # ValueError/AssertionError a error de validacion: el TypeError se escapaba
        # del handler y salia como 500 en vez de 422.
        try:
            valor = float(v)
        except (TypeError, ValueError):
            raise ValueError('IBC debe ser un numero')
        if valor <= 0:
            raise ValueError('IBC debe ser mayor a 0')
        SMMLV_VALUE = 1_300_000
        if valor < SMMLV_VALUE:
            raise ValueError('IBC no puede ser menor al SMMLV')
        return v
    fecha_afiliacion: str
    registrado_por: str = ""

    @field_validator('empresa', 'cargo', 'cliente_txt', 'eps', 'arl', 'ccf', 'afp',
                     'subtipo', 'tel', 'email', 'dir', 'novedades', 'detalle',
                     'fecha_ingreso', 'fecha_afiliacion', 'registrado_por', mode='before')
    @classmethod
    def none_to_str(cls, v):
        return v if v is not None else ""

    @field_validator('fecha_afiliacion', 'fecha_ingreso')
    @classmethod
    def fecha_formato(cls, v, info):
        if not v:
            return v
        if not _DATE_RE.match(v):
            raise ValueError(f'{info.field_name}: formato inválido, use YYYY-MM-DD')
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f'{info.field_name}: fecha inválida ({v})')
        return v

class FacturaCreate(LargosDeColumna):
    _MODELO: ClassVar[str] = "Factura"
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

class FacturaUpdate(LargosDeColumna):
    _MODELO: ClassVar[str] = "Factura"
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

class RetiroCreate(LargosDeColumna):
    _MODELO: ClassVar[str] = "Retiro"
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
        v = str(v).strip()
        # Mismo criterio que AfiliadoCreate y SeguimientoArlCreate. Antes aceptaba
        # cualquier texto: "9999-99-99" entraba como 201, y un valor de mas de 10
        # caracteres reventaba contra la columna String(10) como 500.
        if not _DATE_RE.match(v):
            raise ValueError('fecha: formato inválido, use YYYY-MM-DD')
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f'fecha: fecha inválida ({v})')
        return v

class EmpleadoCreate(LargosDeColumna):
    _MODELO: ClassVar[str] = "Empleado"
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

class SeguimientoArlCreate(LargosDeColumna):
    _MODELO: ClassVar[str] = "SeguimientoArl"
    nombre: str
    documento: str
    cliente: str = ""
    empresa: str = ""
    fecha_afiliacion: str = ""   # 'YYYY-MM-DD'
    entidad_arl: str = "SURA"   # SURA | POSITIVA
    nivel_arl: str = "N/A"
    tipo_afiliado: str = "dependiente"   # dependiente | independiente
    observaciones: Optional[str] = None

    @field_validator('fecha_afiliacion')
    @classmethod
    def fecha_formato(cls, v):
        if not v:
            return v
        if not _DATE_RE.match(v):
            raise ValueError(f'fecha_afiliacion: formato inválido, use YYYY-MM-DD')
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f'fecha_afiliacion: fecha inválida ({v})')
        return v

class SeguimientoArlUpdate(LargosDeColumna):
    _MODELO: ClassVar[str] = "SeguimientoArl"
    nombre: Optional[str] = None
    documento: Optional[str] = None
    cliente: Optional[str] = None
    empresa: Optional[str] = None
    fecha_afiliacion: Optional[str] = None
    entidad_arl: Optional[str] = None
    nivel_arl: Optional[str] = None
    tipo_afiliado: Optional[str] = None
    observaciones: Optional[str] = None
    estado: Optional[str] = None

    @field_validator('fecha_afiliacion')
    @classmethod
    def fecha_formato(cls, v):
        if not v:
            return v
        if not _DATE_RE.match(v):
            raise ValueError(f'fecha_afiliacion: formato inválido, use YYYY-MM-DD')
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f'fecha_afiliacion: fecha inválida ({v})')
        return v

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



# ── PILA: aportantes ─────────────────────────────────────────────────────────
class AportanteCreate(BaseModel):
    """Empresa aportante. `cliente_ref` enlaza con el `cliente_txt` de los afiliados.

    El `dv` se calcula solo si no se envía; si se envía, se valida. Un NIT con
    dígito errado lo rechaza el operador después de haber liquidado todo.
    """
    cliente_ref: str
    razon_social: str
    tipo_doc: str = "NI"
    num_doc: str
    dv: Optional[str] = None
    tipo_persona: str = "J"
    tipo_aportante: Optional[str] = None
    clase_aportante: Optional[str] = None
    cod_arl: Optional[str] = None
    clase_riesgo: Optional[str] = None
    actividad_economica: Optional[str] = None
    cod_depto: Optional[str] = None
    cod_municipio: Optional[str] = None
    cod_sucursal: Optional[str] = None
    nombre_sucursal: Optional[str] = None
    exonerado_parafiscales: bool = False
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None

    @field_validator('cliente_ref', 'razon_social', 'num_doc', mode='before')
    @classmethod
    def no_vacio(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f'{info.field_name} es requerido')
        return str(v).strip()

    @field_validator('num_doc', mode='after')
    @classmethod
    def solo_digitos(cls, v):
        limpio = v.replace(".", "").replace("-", "").replace(" ", "")
        if not limpio.isdigit():
            raise ValueError('num_doc debe contener solo dígitos')
        return limpio


class AportanteUpdate(BaseModel):
    cliente_ref: Optional[str] = None
    razon_social: Optional[str] = None
    tipo_doc: Optional[str] = None
    num_doc: Optional[str] = None
    dv: Optional[str] = None
    tipo_persona: Optional[str] = None
    tipo_aportante: Optional[str] = None
    clase_aportante: Optional[str] = None
    cod_arl: Optional[str] = None
    clase_riesgo: Optional[str] = None
    actividad_economica: Optional[str] = None
    cod_depto: Optional[str] = None
    cod_municipio: Optional[str] = None
    cod_sucursal: Optional[str] = None
    nombre_sucursal: Optional[str] = None
    exonerado_parafiscales: Optional[bool] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    activo: Optional[bool] = None



class LiquidacionRequest(BaseModel):
    """Qué liquidar: un afiliado y un período de cotización.

    La planilla es de una persona. El aportante que va en el encabezado se
    deduce del cliente del afiliado, no se envía.
    """
    afiliado_id: int
    anio: int
    mes: int
    tipo_planilla: str = "E"
    operador: Optional[str] = None

    @field_validator('mes')
    @classmethod
    def mes_valido(cls, v):
        if not 1 <= v <= 12:
            raise ValueError('mes debe estar entre 1 y 12')
        return v

    @field_validator('anio')
    @classmethod
    def anio_valido(cls, v):
        if not 2010 <= v <= 2100:
            raise ValueError('año fuera de rango')
        return v


# ── Multi-tenant: Organizaciones (gestionadas por el superadmin) ──────────────
class OrganizacionCreate(BaseModel):
    """Crea una organización nueva + su usuario admin inicial."""
    nombre: str
    slug: Optional[str] = None            # si no se envía, se deriva del nombre
    admin_username: str
    admin_password: str
    admin_nombre: Optional[str] = None

    @field_validator('nombre', 'admin_username', mode='before')
    @classmethod
    def no_vacio(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f'{info.field_name} es requerido')
        return str(v).strip()

    @field_validator('admin_password')
    @classmethod
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v


class OrganizacionUpdate(BaseModel):
    nombre: Optional[str] = None
    slug: Optional[str] = None
    activo: Optional[bool] = None
    precio_afiliado: Optional[float] = None   # COP por afiliado activo/mes

    @field_validator('precio_afiliado')
    @classmethod
    def precio_no_negativo(cls, v):
        if v is not None and v < 0:
            raise ValueError('El precio por afiliado no puede ser negativo')
        return v


class OrganizacionOut(BaseModel):
    id: int
    nombre: str
    slug: Optional[str] = None
    activo: bool
    total_usuarios: Optional[int] = None
    total_afiliados: Optional[int] = None
