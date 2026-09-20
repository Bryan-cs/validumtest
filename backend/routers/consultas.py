"""Consultas a fuentes oficiales de seguridad social.

Patron proxy: el browser nunca habla con la fuente. El backend mantiene la
sesion, el ViewState y las cookies; el frontend solo ve la imagen del captcha y
los datos ya normalizados.

Flujo de dos pasos (lo impone el captcha de la fuente):

    POST /consultas/adres/iniciar   {tipo_doc, doc}
        -> si hay consulta fresca en cache: {cacheado: true, datos: {...}}
        -> si no:                           {session_id, captcha, expira_seg}

    POST /consultas/adres/resolver  {session_id, captcha}
        -> {datos: {...}, sugerencia: {...}}

El captcha lo escribe SIEMPRE el empleado que esta haciendo el alta. No hay
resolucion automatica ni consultas en lote: una consulta = un captcha = una
persona.

Multi-tenant
------------
`ConsultaExterna` lleva `organizacion_id` y entra en el auto-filtro de
`tenant.py`, asi que el cache queda acotado a la organizacion activa. Es
deliberado: una organizacion no puede ver a quien consulto otra, ni reutilizar
un resultado que otra obtuvo con la autorizacion de su propio titular. Repetir
el mismo documento desde otra organizacion cuesta un captcha nuevo.

La sesion intermedia tambien guarda la organizacion y se verifica al resolver,
para que nadie complete una consulta iniciada por otra organizacion.

Habeas data (Ley 1581/2012): el estado de afiliacion en salud es dato sensible.
Cada consulta queda registrada en `consultas_externas` y en `Actividad` con el
usuario que la hizo. A diferencia del resto del sistema, aqui el admin NO se
suprime del log.
"""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from crud_cache import _cache_get, _cache_set
from database import get_db
from services.consultas.adres import (
    CaptchaIncorrecto,
    ConsultaADRES,
    ErrorConsulta,
    EstadoConsulta,
    FuenteNoDisponible,
    SinResultados,
    captcha_a_data_url,
)
from services.consultas.ruaf import ConsultaRUAF, EstadoRuaf
from tenant import current_org_id

from .deps import require_admin_or_empleado

router = APIRouter(prefix="/consultas", tags=["consultas"])

# La sesion con ADRES (cookies + ViewState) caduca rapido del lado de ellos.
TTL_SESION_SEG = 300
# Una afiliacion cambia por periodo de cotizacion, no por hora.
TTL_RESULTADO_DIAS = int(os.getenv("CONSULTAS_TTL_DIAS", "30"))

CONSULTAS_ENABLED = os.getenv("CONSULTAS_ENABLED", "true").lower() != "false"

# RUAF APAGADO POR DEFECTO.
#
# Verificado el 2026-09-20 con una sonda desde us-east4: todo el dominio
# sispro.gov.co (RUAF incluido) descarta los paquetes desde la red de Railway —
# 25 s de timeout sin respuesta, incluso www.sispro.gov.co, que desde una IP
# colombiana devuelve 200. No es lentitud: es un firewall.
#
# ADRES en cambio si responde (falla en 266 ms por su cadena TLS, que el backend
# ya resuelve). Por eso el flujo queda en ADRES y RUAF no se intenta: esperar
# 30 s para caer igual al respaldo solo empeora la experiencia.
#
# El scraper de RUAF queda en services/consultas/ruaf.py, probado y con tests.
# Para revivirlo hace falta salida por IP colombiana (CONSULTAS_PROXY_URL) y
# poner esta variable en true.
RUAF_ENABLED = os.getenv("CONSULTAS_RUAF_ENABLED", "false").lower() == "true"


class IniciarReq(BaseModel):
    tipo_doc: str = Field(default="CC", max_length=10)
    doc: str = Field(min_length=3, max_length=20)
    # RUAF la exige; sin ella solo se puede consultar ADRES (salud).
    fecha_expedicion: str = Field(default="", max_length=12)


class ResolverReq(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    captcha: str = Field(min_length=1, max_length=20)


def _utcnow():
    return datetime.now(timezone.utc)


def _aware(dt):
    """Postgres devuelve tz-aware; SQLite devuelve naive. Normaliza a aware."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _check_enabled():
    if not CONSULTAS_ENABLED:
        raise HTTPException(503, "Las consultas a fuentes oficiales estan desactivadas")


def _org_activa() -> int:
    """Organizacion de la peticion. El superadmin no tiene, y no consulta datos."""
    org = current_org_id.get()
    if not org:
        raise HTTPException(403, "Esta operacion requiere una organizacion activa")
    return org


def _log_consulta(db: Session, org_id: int, usuario: str, fuente: str, doc: str, detalle: str):
    """Audita SIN excepcion de admin — a diferencia de crud_helpers._log().

    Consultar la afiliacion en salud de una persona es tratamiento de dato
    sensible. Que el rol mas poderoso no deje rastro es justo lo que un auditor
    busca, asi que aqui se registra a todos.
    """
    db.add(models.Actividad(
        organizacion_id=org_id,
        usuario=usuario or "?",
        accion=f"consulta_{fuente}",
        modulo="Consultas",
        detalle=f"doc={doc} · {detalle}",
    ))


def _cache_lookup(db: Session, fuente: str, doc: str):
    """Ultima consulta exitosa todavia vigente para ese documento.

    El auto-filtro de tenant.py ya acota la query a la organizacion activa.
    """
    fila = (db.query(models.ConsultaExterna)
            .filter(models.ConsultaExterna.fuente == fuente,
                    models.ConsultaExterna.doc == doc,
                    models.ConsultaExterna.exito.is_(True))
            .order_by(models.ConsultaExterna.id.desc())
            .first())
    if not fila:
        return None
    if not fila.valido_hasta or _aware(fila.valido_hasta) < _utcnow():
        return None
    try:
        return json.loads(fila.respuesta or "{}")
    except Exception:
        return None


def _match_lista(db: Session, nombre_lista: str, valor: str):
    """Intenta casar el nombre que devuelve la fuente con la lista de la organizacion.

    ADRES dice "NUEVA EPS S.A."; la lista puede decir "Nueva EPS". Devuelve el
    valor de la lista si hay match razonable, si no None — para que el empleado
    elija a mano en vez de guardar un valor que no existe en los selects.
    """
    if not valor:
        return None
    try:
        fila = db.query(models.Lista).filter(models.Lista.nombre == nombre_lista).first()
        opciones = json.loads(fila.items or "[]") if fila else []
    except Exception:
        return None

    def limpio(s):
        s = (s or "").upper()
        for ruido in (" S.A.S.", " S.A.S", " S.A.", " S.A", " EPS", " SAS", ".", ","):
            s = s.replace(ruido, " ")
        return " ".join(s.split())

    objetivo = limpio(valor)
    if not objetivo:
        return None
    for o in opciones:
        if limpio(o) == objetivo:
            return o
    for o in opciones:
        a, b = limpio(o), objetivo
        if a and b and (a in b or b in a):
            return o
    return None


def _sugerencia(db: Session, datos: dict) -> dict:
    """Campos del formulario de Afiliados que la consulta puede prellenar.

    `eps` solo se sugiere si casa con la lista de la organizacion; si no, va en
    `eps_sin_match` para que el empleado lo vea y elija.
    """
    eps_crudo = datos.get("eps")
    eps_match = _match_lista(db, "eps", eps_crudo)
    sug = {}
    if datos.get("nombre"):
        sug["nombre"] = datos["nombre"]
    if eps_match:
        sug["eps"] = eps_match
    if datos.get("municipio"):
        sug["ciudad"] = datos["municipio"]
    return {
        "campos": sug,
        "eps_sin_match": eps_crudo if (eps_crudo and not eps_match) else None,
    }


def _sugerencia_ruaf(db: Session, datos: dict) -> dict:
    """Campos que RUAF puede prellenar: EPS, AFP y CCF.

    Solo se sugiere una administradora VIGENTE. Una persona arrastra fondos y
    ARL historicas: prellenar con una inactiva es peor que dejar el campo vacio,
    porque el empleado no tiene como saber que el dato venia mal.

    ARL queda deliberadamente fuera: en este sistema `Afiliado.arl` guarda el
    NIVEL de riesgo (1-5), no la entidad, asi que el nombre de la ARL no encaja
    ahi. Se devuelve aparte como informacion.
    """
    from services.consultas.ruaf import ConsultaRUAF as _R

    sug, sin_match = {}, {}
    if datos.get("nombre"):
        sug["nombre"] = datos["nombre"]

    for subsistema, lista, campo in (
        ("salud", "eps", "eps"),
        ("pensiones", "afp", "afp"),
        ("compensacion_familiar", "ccf", "ccf"),
    ):
        vigente = _R.administradora_vigente(datos.get(subsistema) or [])
        if not vigente:
            continue
        match = _match_lista(db, lista, vigente)
        if match:
            sug[campo] = match
        else:
            sin_match[campo] = vigente

    # Ciudad: la reporta salud como "Departamento -> Municipio".
    for fila in (datos.get("salud") or []):
        for k, v in fila.items():
            if "municipio" in k.lower() and v and v.strip():
                sug["ciudad"] = v.split("-")[-1].strip()
                break
        if "ciudad" in sug:
            break

    arl_vigente = _R.administradora_vigente(datos.get("riesgos_laborales") or [])
    return {
        "campos": sug,
        "sin_match": sin_match or None,
        # Informativo: no se puede prellenar porque el campo guarda el nivel.
        "arl_reportada": arl_vigente,
    }


@router.post("/adres/iniciar")
async def adres_iniciar(req: IniciarReq, db: Session = Depends(get_db),
                        token=Depends(require_admin_or_empleado)):
    """Paso 1: abre la sesion con ADRES y devuelve el captcha a resolver.

    Si la organizacion ya tiene una consulta vigente de ese documento, devuelve
    los datos directo y no gasta un captcha.
    """
    _check_enabled()
    org_id = _org_activa()
    doc = (req.doc or "").strip()
    if not doc.isdigit():
        raise HTTPException(422, "El documento debe ser numerico")
    if not ConsultaADRES.tipo_doc_soportado(req.tipo_doc):
        raise HTTPException(422, f"ADRES no consulta documentos tipo {req.tipo_doc}")

    en_cache = _cache_lookup(db, "adres", doc)
    if en_cache:
        return {"cacheado": True, "datos": en_cache, "sugerencia": _sugerencia(db, en_cache)}

    try:
        estado, png = await ConsultaADRES.iniciar(req.tipo_doc, doc)
    except FuenteNoDisponible as e:
        raise HTTPException(502, str(e))
    except ErrorConsulta as e:
        raise HTTPException(422, str(e))

    session_id = uuid.uuid4().hex
    _cache_set(f"consulta:sess:{session_id}",
               {"org_id": org_id, "fuente": "adres", "estado": estado.to_dict()},
               ttl=TTL_SESION_SEG)

    return {
        "cacheado": False,
        "session_id": session_id,
        "captcha": captcha_a_data_url(png),
        "expira_seg": TTL_SESION_SEG,
    }


@router.post("/adres/resolver")
async def adres_resolver(req: ResolverReq, db: Session = Depends(get_db),
                         token=Depends(require_admin_or_empleado)):
    """Paso 2: envia el captcha resuelto y devuelve los datos normalizados."""
    _check_enabled()
    org_id = _org_activa()
    crudo = _cache_get(f"consulta:sess:{req.session_id}")
    if not crudo:
        raise HTTPException(410, "La consulta expiro. Genera un codigo nuevo.")
    # Una organizacion no completa una consulta iniciada por otra.
    if crudo.get("org_id") != org_id:
        raise HTTPException(410, "La consulta expiro. Genera un codigo nuevo.")

    estado = EstadoConsulta.from_dict(crudo["estado"])
    usuario = token.get("sub", "?")

    def registrar(exito: bool, datos: dict = None, error: str = None):
        fila = models.ConsultaExterna(
            organizacion_id=org_id,
            fuente="adres",
            tipo_doc=estado.tipo_doc,
            doc=estado.doc,
            exito=exito,
            nombre=(datos or {}).get("nombre"),
            eps=(datos or {}).get("eps"),
            regimen=(datos or {}).get("regimen"),
            estado_afil=(datos or {}).get("estado"),
            tipo_afiliado=(datos or {}).get("tipo_afiliado"),
            respuesta=json.dumps(datos, ensure_ascii=False) if datos else None,
            error_detalle=error,
            usuario=usuario,
            valido_hasta=_utcnow() + timedelta(days=TTL_RESULTADO_DIAS) if exito else None,
        )
        db.add(fila)
        _log_consulta(db, org_id, usuario, "adres", estado.doc,
                      "ok" if exito else f"fallo: {error}")
        db.commit()

    try:
        resultado = await ConsultaADRES.resolver(estado, req.captcha)
    except CaptchaIncorrecto as e:
        # La sesion ya no sirve: ADRES quema el captcha en cada intento.
        _cache_set(f"consulta:sess:{req.session_id}", None, ttl=1)
        raise HTTPException(400, str(e))
    except SinResultados as e:
        registrar(False, error=str(e))
        raise HTTPException(404, str(e))
    except FuenteNoDisponible as e:
        registrar(False, error=str(e))
        raise HTTPException(502, str(e))
    except ErrorConsulta as e:
        registrar(False, error=str(e))
        raise HTTPException(422, str(e))

    datos = resultado.to_dict()
    registrar(True, datos=datos)
    _cache_set(f"consulta:sess:{req.session_id}", None, ttl=1)

    return {"datos": datos, "sugerencia": _sugerencia(db, datos)}


@router.get("/historial")
def historial(doc: str, db: Session = Depends(get_db),
              token=Depends(require_admin_or_empleado)):
    """Consultas hechas sobre un documento en esta organizacion. Rastro de habeas data."""
    _org_activa()
    filas = (db.query(models.ConsultaExterna)
             .filter(models.ConsultaExterna.doc == (doc or "").strip())
             .order_by(models.ConsultaExterna.id.desc())
             .limit(20).all())
    return [{
        "id": f.id,
        "fuente": f.fuente,
        "exito": bool(f.exito),
        "usuario": f.usuario,
        "creado": f.creado,
        "error_detalle": f.error_detalle,
    } for f in filas]


# ─── Endpoints unificados ─────────────────────────────────────────────────────
#
# Preferencia: RUAF primero, ADRES como respaldo.
#
# RUAF es estrictamente superior — trae EPS, AFP, ARL, CCF y cesantias, mientras
# ADRES solo cubre salud — pero exige la fecha de expedicion del documento. Si
# no la hay, o si RUAF esta caido, se cae a ADRES en vez de dejar al empleado
# sin nada.

async def _iniciar_ruaf(org_id: int, req: "IniciarReq"):
    estado, img = await ConsultaRUAF.iniciar(
        req.tipo_doc, req.doc.strip(), req.fecha_expedicion.strip())
    return "ruaf", estado, img


async def _iniciar_adres(org_id: int, req: "IniciarReq"):
    estado, img = await ConsultaADRES.iniciar(req.tipo_doc, req.doc.strip())
    return "adres", estado, img


@router.post("/iniciar")
async def iniciar(req: IniciarReq, db: Session = Depends(get_db),
                  token=Depends(require_admin_or_empleado)):
    """Abre la consulta contra la mejor fuente disponible."""
    _check_enabled()
    org_id = _org_activa()
    doc = (req.doc or "").strip()
    if not doc.isdigit():
        raise HTTPException(422, "El documento debe ser numerico")

    tiene_fecha = bool((req.fecha_expedicion or "").strip())
    puede_ruaf = (RUAF_ENABLED and tiene_fecha
                  and ConsultaRUAF.tipo_doc_soportado(req.tipo_doc))
    puede_adres = ConsultaADRES.tipo_doc_soportado(req.tipo_doc)
    if not puede_ruaf and not puede_adres:
        raise HTTPException(
            422, f"Ninguna fuente consulta documentos tipo {req.tipo_doc}")

    # Cache: solo cuenta el de la fuente que SE VA A USAR.
    #
    # Si hay fecha de expedicion se apunta a RUAF, y un resultado viejo de ADRES
    # no sirve como sustituto: trae unicamente salud. Aceptarlo haria que
    # agregar la fecha no cambiara nada — el empleado la escribe esperando AFP,
    # ARL y caja, y recibiria lo mismo de antes sin entender por que.
    fuente_objetivo = "ruaf" if puede_ruaf else "adres"
    en_cache = _cache_lookup(db, fuente_objetivo, doc)
    if en_cache:
        sug = (_sugerencia_ruaf if fuente_objetivo == "ruaf" else _sugerencia)(db, en_cache)
        return {"cacheado": True, "fuente": fuente_objetivo, "datos": en_cache,
                "sugerencia": sug}

    intentos = []
    if puede_ruaf:
        intentos.append(_iniciar_ruaf)
    if puede_adres:
        intentos.append(_iniciar_adres)

    ultimo = None
    for intento in intentos:
        try:
            fuente, estado, png = await intento(org_id, req)
        except FuenteNoDisponible as e:
            ultimo = e          # fuente caida o cambiada: probar la siguiente
            continue
        except ErrorConsulta as e:
            ultimo = e
            continue

        session_id = uuid.uuid4().hex
        _cache_set(f"consulta:sess:{session_id}",
                   {"org_id": org_id, "fuente": fuente, "estado": estado.to_dict()},
                   ttl=TTL_SESION_SEG)
        return {
            "cacheado": False,
            "fuente": fuente,
            "session_id": session_id,
            "captcha": captcha_a_data_url(png),
            "expira_seg": TTL_SESION_SEG,
            # RUAF distingue mayusculas; ADRES manda solo digitos.
            "captcha_sensible_mayusculas": fuente == "ruaf",
        }

    if isinstance(ultimo, FuenteNoDisponible):
        raise HTTPException(502, str(ultimo))
    raise HTTPException(422, str(ultimo) if ultimo else "No se pudo abrir la consulta")


@router.post("/resolver")
async def resolver(req: ResolverReq, db: Session = Depends(get_db),
                   token=Depends(require_admin_or_empleado)):
    """Envia el captcha resuelto a la fuente con la que se abrio la consulta."""
    _check_enabled()
    org_id = _org_activa()
    crudo = _cache_get(f"consulta:sess:{req.session_id}")
    if not crudo or crudo.get("org_id") != org_id:
        raise HTTPException(410, "La consulta expiro. Genera un codigo nuevo.")

    fuente = crudo.get("fuente", "adres")
    usuario = token.get("sub", "?")
    if fuente == "ruaf":
        estado = EstadoRuaf.from_dict(crudo["estado"])
        cliente, sugeridor = ConsultaRUAF, _sugerencia_ruaf
    else:
        estado = EstadoConsulta.from_dict(crudo["estado"])
        cliente, sugeridor = ConsultaADRES, _sugerencia

    def registrar(exito: bool, datos: dict = None, error: str = None):
        d = datos or {}
        db.add(models.ConsultaExterna(
            organizacion_id=org_id, fuente=fuente,
            tipo_doc=estado.tipo_doc, doc=estado.doc, exito=exito,
            nombre=d.get("nombre"), eps=d.get("eps"), regimen=d.get("regimen"),
            estado_afil=d.get("estado"), tipo_afiliado=d.get("tipo_afiliado"),
            respuesta=json.dumps(d, ensure_ascii=False) if datos else None,
            error_detalle=error, usuario=usuario,
            valido_hasta=_utcnow() + timedelta(days=TTL_RESULTADO_DIAS) if exito else None,
        ))
        _log_consulta(db, org_id, usuario, fuente, estado.doc,
                      "ok" if exito else f"fallo: {error}")
        db.commit()

    try:
        resultado = await cliente.resolver(estado, req.captcha)
    except CaptchaIncorrecto as e:
        _cache_set(f"consulta:sess:{req.session_id}", None, ttl=1)
        raise HTTPException(400, str(e))
    except SinResultados as e:
        registrar(False, error=str(e))
        raise HTTPException(404, str(e))
    except FuenteNoDisponible as e:
        registrar(False, error=str(e))
        raise HTTPException(502, str(e))
    except ErrorConsulta as e:
        registrar(False, error=str(e))
        raise HTTPException(422, str(e))

    datos = resultado.to_dict()
    registrar(True, datos=datos)
    _cache_set(f"consulta:sess:{req.session_id}", None, ttl=1)
    return {"fuente": fuente, "datos": datos, "sugerencia": sugeridor(db, datos)}
