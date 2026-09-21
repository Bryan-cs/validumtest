# -*- coding: utf-8 -*-
"""Buscar a quien liquidar.

Quien llega desde Facturacion tiene el numero de cedula en la mano, no el
nombre como quedo escrito en el sistema. Y a veces lo que se quiere ver no es
una persona sino un grupo entero: todas las del subtipo 22, por ejemplo.
"""
import pytest


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def gente(client, admin_token):
    """Se crean una vez: el cliente y la base viven toda la sesion."""
    creados = []
    for doc, nombre, subtipo, tipo_cot in (
        ("70011001", "PEDRO FILTRO UNO", "0", "01"),
        ("70011002", "MARIA FILTRO DOS", "22", "03"),
        ("70011003", "JOSE FILTRO TRES", "22", "01"),
    ):
        r = client.post("/afiliados", headers=_h(admin_token), json={
            "nombre": nombre, "doc": doc, "tipo_doc": "CC",
            "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
            "subtipo": subtipo, "tipo_cotizante": tipo_cot,
        })
        assert r.status_code in (200, 201), r.text
        creados.append(r.json()["id"])
    return creados


def _pendientes(client, admin_token, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/liquidacion/pendientes?anio=2026&mes=9&{qs}",
                   headers=_h(admin_token))
    assert r.status_code == 200, r.text
    return r.json()


def test_se_busca_por_cedula_completa(client, admin_token, gente):
    filas = _pendientes(client, admin_token, q="70011002")
    assert [f["doc"] for f in filas] == ["70011002"]


def test_tambien_por_un_pedazo_de_la_cedula(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token, q="7001100")}
    assert {"70011001", "70011002", "70011003"} <= docs


def test_y_por_nombre_como_antes(client, admin_token, gente):
    filas = _pendientes(client, admin_token, q="MARIA FILTRO")
    assert [f["doc"] for f in filas] == ["70011002"]


def test_filtrar_por_subtipo_trae_el_grupo_entero(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token, subtipo="22")}
    assert {"70011002", "70011003"} <= docs
    assert "70011001" not in docs


def test_varios_subtipos_separados_por_coma(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token, subtipo="0,22")}
    assert {"70011001", "70011002", "70011003"} <= docs


def test_filtrar_por_tipo_de_cotizante(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token,
                                          subtipo="22", tipo_cotizante="03")}
    assert docs == {"70011002"}


def test_el_tipo_de_cotizante_admite_un_digito(client, admin_token, gente):
    """"3" y "03" son el mismo tipo."""
    unos = _pendientes(client, admin_token, subtipo="22", tipo_cotizante="3")
    assert {f["doc"] for f in unos} == {"70011002"}


def test_sin_filtros_salen_todos(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token)}
    assert {"70011001", "70011002", "70011003"} <= docs


def test_la_fila_trae_el_subtipo_y_el_hueco_de_la_factura(client, admin_token, gente):
    """Lo que la pantalla necesita para filtrar y para cruzar con Facturacion."""
    fila = _pendientes(client, admin_token, q="70011002")[0]
    assert fila["subtipo"] == "22"
    assert "factura_codigo" in fila and "factura_estado" in fila
