# -*- coding: utf-8 -*-
"""El codigo PILA sale del nombre de la administradora.

El formulario guarda el nombre —"Compensar"— y el archivo plano necesita el
codigo —"EPS008"—. Son campos distintos, y el formulario solo llena el
primero. Quien lo llenaba bien se encontraba con que el campo del archivo
salia vacio y el operador rechazaba la planilla con "El codigo de la EPS es
obligatorio cuando hay aporte a salud".
"""
import pytest

from services.pila.catalogos import buscar_codigo, _normalizar


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── La busqueda ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre,esperado", [
    ("Nueva EPS", "EPS037"),
    ("Compensar", "EPS008"),
    ("Famisanar", "EPS017"),
    ("Salud Total", "EPS002"),
    ("Sanitas", "EPS005"),
])
def test_las_eps_del_formulario_encuentran_su_codigo(nombre, esperado):
    assert buscar_codigo("EPS", nombre) == esperado


def test_compensar_es_distinta_segun_el_subsistema():
    """El mismo nombre es una EPS y una caja, con codigos distintos."""
    assert buscar_codigo("EPS", "Compensar") == "EPS008"
    assert buscar_codigo("CCF", "Compensar") == "CCF24"


@pytest.mark.parametrize("nombre,esperado", [
    ("Porvenir", "230301"),
    ("Colpensiones", "25-14"),
    ("Proteccion", "230201"),
])
def test_las_afp_tambien(nombre, esperado):
    assert buscar_codigo("AFP", nombre) == esperado


def test_no_importan_tildes_ni_mayusculas():
    assert buscar_codigo("AFP", "protección") == buscar_codigo("AFP", "PROTECCION")


def test_las_siglas_del_subsistema_no_estorban():
    """El catalogo dice "NUEVA EPS SA." y el formulario "Nueva EPS"."""
    assert _normalizar("NUEVA EPS SA.") == _normalizar("Nueva EPS")


@pytest.mark.parametrize("nombre", ["", "   ", "N/A", "Sin EPS", "Ninguna"])
def test_lo_que_no_nombra_una_administradora_no_devuelve_codigo(nombre):
    assert buscar_codigo("EPS", nombre) == ""


def test_un_nombre_ambiguo_no_adivina():
    """Un codigo equivocado manda los aportes a otra administradora.

    Es mejor dejarlo vacio y que la liquidacion avise, que es lo que hace.
    """
    assert buscar_codigo("EPS", "EPS") == ""


def test_un_tipo_que_no_existe_no_revienta():
    assert buscar_codigo("INVENTADO", "Compensar") == ""


# ─── Al guardar el afiliado ───────────────────────────────────────────────────

def test_elegir_la_eps_en_el_formulario_deja_el_codigo_puesto(client, admin_token):
    r = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "CODIGO AUTOMATICO", "doc": "97000111", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS", "CCF", "AFP"],
        "eps": "Nueva EPS", "ccf": "Compensar", "afp": "Porvenir",
    })
    assert r.status_code in (200, 201), r.text
    quedo = client.get(f"/afiliados/{r.json()['id']}", headers=_h(admin_token)).json()
    assert quedo["cod_eps"] == "EPS037"
    assert quedo["cod_ccf"] == "CCF24"
    assert quedo["cod_afp"] == "230301"


def test_cambiar_la_eps_desde_el_formulario_no_deja_el_codigo_viejo(client, admin_token):
    creado = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "CODIGO CAMBIA", "doc": "97000222", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"], "eps": "Sanitas",
    })
    id_ = creado.json()["id"]
    assert client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()["cod_eps"] == "EPS005"

    client.put(f"/afiliados/{id_}", headers=_h(admin_token), json={
        "nombre": "CODIGO CAMBIA", "doc": "97000222", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"],
        "eps": "Famisanar", "cod_eps": "",
    })
    assert client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()["cod_eps"] == "EPS017"


def test_un_codigo_puesto_a_mano_manda(client, admin_token):
    """Alguien pudo tener una razon para elegir otro: no se le pisa."""
    r = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "CODIGO A MANO", "doc": "97000333", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"],
        "eps": "Nueva EPS", "cod_eps": "EPS002",
    })
    quedo = client.get(f"/afiliados/{r.json()['id']}", headers=_h(admin_token)).json()
    assert quedo["cod_eps"] == "EPS002"


def test_sin_nombre_de_eps_no_se_inventa_codigo(client, admin_token):
    r = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "SIN EPS", "doc": "97000444", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["ARL 4"], "eps": "",
    })
    quedo = client.get(f"/afiliados/{r.json()['id']}", headers=_h(admin_token)).json()
    assert not quedo["cod_eps"]
