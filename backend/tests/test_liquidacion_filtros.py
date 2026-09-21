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
        # Como las guarda Facturacion de verdad: el mes por su nombre y el
        # año como texto. Crearlas con "9" hacia que el test pasara contra un
        # formato que la aplicacion nunca produce.
        r = client.post("/facturas", headers=_h(admin_token), json={
            "doc": doc, "nombre_afiliado": nombre, "anio": "2026",
            "mes": "Septiembre", "codigo": f"F{doc}",
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
    """Un año que ningun otro test toca: la base es compartida por la sesion."""
    r = client.get("/liquidacion/pendientes?anio=2099&mes=1",
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


# ─── El formato del mes ───────────────────────────────────────────────────────
#
# Facturacion guarda el mes por su nombre y el año como texto. Comparar contra
# enteros reventaba en Postgres —"operator does not exist: character varying =
# integer"— y en SQLite pasaba en silencio sin encontrar nada. Los tests no lo
# vieron porque creaban las facturas con "9", un formato que la aplicacion no
# produce.

@pytest.mark.parametrize("guardado", ["Septiembre", "9", "09"])
def test_el_mes_se_encuentra_como_lo_guarde_facturacion(client, admin_token, guardado):
    doc = f"7002{abs(hash(guardado)) % 10000:04d}"
    client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": f"FORMATO {guardado}", "doc": doc, "tipo_doc": "CC",
        "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
    })
    r = client.post("/facturas", headers=_h(admin_token), json={
        "doc": doc, "nombre_afiliado": f"FORMATO {guardado}",
        "anio": "2026", "mes": guardado, "codigo": f"FMT{doc}",
    })
    assert r.status_code in (200, 201), r.text

    docs = {f["doc"] for f in _pendientes(client, admin_token)}
    assert doc in docs, f"no se encontro la factura guardada con mes={guardado!r}"


def test_el_anio_tambien_es_texto(client, admin_token, gente):
    """Si se comparara como entero, Postgres rechazaria la consulta entera."""
    from routers.liquidacion import pendientes
    import inspect
    fuente = inspect.getsource(pendientes)
    assert "str(anio)" in fuente, "el año debe compararse como texto"
