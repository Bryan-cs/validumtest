"""Tests catálogos PILA — siembra idempotente, derogación y endpoint de lectura."""
import pytest

import models
from services.pila import catalogos


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Contenido del catálogo ───────────────────────────────────────────────────

def test_catalogos_completos():
    assert len(catalogos.TIPO_APORTANTE) == 17
    assert len(catalogos.TIPO_PLANILLA) == 18
    assert len(catalogos.TIPO_COTIZANTE) >= 50
    assert catalogos.ANEXO_VERSION == "30"


def test_codigos_de_la_resolucion_1529_de_2026():
    """Los que agregó la última reforma: si faltan, el anexo quedó viejo."""
    assert catalogos.TIPO_APORTANTE["17"] == "Pagador Recicladores de Oficio"
    assert catalogos.TIPO_COTIZANTE["74"] == "Reciclador de Oficio"
    assert "76" in catalogos.TIPO_COTIZANTE
    assert catalogos.TIPO_PLANILLA["W"].startswith("Planilla Reliquidaciones")


def test_sin_codigos_vacios_ni_duplicados():
    for tipo, datos in catalogos.CATALOGOS.items():
        assert all(c.strip() and n.strip() for c, n in datos.items()), tipo
        assert len(set(datos.values())) == len(datos), f"nombres repetidos en {tipo}"


# ─── Siembra ──────────────────────────────────────────────────────────────────

def test_siembra_es_idempotente(client, db):
    catalogos.sembrar(db)
    segunda = catalogos.sembrar(db)
    assert segunda == {"creados": 0, "actualizados": 0, "derogados": 0}


def test_siembra_deja_el_total_esperado(client, db):
    catalogos.sembrar(db)
    esperado = sum(len(v) for v in catalogos.CATALOGOS.values())
    vigentes = db.query(models.PilaCodigo).filter_by(vigente=True).count()
    assert vigentes == esperado


def test_codigo_fuera_del_anexo_se_deroga_pero_no_se_borra(client, db):
    catalogos.sembrar(db)
    db.add(models.PilaCodigo(tipo="TIPO_PLANILLA", codigo="Q",
                             nombre="Planilla de un anexo viejo", vigente=True))
    db.commit()

    resumen = catalogos.sembrar(db)
    assert resumen["derogados"] == 1

    fila = db.query(models.PilaCodigo).filter_by(tipo="TIPO_PLANILLA", codigo="Q").first()
    assert fila is not None, "una planilla histórica todavía puede apuntar a este código"
    assert fila.vigente is False


def test_nombre_cambiado_se_actualiza(client, db):
    catalogos.sembrar(db)
    fila = db.query(models.PilaCodigo).filter_by(tipo="TIPO_PLANILLA", codigo="E").first()
    fila.nombre = "Nombre viejo"
    db.commit()

    resumen = catalogos.sembrar(db)
    assert resumen["actualizados"] >= 1
    db.refresh(fila)
    assert fila.nombre == catalogos.TIPO_PLANILLA["E"]


# ─── Endpoint ─────────────────────────────────────────────────────────────────

def test_listar_todos(client, admin_token):
    r = client.get("/pila/codigos", headers=_h(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["anexo_version"] == "30"
    assert body["total"] >= 95


def test_filtrar_por_tipo(client, admin_token):
    r = client.get("/pila/codigos?tipo=TIPO_APORTANTE", headers=_h(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 17
    assert all(i["tipo"] == "TIPO_APORTANTE" for i in items)
    assert any(i["codigo"] == "01" and i["nombre"] == "Empleador" for i in items)


def test_tipo_desconocido_rechazado(client, admin_token):
    r = client.get("/pila/codigos?tipo=INVENTADO", headers=_h(admin_token))
    assert r.status_code == 400
    assert "Catálogo desconocido" in r.json()["detail"]


def test_derogados_ocultos_por_defecto(client, admin_token, db):
    db.add(models.PilaCodigo(tipo="TIPO_DOC", codigo="ZZ", nombre="Derogado", vigente=False))
    db.commit()

    visibles = client.get("/pila/codigos?tipo=TIPO_DOC", headers=_h(admin_token)).json()["items"]
    assert all(i["codigo"] != "ZZ" for i in visibles)

    todos = client.get("/pila/codigos?tipo=TIPO_DOC&incluir_derogados=true",
                       headers=_h(admin_token)).json()["items"]
    assert any(i["codigo"] == "ZZ" for i in todos)


def test_empleado_puede_leer(client, empleado_token):
    assert client.get("/pila/codigos", headers=_h(empleado_token)).status_code == 200


def test_requiere_autenticacion(client):
    assert client.get("/pila/codigos").status_code in (401, 403)
