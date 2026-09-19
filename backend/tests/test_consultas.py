"""Tests del modulo Consultas (ADRES/BDUA) — version multi-tenant.

Cubren lo que se puede verificar sin salir a internet: el parser del HTML real
de ADRES, el mapeo de EPS contra las listas de la organizacion, el cache, el
RBAC y el aislamiento entre organizaciones.

Lo que NO cubren, a proposito: que el POST real a ADRES funcione. Eso depende
de una fuente externa con captcha y se verifica con `test_contrato_adres.py`,
marcado `red` y excluido de CI (ver pytest.ini).
"""
import io
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from services.consultas.adres import (
    CaptchaIncorrecto,
    ConsultaADRES,
    EstadoConsulta,
    FuenteNoDisponible,
    SinResultados,
    captcha_a_data_url,
)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _fixture(nombre):
    ruta = os.path.join(os.path.dirname(__file__), "fixtures", nombre)
    with io.open(ruta, encoding="utf-8") as f:
        return f.read()


def _utcnow():
    return datetime.now(timezone.utc)


# --- parser: HTML real de ADRES ----------------------------------------------

def test_resultado_real_se_mapea_completo():
    """Fixture con la estructura real de RespuestaConsulta.aspx, datos ficticios.

    ADRES la arma en dos tablas: una vertical con la persona y una horizontal
    con la afiliacion. Rotulos capturados de una respuesta real el 2026-09-19.
    """
    r = ConsultaADRES.parsear(_fixture("adres_encontrado.html"))
    assert r.encontrado is True
    assert r.nombres == "MARIA FERNANDA"
    assert r.apellidos == "GOMEZ RIVERA"
    # el formulario de Afiliados tiene un solo campo de nombre
    assert r.nombre == "MARIA FERNANDA GOMEZ RIVERA"
    assert r.doc == "9999999999"
    assert r.tipo_doc == "CC"
    assert r.eps == "NUEVA EPS S.A."
    assert r.regimen == "CONTRIBUTIVO"
    assert r.estado == "ACTIVO"
    assert r.tipo_afiliado == "COTIZANTE"
    assert r.fecha_afiliacion == "01/03/2020"
    assert r.municipio == "BARRANQUILLA"


def test_resultado_no_encontrado_real():
    """Literal de ADRES: "el afiliado con numero de documento X no se encuentra
    en bdua"."""
    with pytest.raises(SinResultados):
        ConsultaADRES.parsear(_fixture("adres_resultado_no_encontrado.html"))


def test_captcha_incorrecto_real_se_detecta():
    with pytest.raises(CaptchaIncorrecto):
        ConsultaADRES.parsear(_fixture("adres_captcha_incorrecto.html"))


def test_validadores_ocultos_de_aspnet_no_se_leen():
    """ADRES deja validadores en el HTML con visibility:hidden, SIEMPRE presentes:

        RegularExpressionValidator1  "Numero de Identificacion No Valida."
        RequiredFieldValidator1      "El campo Numero ... es requerido"

    Leerlos hace que una consulta exitosa parezca un error.
    """
    from bs4 import BeautifulSoup
    from services.consultas.adres import _texto_visible

    html = _fixture("adres_captcha_incorrecto.html")
    crudo = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    visible = _texto_visible(BeautifulSoup(html, "html.parser"))
    assert "requerido" in crudo
    assert "es requerido" not in visible
    assert "no valida" not in visible


def test_popup_solo_cuando_la_consulta_corrio():
    """El resultado NO viene en el POST: ADRES responde con un window.open()
    hacia RespuestaConsulta.aspx y el dato vive alli. Con captcha malo ni
    consulta, asi que no emite popup."""
    from services.consultas.adres import _url_popup

    assert _url_popup(_fixture("adres_captcha_incorrecto.html")) is None
    assert _url_popup(_fixture("adres_post_con_popup.html")) is not None


def test_sin_formulario_si_es_fuente_cambiada():
    with pytest.raises(FuenteNoDisponible):
        ConsultaADRES.parsear("<html><body><h1>Mantenimiento</h1></body></html>")


def test_tipo_doc_soportado():
    assert ConsultaADRES.tipo_doc_soportado("CC")
    assert ConsultaADRES.tipo_doc_soportado("ce")
    # BDUA es registro de personas: NIT no aplica
    assert not ConsultaADRES.tipo_doc_soportado("NIT")


def test_estado_consulta_round_trip():
    e = EstadoConsulta(tipo_doc="CC", doc="123", cookies={"a": "b"}, viewstate="vs",
                       viewstate_generator="g", event_validation="ev", captcha_guid="guid")
    assert EstadoConsulta.from_dict(e.to_dict()) == e


def test_captcha_data_url_detecta_mime_real():
    """ADRES devuelve JPEG, no PNG."""
    assert captcha_a_data_url(b"\xff\xd8\xff\xe0abc").startswith("data:image/jpeg;base64,")
    assert captcha_a_data_url(b"\x89PNG\r\n").startswith("data:image/png;base64,")


# --- endpoints: validacion y RBAC -------------------------------------------

def test_iniciar_rechaza_documento_no_numerico(client, admin_token):
    r = client.post("/consultas/adres/iniciar",
                    json={"tipo_doc": "CC", "doc": "ABC123"}, headers=_h(admin_token))
    assert r.status_code == 422


def test_iniciar_rechaza_nit(client, admin_token):
    r = client.post("/consultas/adres/iniciar",
                    json={"tipo_doc": "NIT", "doc": "900123456"}, headers=_h(admin_token))
    assert r.status_code == 422
    assert "NIT" in r.json()["detail"]


def test_iniciar_sin_token(client):
    r = client.post("/consultas/adres/iniciar", json={"tipo_doc": "CC", "doc": "1019015048"})
    assert r.status_code in (401, 403)


def test_resolver_con_sesion_inexistente(client, admin_token):
    r = client.post("/consultas/adres/resolver",
                    json={"session_id": "no-existe-esta-sesion", "captcha": "ABCD"},
                    headers=_h(admin_token))
    assert r.status_code == 410


def test_empleado_puede_consultar(client, empleado_token):
    """El empleado hace el alta, asi que debe poder consultar. Se valida por
    RBAC, no por red: un doc no numerico corta antes de salir a ADRES."""
    r = client.post("/consultas/adres/iniciar",
                    json={"tipo_doc": "CC", "doc": "ABC"}, headers=_h(empleado_token))
    assert r.status_code == 422


# --- multi-tenant ------------------------------------------------------------

@pytest.fixture
def otra_org(client, db):
    """Segunda organizacion, para probar aislamiento."""
    import models
    from database import provision_organizacion

    existente = db.query(models.Organizacion).filter_by(slug="org-b").first()
    if existente:
        return existente
    org = provision_organizacion(db, nombre="Org B", slug="org-b",
                                 admin_username="adminb", admin_password="adminb1234",
                                 admin_nombre="Admin B")
    db.commit()
    return org


def test_cache_no_cruza_organizaciones(client, db, otra_org):
    """El resultado que consiguio una organizacion NO lo reutiliza otra.

    No es una optimizacion perdida: cada organizacion consulta con la
    autorizacion de su propio titular y su propio rastro de habeas data. Ver
    el resultado de otra seria una fuga entre inquilinos.
    """
    import models
    from tenant import set_org, reset_org
    from routers.consultas import _cache_lookup

    org_a = db.query(models.Organizacion).filter_by(slug="org-test").first()
    assert org_a and otra_org.id != org_a.id

    db.add(models.ConsultaExterna(
        organizacion_id=org_a.id, fuente="adres", tipo_doc="CC", doc="5555555555",
        exito=True, nombre="PEPITO PEREZ",
        respuesta=json.dumps({"nombre": "PEPITO PEREZ"}), usuario="admin",
        creado=_utcnow(), valido_hasta=_utcnow() + timedelta(days=30),
    ))
    db.commit()

    tok = set_org(org_a.id)
    try:
        assert _cache_lookup(db, "adres", "5555555555") is not None
    finally:
        reset_org(tok)

    tok = set_org(otra_org.id)
    try:
        assert _cache_lookup(db, "adres", "5555555555") is None
    finally:
        reset_org(tok)


def test_consulta_externa_entra_en_el_auto_filtro():
    """Si no esta en la lista de tenant.py, el cache se compartiria entre
    organizaciones aunque el modelo tenga organizacion_id."""
    import models
    from tenant import _tenant_models

    assert models.ConsultaExterna in _tenant_models()


def test_iniciar_devuelve_cache_sin_pedir_captcha(client, admin_token, db):
    import models

    org = db.query(models.Organizacion).filter_by(slug="org-test").first()
    datos = {"encontrado": True, "nombre": "JUANA DE ARCO", "eps": "Nueva EPS",
             "regimen": "CONTRIBUTIVO", "estado": "ACTIVO"}
    db.add(models.ConsultaExterna(
        organizacion_id=org.id, fuente="adres", tipo_doc="CC", doc="9999999998",
        exito=True, nombre="JUANA DE ARCO", eps="Nueva EPS",
        respuesta=json.dumps(datos), usuario="admin",
        creado=_utcnow(), valido_hasta=_utcnow() + timedelta(days=30),
    ))
    db.commit()

    r = client.post("/consultas/adres/iniciar",
                    json={"tipo_doc": "CC", "doc": "9999999998"}, headers=_h(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["cacheado"] is True
    assert body["datos"]["nombre"] == "JUANA DE ARCO"
    assert "captcha" not in body


def test_cache_vencido_no_se_usa(client, db):
    import models
    from tenant import set_org, reset_org
    from routers.consultas import _cache_lookup

    org = db.query(models.Organizacion).filter_by(slug="org-test").first()
    db.add(models.ConsultaExterna(
        organizacion_id=org.id, fuente="adres", tipo_doc="CC", doc="8888888888",
        exito=True, respuesta=json.dumps({"nombre": "VIEJO"}), usuario="admin",
        creado=_utcnow() - timedelta(days=60),
        valido_hasta=_utcnow() - timedelta(days=30),
    ))
    db.commit()
    tok = set_org(org.id)
    try:
        assert _cache_lookup(db, "adres", "8888888888") is None
    finally:
        reset_org(tok)


def test_consulta_fallida_no_entra_al_cache(client, db):
    import models
    from tenant import set_org, reset_org
    from routers.consultas import _cache_lookup

    org = db.query(models.Organizacion).filter_by(slug="org-test").first()
    db.add(models.ConsultaExterna(
        organizacion_id=org.id, fuente="adres", tipo_doc="CC", doc="7777777777",
        exito=False, error_detalle="ADRES caido", usuario="admin",
        creado=_utcnow(), valido_hasta=None,
    ))
    db.commit()
    tok = set_org(org.id)
    try:
        assert _cache_lookup(db, "adres", "7777777777") is None
    finally:
        reset_org(tok)


# --- match de EPS contra la lista de la organizacion -------------------------

def test_match_eps_normaliza_sufijos(client, db):
    import models
    from routers.consultas import _match_lista

    org = db.query(models.Organizacion).filter_by(slug="org-test").first()
    db.query(models.Lista).filter(models.Lista.nombre == "eps",
                                  models.Lista.organizacion_id == org.id).delete()
    db.add(models.Lista(organizacion_id=org.id, nombre="eps",
                        items=json.dumps(["Nueva EPS", "Salud Total", "Sura"])))
    db.commit()

    assert _match_lista(db, "eps", "NUEVA EPS S.A.") == "Nueva EPS"
    assert _match_lista(db, "eps", "SALUD TOTAL EPS S.A.") == "Salud Total"
    # sin correspondencia -> None, para que el empleado elija a mano
    assert _match_lista(db, "eps", "EPS QUE NO EXISTE") is None


# --- auditoria ---------------------------------------------------------------

def test_log_consulta_registra_tambien_al_admin(client, db):
    """crud_helpers._log() suprime al admin. Aqui NO: consultar la afiliacion
    en salud de una persona es dato sensible y tiene que dejar rastro."""
    import models
    from routers.consultas import _log_consulta

    org = db.query(models.Organizacion).filter_by(slug="org-test").first()
    antes = db.query(models.Actividad).filter(
        models.Actividad.modulo == "Consultas").count()
    _log_consulta(db, org.id, "admin", "adres", "1019015048", "ok")
    db.commit()
    despues = db.query(models.Actividad).filter(
        models.Actividad.modulo == "Consultas").count()
    assert despues == antes + 1

    fila = (db.query(models.Actividad)
            .filter(models.Actividad.modulo == "Consultas")
            .order_by(models.Actividad.id.desc()).first())
    assert fila.usuario == "admin"
    assert fila.organizacion_id == org.id
    assert "1019015048" in fila.detalle
