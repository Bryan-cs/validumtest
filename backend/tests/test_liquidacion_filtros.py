# -*- coding: utf-8 -*-
"""A quien liquidar, y como encontrarlo.

El orden del trabajo es: primero se factura, despues se liquida. La pantalla
de liquidacion sale de las facturas del periodo, asi que un mes sin facturar
no ofrece a nadie.

Sobre esa lista se busca por cedula —quien llega desde Facturacion tiene el
numero, no el nombre como quedo escrito— y se filtra por grupos: tipo de
documento, subtipo o tipo de cotizante.
"""
import pytest


def _h(token):
    return {"Authorization": f"Bearer {token}"}


GENTE = (
    # doc, nombre, tipo_doc, subtipo, tipo_cotizante, ¿se le factura el mes?
    ("70011001", "PEDRO FILTRO UNO", "CC", "0",  "01", True),
    ("70011002", "MARIA FILTRO DOS", "CE", "22", "03", True),
    ("70011003", "JOSE FILTRO TRES", "CC", "22", "01", True),
    ("70011004", "ANA SIN FACTURA",  "CC", "0",  "01", False),
)


@pytest.fixture(scope="module")
def gente(client, admin_token):
    """Se crean una vez: el cliente y la base viven toda la sesion."""
    for doc, nombre, tipo_doc, subtipo, tipo_cot, con_factura in GENTE:
        r = client.post("/afiliados", headers=_h(admin_token), json={
            "nombre": nombre, "doc": doc, "tipo_doc": tipo_doc,
            "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
            "subtipo": subtipo, "tipo_cotizante": tipo_cot,
        })
        assert r.status_code in (200, 201), r.text
        if not con_factura:
            continue
        r = client.post("/facturas", headers=_h(admin_token), json={
            "doc": doc, "nombre_afiliado": nombre, "anio": "2026", "mes": "9",
            "codigo": f"F{doc}",
        })
        assert r.status_code in (200, 201), r.text


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


def test_sin_filtros_salen_todos_los_facturados(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token)}
    assert {"70011001", "70011002", "70011003"} <= docs


def test_quien_no_tiene_factura_no_aparece(client, admin_token, gente):
    """Es el punto del cambio: sin factura no hay nada que liquidar."""
    docs = {f["doc"] for f in _pendientes(client, admin_token)}
    assert "70011004" not in docs


def test_un_mes_sin_facturar_no_ofrece_a_nadie(client, admin_token, gente):
    r = client.get("/liquidacion/pendientes?anio=2026&mes=3",
                   headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json() == []


def test_filtrar_por_tipo_de_documento(client, admin_token, gente):
    docs = {f["doc"] for f in _pendientes(client, admin_token, tipo_doc="CE")}
    assert docs == {"70011002"}


def test_la_fila_trae_el_codigo_de_su_factura(client, admin_token, gente):
    fila = _pendientes(client, admin_token, q="70011002")[0]
    assert fila["factura_codigo"] == "F70011002"
    assert fila["factura_estado"] == "pendiente"
    assert fila["sin_afiliado"] is False


def test_la_fila_trae_el_subtipo_y_el_hueco_de_la_factura(client, admin_token, gente):
    """Lo que la pantalla necesita para filtrar y para cruzar con Facturacion."""
    fila = _pendientes(client, admin_token, q="70011002")[0]
    assert fila["subtipo"] == "22"
    assert "factura_codigo" in fila and "factura_estado" in fila
