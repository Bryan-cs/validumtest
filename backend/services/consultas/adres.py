"""Consulta de afiliacion en salud contra ADRES (BDUA).

Fuente oficial:
https://aplicaciones.adres.gov.co/bdua_internet/Pages/ConsultarAfiliadoWeb.aspx

Es un WebForms de ASP.NET con captcha Telerik (RadCaptcha). El flujo obligado es:

  1. GET de la pagina  -> cookies de sesion + __VIEWSTATE + __EVENTVALIDATION +
                          GUID de la imagen del captcha
  2. GET de la imagen  -> se le muestra al empleado
  3. POST del form     -> con el estado anterior + el texto que escribio el empleado

Los tres pasos comparten cookies, asi que el estado de la sesion viaja entre
`iniciar()` y `resolver()` serializado como dict (lo guarda el router en Redis).

El parser es deliberadamente defensivo: busca por ETIQUETA, no por posicion de
celda, y devuelve siempre `campos_crudos` con todo lo que encontro. Si ADRES
reacomoda la tabla, la consulta sigue devolviendo datos y el mapeo se corrige
sin tocar el scraping.
"""
from __future__ import annotations

import base64
import os
import re
import ssl
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any

import httpx
from bs4 import BeautifulSoup

BASE = "https://aplicaciones.adres.gov.co/bdua_internet"
URL_PAGES = f"{BASE}/Pages/"
URL_CONSULTA = f"{URL_PAGES}ConsultarAfiliadoWeb.aspx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 30.0

_CERTS_DIR = os.path.join(os.path.dirname(__file__), "certs")

# Volcado de diagnostico. Vacio = apagado (lo normal). Con ruta, guarda el HTML
# crudo de cada paso para poder ver por que fallo un scraping en un entorno
# donde no se puede reproducir a mano. NUNCA activarlo en produccion sin pensar:
# el HTML del resultado trae datos de salud identificados.
_DEBUG_DIR = os.getenv("CONSULTAS_DEBUG_DIR", "").strip()

# Proxy de salida SOLO para estas consultas. Vacio = conexion directa (lo normal).
#
# Para que existe: el backend corre en Railway (us-east4) y ADRES es un portal
# del Estado colombiano. Puede rechazar IPs de datacenter o de fuera del pais,
# hoy o cuando decida defenderse del scraping. Con esta variable, mover la
# salida a una IP colombiana es un cambio de configuracion, no de codigo.
#
# Formato: http://usuario:clave@host:puerto
# Solo afecta al trafico hacia ADRES; el resto del backend sale igual que antes.
_PROXY = os.getenv("CONSULTAS_PROXY_URL", "").strip() or None


def _cliente(**kw) -> httpx.AsyncClient:
    """AsyncClient con la configuracion comun: TLS verificado y proxy opcional."""
    kw.setdefault("timeout", TIMEOUT)
    kw.setdefault("follow_redirects", True)
    kw["verify"] = _SSL
    if _PROXY:
        kw["proxy"] = _PROXY
    return httpx.AsyncClient(**kw)


def _volcar(nombre: str, contenido: str):
    if not _DEBUG_DIR:
        return
    try:
        os.makedirs(_DEBUG_DIR, exist_ok=True)
        with open(os.path.join(_DEBUG_DIR, nombre), "w", encoding="utf-8") as f:
            f.write(contenido)
    except Exception:
        pass


def _ssl_context() -> ssl.SSLContext:
    """Contexto TLS con verificacion COMPLETA, mas los intermedios que ADRES omite.

    ADRES sirve una cadena incompleta: el leaf lo firma GoDaddy G2 pero el
    servidor adjunta un intermedio de Sectigo que no corresponde. Los navegadores
    lo resuelven bajando el intermedio via AIA; Python no hace AIA fetching y
    falla con CERTIFICATE_VERIFY_FAILED.

    La solucion NO es verify=False: por este canal viajan datos de salud de
    personas identificadas y desactivar la verificacion lo deja expuesto a un
    intermediario. Lo que se hace es aportar el intermedio faltante y seguir
    verificando contra la cadena completa. Ver certs/README.md.
    """
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:
        ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)

    if os.path.isdir(_CERTS_DIR):
        for nombre in sorted(os.listdir(_CERTS_DIR)):
            if nombre.endswith(".pem"):
                try:
                    ctx.load_verify_locations(cafile=os.path.join(_CERTS_DIR, nombre))
                except Exception:
                    pass

    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


_SSL = _ssl_context()

# tipo_doc de BBC -> tipo_doc de ADRES. NIT queda fuera a proposito: BDUA es un
# registro de personas, no de empresas.
TIPOS_DOC = {"CC": "CC", "CE": "CE", "PA": "PA", "PT": "PT", "TI": "TI", "RC": "RC"}


class ErrorConsulta(Exception):
    """Base de los errores de consulta."""


class FuenteNoDisponible(ErrorConsulta):
    """ADRES no respondio, respondio un error HTTP, o cambio de forma."""


class CaptchaIncorrecto(ErrorConsulta):
    """El codigo de seguridad no coincide. Hay que reiniciar la consulta."""


class SinResultados(ErrorConsulta):
    """La consulta funciono pero el documento no esta en BDUA."""


@dataclass
class EstadoConsulta:
    """Todo lo necesario para completar el POST. Serializable a JSON."""
    tipo_doc: str
    doc: str
    cookies: dict
    viewstate: str
    viewstate_generator: str
    event_validation: str
    captcha_guid: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EstadoConsulta":
        return cls(**d)


@dataclass
class ResultadoConsulta:
    encontrado: bool
    nombre: Any = None            # compuesto: "NOMBRES APELLIDOS"
    nombres: Any = None
    apellidos: Any = None
    tipo_doc: Any = None
    doc: Any = None
    fecha_nacimiento: Any = None
    eps: Any = None
    regimen: Any = None
    estado: Any = None
    tipo_afiliado: Any = None
    fecha_afiliacion: Any = None
    fecha_fin_afiliacion: Any = None
    departamento: Any = None
    municipio: Any = None
    campos_crudos: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(s: str) -> str:
    """minusculas sin tildes ni espacios repetidos - para comparar etiquetas."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _hidden(soup: BeautifulSoup, name: str) -> str:
    el = soup.find("input", {"name": name})
    return (el.get("value") or "") if el else ""


_OCULTO = re.compile(r"(visibility\s*:\s*hidden|display\s*:\s*none)", re.I)

_POPUP = re.compile(r"window\.open\s*\(\s*['\"]([^'\"]*RespuestaConsulta[^'\"]*)['\"]", re.I)


def _url_popup(html: str):
    """URL relativa del resultado, si ADRES la emitio.

    El resultado NO viene en el cuerpo del POST: la pagina responde con un
    `window.open('RespuestaConsulta.aspx?tokenId=...')` y el dato vive alli.
    Que haya popup es tambien la senal de que la consulta salio bien.
    """
    m = _POPUP.search(html or "")
    return m.group(1).lstrip("/") if m else None


def _texto_visible(soup: BeautifulSoup) -> str:
    """Texto que el usuario REALMENTE ve.

    ASP.NET deja sus validadores en el HTML de forma permanente, apagados con
    `visibility:hidden`, y los enciende por JavaScript cuando corresponde. La
    pagina de ADRES trae siempre, ocultos:

        RegularExpressionValidator1  "Numero de Identificacion No Valida."
        RequiredFieldValidator1      "El campo Numero ... es requerido"

    Leer el texto crudo hace que una consulta exitosa parezca un error. Por eso
    se descartan los nodos ocultos antes de buscar mensajes.
    """
    copia = BeautifulSoup(str(soup), "html.parser")
    for tag in copia.find_all(["script", "style", "noscript"]):
        tag.decompose()
    for tag in copia.find_all(style=_OCULTO):
        tag.decompose()
    for tag in copia.find_all(attrs={"hidden": True}):
        tag.decompose()
    return _norm(copia.get_text(" ", strip=True))


def _captcha_guid(soup: BeautifulSoup) -> str:
    img = soup.find("img", {"id": re.compile(r"CaptchaImage", re.I)})
    src = (img.get("src") or "") if img else ""
    m = re.search(r"guid=([0-9a-fA-F-]{36})", src)
    if m:
        return m.group(1)
    # Fallback: el GUID tambien viaja en el script de inicializacion del RadCaptcha.
    m = re.search(r"guid=([0-9a-fA-F-]{36})", str(soup))
    if not m:
        raise FuenteNoDisponible("ADRES no devolvio el codigo de seguridad")
    return m.group(1)


class ConsultaADRES:
    """Cliente de la consulta BDUA. Sin estado propio: todo viaja en EstadoConsulta."""

    @staticmethod
    def tipo_doc_soportado(tipo_doc: str) -> bool:
        return (tipo_doc or "").upper() in TIPOS_DOC

    @staticmethod
    async def iniciar(tipo_doc: str, doc: str):
        """Abre sesion con ADRES y devuelve (EstadoConsulta, imagen PNG del captcha)."""
        tipo_doc = (tipo_doc or "CC").upper()
        if tipo_doc not in TIPOS_DOC:
            raise ErrorConsulta(
                "ADRES no consulta documentos tipo " + tipo_doc +
                ". Soportados: " + ", ".join(sorted(TIPOS_DOC))
            )

        headers = {"User-Agent": UA, "Accept-Language": "es-CO,es;q=0.9"}
        try:
            async with _cliente(headers=headers) as cli:
                r = await cli.get(URL_CONSULTA)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")

                vs = _hidden(soup, "__VIEWSTATE")
                if not vs:
                    raise FuenteNoDisponible("ADRES no devolvio __VIEWSTATE")

                guid = _captcha_guid(soup)
                img = await cli.get(
                    BASE + "/Telerik.Web.UI.WebResource.axd",
                    params={"type": "rca", "isc": "true", "guid": guid},
                    headers={"Referer": URL_CONSULTA},
                )
                img.raise_for_status()
                if not img.content:
                    raise FuenteNoDisponible("ADRES devolvio un captcha vacio")

                estado = EstadoConsulta(
                    tipo_doc=TIPOS_DOC[tipo_doc],
                    doc=doc,
                    cookies=dict(cli.cookies),
                    viewstate=vs,
                    viewstate_generator=_hidden(soup, "__VIEWSTATEGENERATOR"),
                    event_validation=_hidden(soup, "__EVENTVALIDATION"),
                    captcha_guid=guid,
                )
                return estado, img.content
        except httpx.HTTPError as e:
            raise FuenteNoDisponible(
                "No se pudo contactar a ADRES: " + type(e).__name__) from e

    @staticmethod
    async def resolver(estado: EstadoConsulta, captcha: str) -> "ResultadoConsulta":
        """Envia el formulario con el captcha resuelto por el empleado."""
        if not (captcha or "").strip():
            raise CaptchaIncorrecto("Escribe el codigo de seguridad")

        data = {
            "RadScriptManager1_TSM": "",
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": estado.viewstate,
            "__VIEWSTATEGENERATOR": estado.viewstate_generator,
            "__EVENTVALIDATION": estado.event_validation,
            "tipoDoc": estado.tipo_doc,
            "txtNumDoc": estado.doc,
            "Capcha$CaptchaTextBox": captcha.strip(),
            "Capcha_ClientState": "",
            "btnConsultar": "Consultar",
        }
        headers = {
            "User-Agent": UA,
            "Accept-Language": "es-CO,es;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": URL_CONSULTA,
            "Origin": "https://aplicaciones.adres.gov.co",
        }
        try:
            # UN SOLO cliente para el POST y para el popup. El POST es el que
            # crea ASP.NET_SessionId, y el resultado vive en esa sesion: si se
            # abre un cliente nuevo para el popup, ADRES responde 500
            # (NullReferenceException en Presentacion.Pages.RespuestaConsulta).
            async with _cliente(headers=headers, cookies=estado.cookies) as cli:
                r = await cli.post(URL_CONSULTA, data=data)
                r.raise_for_status()
                _volcar("1_post.html", r.text)

                url_resultado = _url_popup(r.text)
                if not url_resultado:
                    # Sin popup no hubo consulta: el formulario explica por que.
                    ConsultaADRES._diagnosticar_formulario(r.text)

                rp = await cli.get(URL_PAGES + url_resultado,
                                   headers={"Referer": URL_CONSULTA})
                rp.raise_for_status()
                _volcar("2_resultado.html", rp.text)
        except httpx.HTTPError as e:
            raise FuenteNoDisponible(
                "ADRES no respondio la consulta: " + type(e).__name__) from e

        return ConsultaADRES.parsear(rp.text)

    # -- parsing --------------------------------------------------------------

    # Etiqueta normalizada de ADRES -> campo nuestro.
    # Los rotulos exactos salen de una respuesta real (2026-09-19); los alias
    # extra cubren variantes por si reacomodan la pagina.
    MAPA_CAMPOS = {
        # tabla 1 — datos de la persona (vertical)
        "tipo de identificacion": "tipo_doc",
        "tipo de documento": "tipo_doc",
        "tipo documento": "tipo_doc",
        "numero de identificacion": "doc",
        "numero de documento": "doc",
        "numero documento": "doc",
        "nombres": "nombres",
        "apellidos": "apellidos",
        "nombre": "nombre",
        "nombre completo": "nombre",
        "fecha de nacimiento": "fecha_nacimiento",
        "departamento": "departamento",
        "municipio": "municipio",
        "ciudad": "municipio",
        # tabla 2 — afiliacion (horizontal)
        "estado": "estado",
        "estado afiliacion": "estado",
        "estado de afiliacion": "estado",
        "entidad": "eps",
        "eps": "eps",
        "entidad actual": "eps",
        "administradora": "eps",
        "regimen": "regimen",
        "tipo de regimen": "regimen",
        "fecha de afiliacion efectiva": "fecha_afiliacion",
        "fecha de afiliacion": "fecha_afiliacion",
        "fecha afiliacion": "fecha_afiliacion",
        "fecha de finalizacion de afiliacion": "fecha_fin_afiliacion",
        "tipo de afiliado": "tipo_afiliado",
        "tipo afiliado": "tipo_afiliado",
    }

    # Encabezados de maquetacion que no son datos.
    ETIQUETAS_BASURA = {"columnas", "datos", "dato", "columna"}

    PATRONES_SIN_RESULTADO = (
        "no se encuentra en bdua",      # literal real de la pagina de resultado
        "no se encontro", "no se encontraron", "no existe", "no registra",
        "no se hallaron", "sin informacion", "no tiene afiliacion",
        "no se encuentra afiliado", "no hay registros",
    )
    # Ojo: deben distinguir el ERROR del rotulo del campo, que siempre esta
    # visible ("Ingrese el codigo de la imagen"). Solo mensajes de fallo.
    PATRONES_CAPTCHA = (
        "codigo ingresado no es valido",   # el literal que devuelve ADRES hoy
        "codigo de seguridad no",
        "codigo no es correcto",
        "codigo incorrecto",
        "codigo invalido",
        "valor ingresado no coincide",
    )

    @classmethod
    def _diagnosticar_formulario(cls, html: str):
        """Por que el POST no produjo resultado. Siempre levanta excepcion.

        Se aplica a la PAGINA DEL FORMULARIO, no a la del resultado: si ADRES no
        emitio el popup, la razon esta aca.
        """
        soup = BeautifulSoup(html, "html.parser")
        # Solo el texto visible: los validadores ocultos de ASP.NET mienten.
        texto = _texto_visible(soup)

        if any(p in texto for p in cls.PATRONES_CAPTCHA):
            raise CaptchaIncorrecto("El codigo de seguridad no coincide. Genera uno nuevo.")
        if "identificacion no valida" in texto:
            raise SinResultados("ADRES rechazo el numero de documento por formato invalido")
        if any(p in texto for p in cls.PATRONES_SIN_RESULTADO):
            raise SinResultados("El documento no esta registrado en BDUA (ADRES)")
        # Verificado 2026-09-19: cuando el documento no esta en BDUA, ADRES no
        # emite mensaje — devuelve el formulario limpio y sin popup.
        if cls._tiene_formulario(soup):
            raise SinResultados("El documento no esta registrado en BDUA (ADRES)")
        raise FuenteNoDisponible(
            "ADRES respondio pero no se reconocio el resultado. "
            "Puede haber cambiado el formulario."
        )

    @classmethod
    def parsear(cls, html: str) -> "ResultadoConsulta":
        """Parsea la PAGINA DE RESULTADO (RespuestaConsulta.aspx)."""
        soup = BeautifulSoup(html, "html.parser")
        texto = _texto_visible(soup)

        if any(p in texto for p in cls.PATRONES_CAPTCHA):
            raise CaptchaIncorrecto("El codigo de seguridad no coincide. Genera uno nuevo.")
        if any(p in texto for p in cls.PATRONES_SIN_RESULTADO):
            raise SinResultados("El documento no esta registrado en BDUA (ADRES)")

        crudos = cls._extraer_pares(soup)
        if not crudos:
            if cls._tiene_formulario(soup):
                raise SinResultados("El documento no esta registrado en BDUA (ADRES)")
            raise FuenteNoDisponible(
                "ADRES respondio pero no se reconocio el resultado. "
                "Puede haber cambiado el formulario."
            )

        res = ResultadoConsulta(encontrado=True, campos_crudos=crudos)
        for etiqueta, valor in crudos.items():
            campo = cls.MAPA_CAMPOS.get(_norm(etiqueta))
            if campo and not getattr(res, campo, None):
                setattr(res, campo, valor)

        # ADRES entrega NOMBRES y APELLIDOS por separado; el formulario de BBC
        # tiene un solo campo "Nombre completo".
        if not res.nombre:
            partes = [p for p in (res.nombres, res.apellidos) if p]
            if partes:
                res.nombre = " ".join(partes)

        if not any([res.nombre, res.eps, res.estado]):
            raise SinResultados("El documento no esta registrado en BDUA (ADRES)")
        return res

    @staticmethod
    def _tiene_formulario(soup: BeautifulSoup) -> bool:
        """El formulario de busqueda sigue en pie.

        Si esta, ADRES nos entendio y simplemente no hallo al afiliado. Si no
        esta, la pagina dejo de ser la que conocemos y hay que revisar el
        scraper antes de confiar en nada.
        """
        return bool(soup.find("input", {"name": "txtNumDoc"})
                    and soup.find(attrs={"name": "btnConsultar"}))

    @staticmethod
    def _extraer_pares(soup: BeautifulSoup) -> dict:
        """Saca pares etiqueta->valor de las tablas del resultado.

        Cubre las dos formas que usa BDUA: tabla vertical (label | valor por fila)
        y tabla horizontal (fila de encabezados + fila de datos).
        """
        pares = {}

        for tabla in soup.find_all("table"):
            filas = tabla.find_all("tr")
            if not filas:
                continue

            # horizontal: fila de encabezados + una fila de datos con igual nro de celdas
            encabezados = [c.get_text(" ", strip=True) for c in filas[0].find_all(["th", "td"])]
            if len(encabezados) > 2 and len(filas) > 1:
                datos = [c.get_text(" ", strip=True) for c in filas[1].find_all("td")]
                if len(datos) == len(encabezados):
                    for h, v in zip(encabezados, datos):
                        if h and v and h != v:
                            pares.setdefault(h, v)
                    continue

            # vertical: exactamente dos celdas por fila
            for fila in filas:
                celdas = fila.find_all(["td", "th"])
                if len(celdas) != 2:
                    continue
                etiqueta = celdas[0].get_text(" ", strip=True).rstrip(":")
                valor = celdas[1].get_text(" ", strip=True)
                if etiqueta and valor and etiqueta != valor:
                    pares.setdefault(etiqueta, valor)

        return {k: v for k, v in pares.items()
                if len(k) < 60 and len(v) < 200
                and _norm(k) not in ConsultaADRES.ETIQUETAS_BASURA}


def captcha_a_data_url(img: bytes) -> str:
    """data: URL con el mime real. ADRES devuelve JPEG, no PNG."""
    if img[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif img[:4] == b"\x89PNG":
        mime = "image/png"
    elif img[:3] == b"GIF":
        mime = "image/gif"
    else:
        mime = "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(img).decode("ascii")
