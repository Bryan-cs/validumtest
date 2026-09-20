"""Cliente del operador de información (SuAporte — Enlace Operativo / ARUS).

Sustituye el recorrido manual de descargar el plano, entrar al portal, subirlo,
revisar inconsistencias y volver por el enlace de pago. Todo eso son llamadas.

El encadenado que exige el operador, en este orden:

1. `POST /auth/login` con la clave secreta en un header. Devuelve cinco headers
   de sesión (`token`, `faces`, `refresh-token` y sus dos fechas) que hay que
   reenviar en todo lo demás.
2. `GET /api/gestion/authorization/user/contributor` sobre el aportante que se
   va a liquidar. Devuelve otros cuatro headers (`profiles`, `contributor`,
   `appId`, `refrescar`). Sin esto, el resto responde 401.
3. `POST /api/generadorPlanillas/v1/planillas/validacion` con el archivo plano.
4. `GET .../inconsistencias`, `GET .../totales` y `GET .../pago/url`.

**Modo simulación.** Por defecto el cliente no sale a la red: arma la petición,
la registra y devuelve una respuesta marcada como simulada. Enviar una planilla
crea un registro real en el operador y el enlace de pago mueve dinero, así que
el envío real se habilita explícitamente con `SUAPORTE_MODO=real` y conviene
que la primera vez la dispare una persona, no un test.

Credenciales: `SUAPORTE_USUARIO` (tipo + número, p.ej. CC8487324),
`SUAPORTE_CONTRASENA` y `SUAPORTE_CLAVE_SECRETA`. Nunca en el código.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger("bbcfile")

BASE_AUTH = os.getenv("SUAPORTE_BASE_AUTH", "https://www.suaporte.com.co/auth")
BASE_GESTION = os.getenv("SUAPORTE_BASE_GESTION", "https://www.suaporte.com.co/api/gestion")
BASE_PLANILLAS = os.getenv("SUAPORTE_BASE_PLANILLAS",
                           "https://www.suaporte.com.co/api/generadorPlanillas")

TIMEOUT = float(os.getenv("SUAPORTE_TIMEOUT", "60"))

# Headers que devuelve cada paso y que hay que arrastrar a los siguientes.
HEADERS_SESION = ("token", "faces", "refresh-token", "refresh-token-date", "refresh-token-ttl")
HEADERS_AUTORIZACION = ("profiles", "contributor", "appId", "refrescar")


class ErrorOperador(Exception):
    """Falla al hablar con el operador. El detalle va en el mensaje."""


@dataclass
class Sesion:
    """Los headers vivos de una sesión con el operador."""
    sesion: dict = field(default_factory=dict)
    autorizacion: dict = field(default_factory=dict)
    simulada: bool = False

    @property
    def headers(self) -> dict:
        return {**self.sesion, **self.autorizacion}

    @property
    def autorizada(self) -> bool:
        return bool(self.sesion) and bool(self.autorizacion)


def modo_real() -> bool:
    """¿Se sale a la red? Solo con SUAPORTE_MODO=real."""
    return os.getenv("SUAPORTE_MODO", "simulacion").strip().lower() == "real"


def credenciales() -> tuple:
    usuario = os.getenv("SUAPORTE_USUARIO", "")
    contrasena = os.getenv("SUAPORTE_CONTRASENA", "")
    clave = os.getenv("SUAPORTE_CLAVE_SECRETA", "")
    return usuario, contrasena, clave


def hay_credenciales() -> bool:
    return all(credenciales())


def _registrar(paso: str, **datos):
    """Deja rastro de la llamada sin escribir credenciales en el log."""
    seguros = {k: v for k, v in datos.items()
               if k not in ("contrasena", "clave_secreta", "clave-secreta")}
    log.info(f"PILA operador [{'real' if modo_real() else 'simulacion'}] {paso}: {seguros}")


def _tomar(headers, nombres) -> dict:
    """Extrae los headers que el operador devuelve, sin distinguir mayúsculas."""
    bajos = {k.lower(): v for k, v in headers.items()}
    return {n: bajos[n.lower()] for n in nombres if n.lower() in bajos}


# ─── Paso 1: autenticación ────────────────────────────────────────────────────

def autenticar(cliente: Optional[httpx.Client] = None) -> Sesion:
    usuario, contrasena, clave = credenciales()

    # En simulación no se piden credenciales: sirve para revisar el armado de
    # las peticiones en una máquina que no tiene los secretos.
    if not modo_real():
        _registrar("login", usuario=usuario or "(sin configurar)", url=f"{BASE_AUTH}/login")
        return Sesion(sesion={h: f"simulado-{h}" for h in HEADERS_SESION}, simulada=True)

    if not all((usuario, contrasena, clave)):
        raise ErrorOperador(
            "Faltan credenciales del operador. Define SUAPORTE_USUARIO, "
            "SUAPORTE_CONTRASENA y SUAPORTE_CLAVE_SECRETA.")

    _registrar("login", usuario=usuario, url=f"{BASE_AUTH}/login")

    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=TIMEOUT)
    try:
        r = cliente.post(f"{BASE_AUTH}/login",
                         json={"usuario": usuario, "contrasena": contrasena},
                         headers={"clave-secreta": clave,
                                  "Content-Type": "application/json"})
        if r.status_code != 200:
            raise ErrorOperador(f"El operador rechazó la autenticación "
                                f"({r.status_code}): {r.text[:300]}")
        sesion = _tomar(r.headers, HEADERS_SESION)
        if "token" not in sesion:
            raise ErrorOperador("La autenticación no devolvió el header 'token'")
        return Sesion(sesion=sesion)
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo contactar al operador: {e}") from e
    finally:
        if propio:
            cliente.close()


# ─── Paso 2: autorización sobre el aportante ──────────────────────────────────

def autorizar(sesion: Sesion, tipo_doc: str, num_doc: str,
              cliente: Optional[httpx.Client] = None) -> Sesion:
    """Pide permiso para operar sobre ese aportante.

    Es el paso que responde "este usuario sí puede liquidarle a esta empresa".
    """
    _registrar("autorizacion", aportante=f"{tipo_doc}{num_doc}")

    if sesion.simulada or not modo_real():
        sesion.autorizacion = {h: f"simulado-{h}" for h in HEADERS_AUTORIZACION}
        sesion.simulada = True
        return sesion

    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=TIMEOUT)
    try:
        r = cliente.get(f"{BASE_GESTION}/authorization/user/contributor",
                        params={"id": num_doc, "tipoIdentificacion": tipo_doc,
                                "numeroIdentificacion": num_doc},
                        headers=sesion.sesion)
        if r.status_code == 401:
            raise ErrorOperador("El usuario no está autorizado sobre ese aportante")
        if r.status_code != 200:
            raise ErrorOperador(f"Autorización rechazada ({r.status_code}): {r.text[:300]}")
        sesion.autorizacion = _tomar(r.headers, HEADERS_AUTORIZACION)
        return sesion
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo autorizar: {e}") from e
    finally:
        if propio:
            cliente.close()


# ─── Paso 3: enviar la planilla ───────────────────────────────────────────────

def validar_planilla(sesion: Sesion, contenido: str, nombre_archivo: str,
                     tipo_archivo: str = "I", planilla_ugpp: bool = False,
                     solo_novedades: bool = False,
                     cliente: Optional[httpx.Client] = None) -> dict:
    """Sube el archivo plano y devuelve lo que responda el operador.

    `tipo_archivo` es el que espera el servicio en su cadena de parámetros; el
    ejemplo de la documentación usa "I".
    """
    if not sesion.autorizada and modo_real():
        raise ErrorOperador("Hay que autorizar sobre el aportante antes de enviar")

    parametros = json.dumps({"planillaUGPP": planilla_ugpp,
                             "planillaNSoloNovedades": solo_novedades,
                             "tipoArchivo": tipo_archivo})
    _registrar("validacion", archivo=nombre_archivo, bytes=len(contenido),
               parametros=parametros)

    if sesion.simulada or not modo_real():
        return {"simulado": True, "parametros": json.loads(parametros),
                "archivo": nombre_archivo, "bytes": len(contenido),
                "mensaje": "No se envió nada: el cliente está en modo simulación."}

    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=TIMEOUT)
    try:
        r = cliente.post(
            f"{BASE_PLANILLAS}/v1/planillas/validacion",
            params={"parametros": parametros},
            files={"archivo": (nombre_archivo, contenido.encode("latin-1"), "text/plain")},
            headers=sesion.headers)
        if r.status_code not in (200, 201):
            raise ErrorOperador(f"El operador rechazó la planilla "
                                f"({r.status_code}): {r.text[:500]}")
        return r.json() if r.headers.get("content-type", "").startswith("application/json") \
            else {"respuesta": r.text[:2000]}
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo enviar la planilla: {e}") from e
    finally:
        if propio:
            cliente.close()


# ─── Paso 4: resultado ────────────────────────────────────────────────────────

def _get_json(sesion: Sesion, url: str, params: dict = None,
              cliente: Optional[httpx.Client] = None, vacio=None):
    if sesion.simulada or not modo_real():
        return vacio if vacio is not None else {"simulado": True}
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=TIMEOUT)
    try:
        r = cliente.get(url, params=params or {}, headers=sesion.headers)
        if r.status_code != 200:
            raise ErrorOperador(f"{url} respondió {r.status_code}: {r.text[:300]}")
        return r.json()
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo consultar {url}: {e}") from e
    finally:
        if propio:
            cliente.close()


def inconsistencias(sesion: Sesion, codigo_planilla: str, desde: int = 0,
                    limite: int = 100, cliente: Optional[httpx.Client] = None):
    """Los errores y alertas de la planilla, que hoy se revisan a mano."""
    _registrar("inconsistencias", planilla=codigo_planilla)
    return _get_json(sesion,
                     f"{BASE_PLANILLAS}/v1/planillas/{codigo_planilla}/inconsistencias",
                     {"registro-inicial": desde, "limite": limite}, cliente,
                     vacio={"simulado": True, "inconsistencias": []})


def totales(sesion: Sesion, numero_planilla: str, cliente: Optional[httpx.Client] = None):
    _registrar("totales", planilla=numero_planilla)
    return _get_json(sesion, f"{BASE_PLANILLAS}/v1/planillas/{numero_planilla}/totales",
                     None, cliente)


def url_pago(sesion: Sesion, numero_planilla: str,
             cliente: Optional[httpx.Client] = None) -> str:
    """La URL con el botón de PSE. Abrirla inicia el pago real."""
    _registrar("url_pago", planilla=numero_planilla)
    datos = _get_json(sesion, f"{BASE_PLANILLAS}/v1/planillas/{numero_planilla}/pago/url",
                      None, cliente, vacio={"url": ""})
    if isinstance(datos, str):
        return datos
    for clave in ("url", "urlPago", "link"):
        if datos.get(clave):
            return datos[clave]
    return ""


def administradoras_de(sesion: Sesion, tipo_doc: str, num_doc: str,
                       cliente: Optional[httpx.Client] = None):
    """EPS y AFP reales de una persona según BDUA y RUAF.

    Sirve para liquidar con la administradora que el operador tiene registrada
    en vez de la que esté en nuestra base, que es de donde salen las alertas
    "la EPS no coincide con la registrada".
    """
    _registrar("bdua_ruaf", documento=f"{tipo_doc}{num_doc}")
    return _get_json(
        sesion,
        f"{BASE_PLANILLAS}/v1/administradoras/bdua-ruaf/{tipo_doc}/{num_doc}",
        None, cliente, vacio={"simulado": True})


# ─── Recorrido completo ───────────────────────────────────────────────────────

def enviar_planilla(contenido: str, nombre_archivo: str, tipo_doc_aportante: str,
                    num_doc_aportante: str, tipo_archivo: str = "I") -> dict:
    """Los cuatro pasos de una vez, reutilizando una sola conexión.

    Devuelve lo que se pueda obtener en cada etapa. Si el operador rechaza la
    planilla, la excepción lleva su mensaje tal cual: es más útil que uno
    nuestro.
    """
    with httpx.Client(timeout=TIMEOUT) as cliente:
        sesion = autenticar(cliente)
        autorizar(sesion, tipo_doc_aportante, num_doc_aportante, cliente)
        respuesta = validar_planilla(sesion, contenido, nombre_archivo,
                                     tipo_archivo=tipo_archivo, cliente=cliente)

        numero = ""
        for clave in ("numeroPlanilla", "numero", "codigoPlanilla", "codigo"):
            if isinstance(respuesta, dict) and respuesta.get(clave):
                numero = str(respuesta[clave])
                break

        resultado = {"simulado": sesion.simulada, "respuesta": respuesta,
                     "numero_planilla": numero, "inconsistencias": None,
                     "totales": None, "url_pago": ""}
        if numero:
            resultado["inconsistencias"] = inconsistencias(sesion, numero, cliente=cliente)
            resultado["totales"] = totales(sesion, numero, cliente=cliente)
            resultado["url_pago"] = url_pago(sesion, numero, cliente=cliente)
        return resultado
