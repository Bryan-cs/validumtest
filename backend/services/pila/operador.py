"""Cliente del operador de información PILA.

SuAporte (Enlace Operativo / ARUS) y PagoSimple (Simple S.A.) usan el mismo
encadenado de APIs; cambia el dominio y la clave secreta. Se elige con
`PILA_OPERADOR=pagosimple` o `suaporte`.

El recorrido, en este orden:

1. `POST /auth/login` con la clave secreta en un header. Devuelve cinco headers
   de sesión (`token`, `faces`, `refresh-token` y sus dos fechas) que hay que
   reenviar en todo lo demás.
2. `GET /api/gestion/authorization/user/contributor` sobre el aportante que se
   va a liquidar. Devuelve otros cuatro headers (`profiles`, `contributor`,
   `appId`, `refrescar`). Sin esto, el resto responde 401.
3. `POST /api/generadorPlanillas/v1/planillas/validacion` con el archivo plano.
4. `GET .../inconsistencias`, `GET .../totales` y `GET .../pago/url`.
5. Tras el pago, `GET .../planillas/{numero}/comprobante` (u otras rutas
   equivalentes) para el recibo que emite el operador.

**Modo simulación.** Por defecto el cliente no sale a la red: arma la petición,
la registra y devuelve una respuesta marcada como simulada. Enviar una planilla
crea un registro real en el operador y el enlace de pago mueve dinero, así que
el envío real se habilita explícitamente con `SUAPORTE_MODO=real`.

Credenciales: usuario (tipo + número, p.ej. CC8487324), contraseña y la clave
de API (`PAGOSIMPLE_API_KEY` o `SUAPORTE_CLAVE_SECRETA`). Nunca en el código.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import certifi
import httpx

log = logging.getLogger("bbcfile")

def operador_nombre() -> str:
    """suaporte | pagosimple. Lo elige PILA_OPERADOR, no el código."""
    nombre = (os.getenv("PILA_OPERADOR") or "suaporte").strip().lower()
    return "pagosimple" if nombre in ("pagosimple", "pago_simple", "simple") else "suaporte"


def _base_auth() -> str:
    if operador_nombre() == "pagosimple":
        return os.getenv("PAGOSIMPLE_BASE_AUTH", "https://www.simple.co/auth")
    return os.getenv("SUAPORTE_BASE_AUTH", "https://www.suaporte.com.co/auth")


def _base_gestion() -> str:
    if operador_nombre() == "pagosimple":
        return os.getenv("PAGOSIMPLE_BASE_GESTION", "https://www.simple.co/api/gestion")
    return os.getenv("SUAPORTE_BASE_GESTION", "https://www.suaporte.com.co/api/gestion")


def _base_planillas() -> str:
    if operador_nombre() == "pagosimple":
        return os.getenv("PAGOSIMPLE_BASE_PLANILLAS",
                         "https://www.simple.co/api/generadorPlanillas")
    return os.getenv("SUAPORTE_BASE_PLANILLAS",
                     "https://www.suaporte.com.co/api/generadorPlanillas")


# Alias para tests y lecturas antiguas: se resuelven al importar. El envío
# usa las funciones, que sí ven un cambio de PILA_OPERADOR en caliente.
BASE_AUTH = _base_auth()
BASE_GESTION = _base_gestion()
BASE_PLANILLAS = _base_planillas()

TIMEOUT = float(os.getenv("SUAPORTE_TIMEOUT", "60"))

# El servidor del operador envía solo su certificado de hoja y omite el
# intermedio de DigiCert, así que la verificación falla con
# CERTIFICATE_VERIFY_FAILED. Se completa la cadena con el intermedio publicado
# por DigiCert en vez de desactivar la verificación: por aquí viajan las
# credenciales. `SUAPORTE_CA_BUNDLE` permite apuntar a otro bundle si el
# operador cambia de emisor.
_INTERMEDIO = Path(__file__).parent / "datos" / "suaporte_intermedio.pem"


def contexto_tls() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=os.getenv("SUAPORTE_CA_BUNDLE") or certifi.where())
    if not os.getenv("SUAPORTE_CA_BUNDLE") and _INTERMEDIO.exists():
        ctx.load_verify_locations(cafile=str(_INTERMEDIO))
    return ctx


def _cliente_nuevo() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, verify=contexto_tls())

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
    usuario = os.getenv("PAGOSIMPLE_USUARIO") or os.getenv("SUAPORTE_USUARIO", "")
    contrasena = os.getenv("PAGOSIMPLE_CONTRASENA") or os.getenv("SUAPORTE_CONTRASENA", "")
    if operador_nombre() == "pagosimple":
        clave = os.getenv("PAGOSIMPLE_API_KEY") or os.getenv("SUAPORTE_CLAVE_SECRETA", "")
    else:
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


def cifrar(dato: str, cliente: Optional[httpx.Client] = None) -> str:
    """Cifra un dato con el servicio RSA del operador y lo devuelve en Base64.

    El login rechaza la contraseña en texto plano con "El dato no tiene formato
    de cifrado válido", así que este paso es obligatorio aunque la
    documentación diga que admite ambas formas. No requiere autenticación.
    """
    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    try:
        r = cliente.post(f"{_base_auth()}/crypto/cifrar-datos", json={"datoACifrar": dato})
        if r.status_code != 200:
            raise ErrorOperador(f"No se pudo cifrar ({r.status_code}): {r.text[:200]}")
        cuerpo = r.json()
        cifrado = cuerpo.get("datoCifrado") or cuerpo.get("data") or cuerpo.get("dato")
        if isinstance(cifrado, dict):
            cifrado = cifrado.get("datoCifrado")
        if not cifrado:
            raise ErrorOperador(f"El cifrado no devolvió dato: {str(cuerpo)[:200]}")
        return cifrado
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo cifrar el dato: {e}") from e
    finally:
        if propio:
            cliente.close()



# ─── Paso 1: autenticación ────────────────────────────────────────────────────

def autenticar(cliente: Optional[httpx.Client] = None) -> Sesion:
    usuario, contrasena, clave = credenciales()

    # En simulación no se piden credenciales: sirve para revisar el armado de
    # las peticiones en una máquina que no tiene los secretos.
    if not modo_real():
        _registrar("login", usuario=usuario or "(sin configurar)", url=f"{_base_auth()}/login")
        return Sesion(sesion={h: f"simulado-{h}" for h in HEADERS_SESION}, simulada=True)

    if not all((usuario, contrasena, clave)):
        raise ErrorOperador(
            "Faltan credenciales del operador. Define usuario, contraseña y "
            "PAGOSIMPLE_API_KEY (o SUAPORTE_CLAVE_SECRETA).")

    _registrar("login", usuario=usuario, url=f"{_base_auth()}/login")

    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    try:
        # La contraseña viaja cifrada: el login rechaza el texto plano.
        secreto = contrasena if os.getenv("SUAPORTE_CIFRAR", "1") == "0"             else cifrar(contrasena, cliente)
        r = cliente.post(f"{_base_auth()}/login",
                         json={"usuario": usuario, "contrasena": secreto},
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


def consultar_aportante(sesion: Sesion, tipo_doc: str, num_doc: str,
                        cliente: Optional[httpx.Client] = None) -> dict:
    """Los datos del aportante en el operador, incluido su id interno.

    Ese id es el que pide la autorización: el servicio recibe un entero, no el
    número de documento. Si el usuario no tiene permisos sobre el aportante, el
    operador lo dice aquí y no hay que llegar a la autorización para saberlo.
    """
    if sesion.simulada or not modo_real():
        return {"simulado": True, "id": 0, "razonSocial": "(simulado)"}

    _registrar("consultar_aportante", aportante=f"{tipo_doc}{num_doc}")
    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    try:
        r = cliente.get(f"{_base_gestion()}/aportante/{tipo_doc}/{num_doc}",
                        headers=sesion.sesion)
        if r.status_code != 200:
            raise ErrorOperador(f"No se pudo consultar el aportante "
                                f"{tipo_doc} {num_doc}: {r.text[:250]}")
        return r.json()
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo consultar el aportante: {e}") from e
    finally:
        if propio:
            cliente.close()



# ─── Paso 2: autorización sobre el aportante ──────────────────────────────────

def autorizar(sesion: Sesion, tipo_doc: str, num_doc: str,
              cliente: Optional[httpx.Client] = None,
              aportante_id: Optional[int] = None) -> Sesion:
    """Pide permiso para operar sobre ese aportante.

    Es el paso que responde "este usuario sí puede liquidarle a esta empresa".
    El servicio identifica al aportante por su id interno, no por el documento,
    así que si no se conoce se consulta primero.
    """
    _registrar("autorizacion", aportante=f"{tipo_doc}{num_doc}")

    if sesion.simulada or not modo_real():
        sesion.autorizacion = {h: f"simulado-{h}" for h in HEADERS_AUTORIZACION}
        sesion.simulada = True
        return sesion

    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    try:
        if aportante_id is None:
            aportante_id = consultar_aportante(sesion, tipo_doc, num_doc, cliente).get("id")

        r = cliente.get(f"{_base_gestion()}/authorization/user/contributor",
                        params={"id": aportante_id, "tipoIdentificacion": tipo_doc,
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
    cliente = cliente or _cliente_nuevo()
    try:
        r = cliente.post(
            f"{_base_planillas()}/v1/planillas/validacion",
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

def corregir_planilla(sesion: Sesion, codigo_planilla: str,
                     tipo_archivo: str = "I", planilla_ugpp: bool = False,
                     solo_novedades: bool = False,
                     validar_ingreso_retiro: bool = False,
                     cliente: Optional[httpx.Client] = None) -> dict:
    """Le pide al operador que corrija lo que marcó como autocorregible.

    Hay errores que el operador sabe arreglar solo, y el portal tiene un botón
    para eso. El caso que lo hizo falta: el código de actividad económica, que
    sale del anexo del Decreto 768 y no está en ningún documento que tengamos.
    Preguntárselo a quien valida es mejor que adivinarlo.

    Solo toca los errores del cotizante y del aportante. Las advertencias no
    las corrige, y por eso `corregirInconsistenciaInformativa` va en false: lo
    dice su propia documentación.
    """
    if not sesion.autorizada and modo_real():
        raise ErrorOperador("Hay que autorizar sobre el aportante antes de corregir")

    cuerpo = {
        "codigoPlanilla": str(codigo_planilla),
        "corregirInconsistenciaInformativa": False,
        "planillaNSoloNovedades": solo_novedades,
        "planillaUGPP": planilla_ugpp,
        "tipoArchivo": tipo_archivo,
        "validarIngresoRetiro": validar_ingreso_retiro,
    }
    _registrar("correccion", planilla=codigo_planilla)

    if sesion.simulada or not modo_real():
        return {"simulado": True, "parametros": cuerpo,
                "mensaje": "No se pidió nada: el cliente está en modo simulación."}

    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    try:
        r = cliente.post(f"{_base_planillas()}/v1/planillas/{codigo_planilla}/correccion",
                         json=cuerpo, headers=sesion.headers)
        if r.status_code not in (200, 201):
            raise ErrorOperador(f"El operador no pudo corregir la planilla "
                                f"({r.status_code}): {r.text[:500]}")
        return r.json() if r.headers.get("content-type", "").startswith("application/json")             else {"respuesta": r.text[:2000]}
    except httpx.HTTPError as e:
        raise ErrorOperador(f"No se pudo pedir la corrección: {e}") from e
    finally:
        if propio:
            cliente.close()


def _get_json(sesion: Sesion, url: str, params: dict = None,
              cliente: Optional[httpx.Client] = None, vacio=None):
    if sesion.simulada or not modo_real():
        return vacio if vacio is not None else {"simulado": True}
    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    try:
        r = cliente.get(url, params=params or {}, headers=sesion.headers)
        if r.status_code != 200:
            raise ErrorOperador(f"{url} respondió {r.status_code}: {r.text[:300]}")
        # El operador anuncia application/json pero a veces responde el dato
        # pelado —la URL de pago llega así—, que no es JSON válido.
        try:
            return r.json()
        except ValueError:
            return r.text.strip()
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
                     f"{_base_planillas()}/v1/planillas/{codigo_planilla}/inconsistencias",
                     {"registro-inicial": desde, "limite": limite}, cliente,
                     vacio={"simulado": True, "inconsistencias": []})


def totales(sesion: Sesion, numero_planilla: str, cliente: Optional[httpx.Client] = None):
    """Los totales que cobra el operador, que no son los que liquida el motor.

    El operador devuelve el valor final: nuestro subtotal mas los intereses de
    mora que correspondan por pagar el periodo despues de la fecha limite. En la
    planilla 88320590 eso fue $429.600 de aportes mas $6.000 de intereses, o sea
    $435.600, y la prefactura lo separa en "SUBTOTAL SIN INTERESES" y "TOTAL
    INTERESES". Los intereses se prorratean por administradora, asi que tampoco
    conviene contrastar linea por linea contra la liquidacion propia.

    El interes depende de la fecha en que se pague, no de la que se liquide, asi
    que el motor no lo calcula: la cifra que manda es esta.
    """
    _registrar("totales", planilla=numero_planilla)
    return _get_json(sesion, f"{_base_planillas()}/v1/planillas/{numero_planilla}/totales",
                     None, cliente)


def url_pago(sesion: Sesion, numero_planilla: str,
             cliente: Optional[httpx.Client] = None) -> str:
    """La URL con el botón de PSE. Abrirla inicia el pago real.

    El operador la devuelve como texto pelado aunque anuncie JSON, y la
    entrega incluso para planillas todavía sin numerar. Con el número a veces
    responde vacío: el código de la planilla es el que sí trae el enlace.
    """
    _registrar("url_pago", planilla=numero_planilla)
    datos = _get_json(sesion, f"{_base_planillas()}/v1/planillas/{numero_planilla}/pago/url",
                      None, cliente, vacio={"url": ""})
    return _url_http(datos)


def enlace_de_pago(sesion: Sesion, codigo_planilla: str = "",
                   numero_planilla: str = "",
                   cliente: Optional[httpx.Client] = None) -> str:
    """Prueba el código y, si ese no trae URL, el número."""
    for ref in (codigo_planilla, numero_planilla):
        ref = str(ref or "").strip()
        if not ref or ref == "0":
            continue
        try:
            enlace = url_pago(sesion, ref, cliente)
        except ErrorOperador:
            continue
        if enlace:
            return enlace
    return ""


def _url_http(datos) -> str:
    if isinstance(datos, str):
        candidato = datos.strip().strip('"').strip("'")
        return candidato if candidato.startswith(("http://", "https://")) else ""
    if not isinstance(datos, dict):
        return ""
    for clave in ("url", "urlPago", "link", "url_pago", "enlace"):
        hallado = _url_http(datos.get(clave))
        if hallado:
            return hallado
    return ""


# El operador no publica OpenAPI de comprobantes. Estas rutas existen detrás
# del mismo gateway que validación/pago; se prueban en ese orden.
_RUTAS_COMPROBANTE = (
    "comprobante",
    "soporte",
    "pdf",
    "soportePago",
    "comprobantePago",
)


def _nombre_adjunto(headers: dict, numero: str) -> str:
    raw = headers.get("content-disposition") or headers.get("Content-Disposition") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', raw, re.I)
    if m:
        return m.group(1).strip()
    tipo = (headers.get("content-type") or "").lower()
    ext = ".zip" if "zip" in tipo else ".pdf"
    return f"comprobante_{numero}{ext}"


def _bytes_de_respuesta(r: httpx.Response) -> tuple[bytes, str]:
    """PDF/ZIP crudo, o JSON con el archivo en base64 / una URL."""
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    raw = r.content or b""
    if raw.startswith(b"%PDF") or "pdf" in ctype:
        return raw, "application/pdf"
    if raw.startswith(b"PK") or "zip" in ctype:
        return raw, "application/zip"
    if not raw:
        raise ErrorOperador("El operador devolvió el comprobante vacío")
    if "json" in ctype or raw[:1] in (b"{", b"["):
        try:
            datos = r.json()
        except ValueError:
            return raw, ctype or "application/octet-stream"
        if isinstance(datos, str):
            datos = {"archivo": datos}
        if not isinstance(datos, dict):
            raise ErrorOperador("El operador no devolvió un comprobante reconocible")
        for clave in ("archivo", "file", "contenido", "comprobante", "pdf",
                      "base64", "data"):
            valor = datos.get(clave)
            if isinstance(valor, str) and valor.strip():
                try:
                    cuerpo = base64.b64decode(valor, validate=False)
                except Exception:
                    continue
                if cuerpo.startswith(b"%PDF"):
                    return cuerpo, "application/pdf"
                if cuerpo.startswith(b"PK"):
                    return cuerpo, "application/zip"
                if len(cuerpo) > 32:
                    return cuerpo, "application/octet-stream"
        url = datos.get("url") or datos.get("urlComprobante") or datos.get("link")
        if url:
            return b"", f"url:{url}"
        raise ErrorOperador(
            f"El operador no trajo el archivo del comprobante: {str(datos)[:240]}")
    return raw, ctype or "application/octet-stream"


def descargar_comprobante(sesion: Sesion, numero_planilla: str,
                          cliente: Optional[httpx.Client] = None
                          ) -> tuple[bytes, str, str]:
    """El recibo de pago de esa planilla numerada: PDF o ZIP.

    PagoSimple y SuAporte lo entregan después de pagar, no el plano tipo 1/2.
    """
    if not sesion.autorizada:
        raise ErrorOperador("Hay que autorizar la sesión sobre el aportante "
                            "antes de pedir el comprobante")
    if sesion.simulada or not modo_real():
        raise ErrorOperador("En simulación no hay comprobante del operador")
    _registrar("comprobante", planilla=numero_planilla)
    propio = cliente is None
    cliente = cliente or _cliente_nuevo()
    ultimo = ""
    try:
        for sufijo in _RUTAS_COMPROBANTE:
            url = f"{_base_planillas()}/v1/planillas/{numero_planilla}/{sufijo}"
            try:
                r = cliente.get(url, headers=sesion.headers)
            except httpx.HTTPError as e:
                ultimo = f"{url}: {e}"
                continue
            if r.status_code in (404, 405):
                ultimo = f"{url} respondió {r.status_code}"
                continue
            if r.status_code != 200:
                ultimo = f"{url} respondió {r.status_code}: {r.text[:300]}"
                if r.status_code in (401, 403):
                    raise ErrorOperador(ultimo)
                continue
            try:
                cuerpo, tipo = _bytes_de_respuesta(r)
            except ErrorOperador as e:
                ultimo = str(e)
                continue
            if tipo.startswith("url:"):
                destino = tipo[4:]
                try:
                    r2 = cliente.get(destino, headers=sesion.headers)
                except httpx.HTTPError as e:
                    ultimo = f"{destino}: {e}"
                    continue
                if r2.status_code != 200:
                    ultimo = f"{destino} respondió {r2.status_code}"
                    continue
                cuerpo, tipo = _bytes_de_respuesta(r2)
                r = r2
            if not cuerpo or tipo.startswith("url:"):
                ultimo = f"{url} no trajo un archivo"
                continue
            return cuerpo, tipo, _nombre_adjunto(r.headers, numero_planilla)
        raise ErrorOperador(
            f"No se pudo bajar el comprobante de {numero_planilla}. {ultimo}")
    finally:
        if propio:
            cliente.close()


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
        f"{_base_planillas()}/v1/administradoras/bdua-ruaf/{tipo_doc}/{num_doc}",
        None, cliente, vacio={"simulado": True})


# ─── Recorrido completo ───────────────────────────────────────────────────────

def interpretar_validacion(respuesta: dict) -> dict:
    """Saca de la respuesta del operador lo que interesa.

    El código de la planilla, los errores y las advertencias vienen anidados en
    `validacionPlanillas`, no en la raíz. Cada error trae el campo exacto del
    registro que lo causó y si el operador puede corregirlo solo.
    """
    if not isinstance(respuesta, dict):
        return {}
    validaciones = respuesta.get("validacionPlanillas") or []
    if not validaciones:
        return {"estado_validacion": respuesta.get("estadoValidacion", "")}

    v = validaciones[0]

    def _lista(clave, tipo):
        return [{
            "tipo": tipo,
            "regla": x.get("idRegla", ""),
            "descripcion": x.get("descripcion", ""),
            "identificacion": x.get("identificacion", ""),
            "linea": x.get("linea", ""),
            "campos": f"{x.get('campoInicial', '')}-{x.get('campoFinal', '')}".strip("-"),
            "autocorrige": str(x.get("autocorreccion", "")).strip().lower() == "si",
        } for x in (v.get(clave) or [])]

    # numeroPlanilla llega en 0 mientras la planilla tenga errores sin corregir.
    numero = v.get("numeroPlanilla") or 0
    return {
        "estado_validacion": respuesta.get("estadoValidacion", ""),
        "codigo_planilla": str(v.get("codigoPlanilla") or ""),
        "numero_planilla": str(numero) if numero else "",
        "errores": _lista("erroresEmpresaPlanilla", "empresa") +
                   _lista("erroresCotizantePlanilla", "cotizante"),
        "advertencias": _lista("advertenciasPlanilla", "advertencia"),
    }


def pedir_correccion(codigo_planilla: str, tipo_doc_aportante: str,
                    num_doc_aportante: str, tipo_archivo: str = "I") -> dict:
    """Pide la corrección automática y vuelve a leer cómo quedó la planilla.

    El recorrido completo, igual que el envío: autenticar, autorizar sobre el
    aportante, corregir y releer. Devolver el estado posterior es la mitad del
    valor, porque es donde se ve qué quedó sin corregir.
    """
    with _cliente_nuevo() as cliente:
        sesion = autenticar(cliente)
        aportante = consultar_aportante(sesion, tipo_doc_aportante, num_doc_aportante, cliente)
        autorizar(sesion, tipo_doc_aportante, num_doc_aportante, cliente,
                  aportante_id=aportante.get("id"))
        respuesta = corregir_planilla(sesion, codigo_planilla,
                                      tipo_archivo=tipo_archivo, cliente=cliente)
        resultado = {"simulado": sesion.simulada, "respuesta": respuesta,
                     "codigo_planilla": str(codigo_planilla)}
        if sesion.simulada:
            return resultado

        # Lo que quedó después de corregir: si algo sigue mal, aquí se ve.
        try:
            resultado["inconsistencias"] = inconsistencias(sesion, codigo_planilla,
                                                           cliente=cliente)
        except ErrorOperador as e:
            log.warning(f"PILA: no se pudieron releer las inconsistencias: {e}")
        for clave, fn in (("totales", totales), ("url_pago", url_pago)):
            try:
                resultado[clave] = fn(sesion, codigo_planilla, cliente=cliente)
            except ErrorOperador:
                pass
        return resultado


def traer_comprobante(numero_planilla: str, tipo_doc_aportante: str,
                      num_doc_aportante: str) -> tuple[bytes, str, str]:
    """Login, autoriza sobre el aportante y baja el comprobante pagado."""
    with _cliente_nuevo() as cliente:
        sesion = autenticar(cliente)
        aportante = consultar_aportante(
            sesion, tipo_doc_aportante, num_doc_aportante, cliente)
        autorizar(sesion, tipo_doc_aportante, num_doc_aportante, cliente,
                  aportante_id=aportante.get("id"))
        return descargar_comprobante(sesion, numero_planilla, cliente)


def enviar_planilla(contenido: str, nombre_archivo: str, tipo_doc_aportante: str,
                    num_doc_aportante: str, tipo_archivo: str = "I") -> dict:
    """Los pasos del recorrido de una vez, reutilizando una sola conexión.

    Devuelve lo que se pueda obtener en cada etapa. Si el operador rechaza la
    planilla, la excepción lleva su mensaje tal cual: es más útil que uno
    nuestro.
    """
    with _cliente_nuevo() as cliente:
        sesion = autenticar(cliente)
        aportante = consultar_aportante(sesion, tipo_doc_aportante, num_doc_aportante, cliente)
        autorizar(sesion, tipo_doc_aportante, num_doc_aportante, cliente,
                  aportante_id=aportante.get("id"))
        respuesta = validar_planilla(sesion, contenido, nombre_archivo,
                                     tipo_archivo=tipo_archivo, cliente=cliente)

        resultado = {"simulado": sesion.simulada, "respuesta": respuesta,
                     "totales": None, "url_pago": ""}
        resultado.update(interpretar_validacion(respuesta))

        # Los totales y el enlace se piden con el código, que el operador asigna
        # apenas recibe la planilla. El número tarda: no lo asigna mientras
        # queden errores. Pedirlos con el número dejaba el enlace vacío aunque
        # el operador ya lo tuviera listo.
        referencia = resultado.get("codigo_planilla") or resultado.get("numero_planilla")
        if referencia:
            try:
                resultado["totales"] = totales(sesion, referencia, cliente=cliente)
            except ErrorOperador as e:
                log.warning(f"PILA: no se pudieron leer los totales de {referencia}: {e}")
            resultado["url_pago"] = enlace_de_pago(
                sesion, resultado.get("codigo_planilla") or "",
                resultado.get("numero_planilla") or "", cliente)
        return resultado
