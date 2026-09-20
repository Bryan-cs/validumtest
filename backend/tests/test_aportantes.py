"""Tests módulo Aportantes PILA — CRUD, dígito de verificación, validaciones, RBAC."""
import itertools

import pytest

from routers.aportantes import calcular_dv

# La BD de tests es de sesion y no hace rollback entre casos (ver conftest), asi
# que cada test necesita su propio cliente_ref: es unico por organizacion.
_contador = itertools.count(1)


@pytest.fixture
def aportante_payload():
    n = next(_contador)
    return {
        "cliente_ref": f"CARSECOOP-{n}",
        "razon_social": f"CARSECOOP {n} SAS",
        "tipo_doc": "NI",
        "num_doc": f"9001234{n:02d}",
        "tipo_aportante": "01",
        "clase_aportante": "A",
        "cod_arl": "14-11",      # ARL SURA, del catálogo de la UGPP
        "clase_riesgo": "1",
        "cod_depto": "05",       # Antioquia
        "cod_municipio": "001",  # Medellín
    }


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Dígito de verificación ───────────────────────────────────────────────────

@pytest.mark.parametrize("nit,dv", [
    ("890903938", "8"),   # Bancolombia
    ("899999068", "1"),   # Ecopetrol
    ("860002964", "4"),   # Banco de Bogotá
    ("890900608", "9"),   # Grupo Argos
])
def test_calcular_dv_casos_conocidos(nit, dv):
    """NIT públicos reales: comprueban el algoritmo, no su propia salida."""
    assert calcular_dv(nit) == dv


def test_dv_se_calcula_si_no_se_envia(client, admin_token, aportante_payload):
    r = client.post("/aportantes", json=aportante_payload, headers=_h(admin_token))
    assert r.status_code == 201
    assert r.json()["dv"] == calcular_dv(aportante_payload["num_doc"])


def test_dv_errado_se_rechaza(client, admin_token, aportante_payload):
    malo = calcular_dv(aportante_payload["num_doc"])
    malo = "9" if malo != "9" else "8"
    p = {**aportante_payload, "dv": malo}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "dígito de verificación" in r.json()["detail"]


def test_cedula_no_lleva_dv(client, admin_token, aportante_payload):
    p = {**aportante_payload, "tipo_doc": "CC", "num_doc": "1095908234",
         "tipo_persona": "N"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 201
    assert r.json()["dv"] is None


def test_endpoint_dv(client, admin_token):
    r = client.get("/aportantes/dv/900.123-456", headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json() == {"num_doc": "900123456", "dv": calcular_dv("900123456")}


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def test_crear_y_listar(client, admin_token, aportante_payload):
    assert client.post("/aportantes", json=aportante_payload,
                       headers=_h(admin_token)).status_code == 201
    r = client.get("/aportantes", headers=_h(admin_token))
    assert r.status_code == 200
    assert any(a["cliente_ref"] == aportante_payload["cliente_ref"] for a in r.json())


def test_crear_empleado_permitido(client, empleado_token, aportante_payload):
    assert client.post("/aportantes", json=aportante_payload,
                       headers=_h(empleado_token)).status_code == 201


def test_cliente_ref_duplicado_rechazado(client, admin_token, aportante_payload):
    assert client.post("/aportantes", json=aportante_payload,
                       headers=_h(admin_token)).status_code == 201
    p = {**aportante_payload, "num_doc": "900777666"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 409


def test_num_doc_con_puntos_se_normaliza(client, admin_token, aportante_payload):
    p = {**aportante_payload, "num_doc": "900.123.456"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 201
    assert r.json()["num_doc"] == "900123456"


def test_actualizar(client, admin_token, aportante_payload):
    cid = client.post("/aportantes", json=aportante_payload,
                      headers=_h(admin_token)).json()["id"]
    r = client.put(f"/aportantes/{cid}", json={"razon_social": "CARSECOOP LTDA",
                                               "exonerado_parafiscales": True},
                   headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["razon_social"] == "CARSECOOP LTDA"
    assert r.json()["exonerado_parafiscales"] is True


def test_actualizar_num_doc_recalcula_dv(client, admin_token, aportante_payload):
    cid = client.post("/aportantes", json=aportante_payload,
                      headers=_h(admin_token)).json()["id"]
    r = client.put(f"/aportantes/{cid}", json={"num_doc": "830053630"},
                   headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["dv"] == calcular_dv("830053630")


def test_obtener_incluye_conteo_afiliados(client, admin_token, aportante_payload):
    cid = client.post("/aportantes", json=aportante_payload,
                      headers=_h(admin_token)).json()["id"]
    r = client.get(f"/aportantes/{cid}", headers=_h(admin_token))
    assert r.status_code == 200
    assert "afiliados" in r.json()


def test_404_inexistente(client, admin_token):
    assert client.get("/aportantes/99999", headers=_h(admin_token)).status_code == 404


# ─── Validaciones que el operador rechazaría después ──────────────────────────

def test_clase_riesgo_invalida(client, admin_token, aportante_payload):
    p = {**aportante_payload, "clase_riesgo": "9"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "clase_riesgo" in r.json()["detail"]


def test_tipo_doc_invalido(client, admin_token, aportante_payload):
    p = {**aportante_payload, "tipo_doc": "XX"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400


def test_cod_depto_debe_ser_dane(client, admin_token, aportante_payload):
    p = {**aportante_payload, "cod_depto": "5"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "DANE" in r.json()["detail"]


def test_num_doc_no_numerico_rechazado(client, admin_token, aportante_payload):
    p = {**aportante_payload, "num_doc": "ABC123"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 422


# ─── Validación contra el catálogo PILA ───────────────────────────────────────

def test_arl_inexistente_rechazada(client, admin_token, aportante_payload):
    p = {**aportante_payload, "cod_arl": "14-99"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "cod_arl" in r.json()["detail"]


def test_tipo_aportante_inexistente_rechazado(client, admin_token, aportante_payload):
    p = {**aportante_payload, "tipo_aportante": "99"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "tipo_aportante" in r.json()["detail"]


def test_municipio_de_otro_departamento_rechazado(client, admin_token, aportante_payload):
    """05001 es Medellín; 08001 es Barranquilla. 05 + 001 vale, 08 + 001 también,
    pero 05 + 999 no existe."""
    p = {**aportante_payload, "cod_depto": "05", "cod_municipio": "999"}
    r = client.post("/aportantes", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "no pertenece al departamento" in r.json()["detail"]


def test_municipio_valido_aceptado(client, admin_token, aportante_payload):
    p = {**aportante_payload, "cod_depto": "08", "cod_municipio": "001"}  # Barranquilla
    assert client.post("/aportantes", json=p, headers=_h(admin_token)).status_code == 201


# ─── RBAC y protección del histórico ──────────────────────────────────────────

def test_eliminar_solo_admin(client, admin_token, empleado_token, aportante_payload):
    cid = client.post("/aportantes", json=aportante_payload,
                      headers=_h(admin_token)).json()["id"]
    assert client.delete(f"/aportantes/{cid}", headers=_h(empleado_token)).status_code == 403
    assert client.delete(f"/aportantes/{cid}", headers=_h(admin_token)).status_code == 200


def test_requiere_autenticacion(client):
    assert client.get("/aportantes").status_code in (401, 403)


def test_no_se_borra_aportante_con_planillas(client, admin_token, aportante_payload, db):
    import models
    cid = client.post("/aportantes", json=aportante_payload,
                      headers=_h(admin_token)).json()["id"]
    ap = db.query(models.AportantePila).filter_by(id=cid).first()
    db.add(models.PlanillaLiquidacion(
        organizacion_id=ap.organizacion_id, aportante_id=cid, cliente_ref=ap.cliente_ref,
        tipo_planilla="E", periodo_cotizacion="2026-09", periodo_pago="2026-10"))
    db.commit()

    r = client.delete(f"/aportantes/{cid}", headers=_h(admin_token))
    assert r.status_code == 409
    assert "planilla" in r.json()["detail"].lower()
