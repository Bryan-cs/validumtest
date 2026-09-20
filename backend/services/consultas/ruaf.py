"""Consulta de afiliaciones contra RUAF (SISPRO / Ministerio de Salud).

Fuente: https://ruaf.sispro.gov.co/Filtro.aspx

Es lo que ADRES no da: ademas de salud, trae **pensiones (AFP), riesgos
laborales (ARL), cajas de compensacion (CCF) y cesantias** en una sola consulta.

Flujo (WebForms de ASP.NET, cuatro pasos):

  1. GET  TerminosCondiciones.aspx  -> ViewState
  2. POST TerminosCondiciones.aspx  -> aceptar; el servidor redirige a Filtro.aspx
     (sin este paso Filtro.aspx rebota: la puerta esta en el servidor)
  3. GET  Filtro.aspx               -> ViewState + GUID del captcha
     GET  CaptchaImage.axd?guid=... -> imagen para que la resuelva una persona
  4. POST Filtro.aspx               -> btnVerify (valida el codigo) y luego
                                       btnConsultar (trae el resultado)

A diferencia de ADRES, RUAF pide tambien la **fecha de expedicion** del
documento.

TLS: este host presenta una cadena completa y valida (DigiCert/GeoTrust), asi
que no necesita los intermedios que hay que aportarle a ADRES. Se reutiliza el
mismo contexto igual, que es un superconjunto del almacen por defecto.

Sobre los terminos de uso
-------------------------
El preambulo del Ministerio habilita la consulta al titular "o un tercero en el
marco legal establecido", pero la casilla que se acepta dice "unicamente
solicitare informacion relativa a mi persona". Es una contradiccion del propio
texto. Para que una agremiadora quede del lado del "tercero en el marco legal",
la autorizacion del afiliado tiene que existir y quedar registrada: por eso el
router exige y guarda la referencia de esa autorizacion en cada consulta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

import httpx
from bs4 import BeautifulSoup

# Helpers compartidos con el scraper de ADRES. Viven alli porque fueron escritos
# para ese caso primero; si aparece una tercera fuente conviene extraerlos a un
# modulo comun.
from .adres import (
    CaptchaIncorrecto,
    ErrorConsulta,
    FuenteNoDisponible,
    SinResultados,
    _cliente,
    _hidden,
    _norm,
    _texto_visible,
)

BASE = "https://ruaf.sispro.gov.co"
URL_TERMINOS = f"{BASE}/TerminosCondiciones.aspx"
URL_FILTRO = f"{BASE}/Filtro.aspx"
URL_CAPTCHA = f"{BASE}/CaptchaImage.axd"

# tipo_doc nuestro -> value del select de RUAF (formato "id|sigla")
TIPOS_DOC = {
    "CC": "5|CC", "CE": "4|CE", "TI": "3|TI", "RC": "2|RC", "PA": "6|PA",
    "PT": "15|PT", "PE": "14|PE", "SC": "13|SC", "CD": "10|CD",
}


@dataclass
class EstadoRuaf:
    """Estado de la sesion entre `iniciar()` y `resolver()`. Serializable."""
    tipo_doc: str
    doc: str
    fecha_expedicion: str
    cookies: dict
    viewstate: str
    viewstate_generator: str
    event_validation: str
    captcha_guid: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EstadoRuaf":
        return cls(**d)


@dataclass
class ResultadoRuaf:
    """Afiliaciones por subsistema. `None` = RUAF no reporto ese subsistema."""
    encontrado: bool
    nombre: Any = None
    tipo_doc: Any = None
    doc: Any = None
    salud: list = field(default_factory=list)
    pensiones: list = field(default_factory=list)
    riesgos_laborales: list = field(default_factory=list)
    compensacion_familiar: list = field(default_factory=list)
    cesantias: list = field(default_factory=list)
    # Todo lo que se encontro, aunque no se haya sabido clasificar.
    tablas_crudas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _fecha_ruaf(valor: str) -> str:
    """Normaliza la fecha al formato del datepicker de RUAF (dd/mm/aaaa).

    El <input type="date"> del formulario entrega YYYY-MM-DD; una carga manual
    puede venir dd/mm/aaaa. Se aceptan ambas para que el formato de un control
    del navegador no decida si la consulta funciona.
    """
    v = (valor or "").strip()
    if not v:
        return ""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        a, mes, d = m.groups()
        return f"{d}/{mes}/{a}"
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        d, mes, a = m.groups()
        return f"{int(d):02d}/{int(mes):02d}/{a}"
    return v


def _guid_captcha(soup: BeautifulSoup) -> str:
    m = re.search(r"CaptchaImage\.axd\?guid=([0-9a-fA-F-]{36})", str(soup))
    if not m:
        raise FuenteNoDisponible("RUAF no devolvio el codigo de seguridad")
    return m.group(1)


def _estado_aspnet(soup: BeautifulSoup) -> dict:
    return {
        "__VIEWSTATE": _hidden(soup, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _hidden(soup, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _hidden(soup, "__EVENTVALIDATION"),
    }


class ConsultaRUAF:
    """Cliente de la consulta RUAF. Sin estado propio: viaja en EstadoRuaf."""

    @staticmethod
    def tipo_doc_soportado(tipo_doc: str) -> bool:
        return (tipo_doc or "").upper() in TIPOS_DOC

    @staticmethod
    async def iniciar(tipo_doc: str, doc: str, fecha_expedicion: str):
        """Acepta terminos, abre Filtro.aspx y devuelve (EstadoRuaf, imagen).

        `fecha_expedicion` en el formato que espera el datepicker (dd/mm/aaaa).
        """
        tipo_doc = (tipo_doc or "CC").upper()
        if tipo_doc not in TIPOS_DOC:
            raise ErrorConsulta(
                "RUAF no consulta documentos tipo " + tipo_doc +
                ". Soportados: " + ", ".join(sorted(TIPOS_DOC))
            )
        fecha_expedicion = _fecha_ruaf(fecha_expedicion)
        if not fecha_expedicion:
            raise ErrorConsulta("RUAF exige la fecha de expedicion del documento")

        headers = {"User-Agent": _UA, "Accept-Language": "es-CO,es;q=0.9"}
        try:
            async with _cliente(headers=headers) as cli:
                # 1) terminos
                r = await cli.get(URL_TERMINOS)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                if not _hidden(soup, "__VIEWSTATE"):
                    raise FuenteNoDisponible("RUAF no devolvio __VIEWSTATE en terminos")

                data = _estado_aspnet(soup)
                data.update({
                    "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                    "ctl00$MainContent$RadioButtonList1": "1",   # Acepto
                    "ctl00$MainContent$btnEnviar": "Enviar",
                })
                r2 = await cli.post(URL_TERMINOS, data=data, headers={
                    "Referer": URL_TERMINOS,
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                r2.raise_for_status()
                if "Filtro.aspx" not in str(r2.url):
                    raise FuenteNoDisponible(
                        "RUAF no dejo pasar la pantalla de terminos")

                # 2) formulario de consulta
                soup2 = BeautifulSoup(r2.text, "html.parser")
                guid = _guid_captcha(soup2)
                img = await cli.get(URL_CAPTCHA, params={"guid": guid},
                                    headers={"Referer": URL_FILTRO})
                img.raise_for_status()
                if not img.content:
                    raise FuenteNoDisponible("RUAF devolvio un captcha vacio")

                est = _estado_aspnet(soup2)
                estado = EstadoRuaf(
                    tipo_doc=TIPOS_DOC[tipo_doc],
                    doc=doc,
                    fecha_expedicion=fecha_expedicion,
                    cookies=dict(cli.cookies),
                    viewstate=est["__VIEWSTATE"],
                    viewstate_generator=est["__VIEWSTATEGENERATOR"],
                    event_validation=est["__EVENTVALIDATION"],
                    captcha_guid=guid,
                )
                return estado, img.content
        except httpx.HTTPError as e:
            raise FuenteNoDisponible(
                "No se pudo contactar a RUAF: " + type(e).__name__) from e

    @staticmethod
    async def resolver(estado: EstadoRuaf, captcha: str) -> "ResultadoRuaf":
        """Verifica el codigo y trae el reporte."""
        if not (captcha or "").strip():
            raise CaptchaIncorrecto("Escribe el codigo de seguridad")

        headers = {
            "User-Agent": _UA,
            "Accept-Language": "es-CO,es;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": URL_FILTRO,
            "Origin": BASE,
        }

        def _cuerpo(soup_estado: dict, boton: str, valor: str) -> dict:
            d = dict(soup_estado)
            d.update({
                "__EVENTTARGET": "", "__EVENTARGUMENT": "",
                "ctl00$MainContent$ddlTiposDocumentos": estado.tipo_doc,
                "ctl00$MainContent$txbNumeroIdentificacion": estado.doc,
                "ctl00$MainContent$datepicker": estado.fecha_expedicion,
                "ctl00$MainContent$txtCaptcha": captcha.strip(),
                boton: valor,
            })
            return d

        try:
            async with _cliente(headers=headers, cookies=estado.cookies) as cli:
                base_estado = {
                    "__VIEWSTATE": estado.viewstate,
                    "__VIEWSTATEGENERATOR": estado.viewstate_generator,
                    "__EVENTVALIDATION": estado.event_validation,
                }
                # Paso 1: Verificar (valida el captcha y habilita Consultar)
                r = await cli.post(URL_FILTRO, data=_cuerpo(
                    base_estado, "ctl00$MainContent$btnVerify", "Verificar"))
                r.raise_for_status()
                ConsultaRUAF._revisar_captcha(r.text)

                # Paso 2: Consultar, con el ViewState que devolvio el paso 1.
                soup = BeautifulSoup(r.text, "html.parser")
                r2 = await cli.post(URL_FILTRO, data=_cuerpo(
                    _estado_aspnet(soup),
                    "ctl00$MainContent$btnConsultar", "Consultar"))
                r2.raise_for_status()
        except httpx.HTTPError as e:
            raise FuenteNoDisponible(
                "RUAF no respondio la consulta: " + type(e).__name__) from e

        return ConsultaRUAF.parsear(r2.text)

    # -- parsing --------------------------------------------------------------
    #
    # El resultado es un reporte SSRS (ReportViewer) con tablas ANIDADAS: la
    # tabla externa contiene el reporte entero como si fuera una sola fila, asi
    # que recorrer todas las <table> devuelve basura. Solo sirven las tablas
    # HOJA (las que no contienen otra tabla adentro).
    #
    # Cada seccion se reconoce por la firma de sus columnas, no por el titulo
    # que la precede: en SSRS ese titulo vive en una celda suelta y su posicion
    # en el DOM no es fiable.

    PATRONES_CAPTCHA = (
        "codigo ingresado no es valido", "codigo no es correcto",
        "codigo incorrecto", "codigo invalido", "captcha incorrecto",
        "codigo de seguridad no", "codigo de verificacion",
    )
    PATRONES_SIN_RESULTADO = (
        "no se encontro", "no se encontraron", "no existe", "no registra",
        "no tiene afiliacion", "sin informacion", "no hay registros",
        "no se han reportado afiliaciones",
    )

    # subsistema -> columnas que lo identifican de forma univoca
    FIRMAS = (
        ("basica",                ("primer nombre", "primer apellido")),
        ("riesgos_laborales",     ("actividad economica",)),
        ("compensacion_familiar", ("administradora cf",)),
        ("salud",                 ("tipo de afiliado", "regimen")),
        ("cesantias",             ("regimen", "municipio labora")),
        ("pensiones",             ("regimen", "administradora")),
    )

    @classmethod
    def _revisar_captcha(cls, html: str):
        texto = _texto_visible(BeautifulSoup(html, "html.parser"))
        if any(p in texto for p in cls.PATRONES_CAPTCHA):
            raise CaptchaIncorrecto(
                "El codigo de seguridad no coincide. Genera uno nuevo.")

    @staticmethod
    def _tablas_hoja(soup: BeautifulSoup) -> list:
        """Tablas sin tablas anidadas dentro, como {encabezados, filas}."""
        salida = []
        for t in soup.find_all("table"):
            if t.find("table"):
                continue
            filas = [[c.get_text(" ", strip=True) for c in f.find_all(["th", "td"])]
                     for f in t.find_all("tr")]
            filas = [f for f in filas if any(x.strip() for x in f)]
            if len(filas) < 2:
                continue
            enc = filas[0]
            datos = [dict(zip(enc, f)) for f in filas[1:] if len(f) == len(enc)]
            if datos and any(e.strip() for e in enc):
                salida.append({"encabezados": enc, "filas": datos})
        return salida

    @classmethod
    def _clasificar(cls, encabezados: list):
        cols = {_norm(e) for e in encabezados if e.strip()}
        for destino, firma in cls.FIRMAS:
            if all(any(f in c for c in cols) for f in firma):
                return destino
        return None

    @staticmethod
    def _activa(fila: dict):
        """La fila esta vigente. RUAF usa Activo/Activa/VIGENTE segun subsistema."""
        for k, v in fila.items():
            if "estado" in _norm(k):
                n = _norm(v)
                return n.startswith("activ") or "vigente" in n
        return False

    @classmethod
    def parsear(cls, html: str) -> "ResultadoRuaf":
        soup = BeautifulSoup(html, "html.parser")
        texto = _texto_visible(soup)

        if any(p in texto for p in cls.PATRONES_CAPTCHA):
            raise CaptchaIncorrecto(
                "El codigo de seguridad no coincide. Genera uno nuevo.")

        hojas = cls._tablas_hoja(soup)
        res = ResultadoRuaf(encontrado=False, tablas_crudas=hojas)

        for h in hojas:
            destino = cls._clasificar(h["encabezados"])
            if destino == "basica":
                b = h["filas"][0]
                res.doc = next((v for k, v in b.items()
                                if "identificacion" in _norm(k)), None)
                partes = []
                for etiqueta in ("primer nombre", "segundo nombre",
                                 "primer apellido", "segundo apellido"):
                    val = next((v for k, v in b.items() if _norm(k) == etiqueta), "")
                    if val and val.strip():
                        partes.append(val.strip())
                res.nombre = " ".join(partes) or None
            elif destino:
                getattr(res, destino).extend(h["filas"])

        res.encontrado = bool(res.nombre or res.salud or res.pensiones
                              or res.riesgos_laborales
                              or res.compensacion_familiar or res.cesantias)
        if not res.encontrado:
            if any(p in texto for p in cls.PATRONES_SIN_RESULTADO):
                raise SinResultados("El documento no registra afiliaciones en RUAF")
            if soup.find("input", {"name": "ctl00$MainContent$txbNumeroIdentificacion"}):
                raise SinResultados("El documento no registra afiliaciones en RUAF")
            raise FuenteNoDisponible(
                "RUAF respondio pero no se reconocio el resultado. "
                "Puede haber cambiado el reporte.")
        return res

    @classmethod
    def administradora_vigente(cls, filas: list):
        """Administradora de la primera fila vigente. None si ninguna lo esta.

        Una persona puede arrastrar varias ARL o AFP historicas; sugerir una
        inactiva al formulario seria peor que no sugerir nada.
        """
        for f in filas:
            if cls._activa(f):
                for k, v in f.items():
                    if "administradora" in _norm(k) and v.strip():
                        return v.strip()
        return None


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
