"""Tests de brechas — permisos, integridad contable, rate limiting, portal."""
import pytest


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cliente_token(client, admin_token):
    """Crea un usuario con rol cliente y devuelve su token."""
    h = {"Authorization": f"Bearer {admin_token}"}
    client.post("/usuarios", json={
        "username": "cliente_test",
        "password": "cli1234",
        "rol": "cliente",
        "nombre": "Cliente Test",
        "cliente_ref": "ClienteTestCorp",
    }, headers=h)
    r = client.post("/auth/login", json={"username": "cliente_test", "password": "cli1234"})
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def factura_pendiente_id(client, admin_token):
    """Devuelve el id de la primera factura pendiente, creándola si no existe."""
    h = {"Authorization": f"Bearer {admin_token}"}
    # Asegurar que existe el afiliado de facturación base
    client.post("/afiliados", json={
        "nombre": "Gaps Test", "tipo_doc": "CC", "doc": "111333555",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
    }, headers=h)
    r = client.post("/facturas", json={
        "nombre_afiliado": "Gaps Test", "doc": "111333555",
        "cliente": "TestCorp", "mes": "Marzo", "anio": "2026",
        "periodo": "", "estado": "pendiente",
        "ingresos": 200000, "costos": 80000, "costo_adm": 20000,
        "conceptos_extra": 0, "utilidad": 999999,  # valor falso — debe recalcularse
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)
    r2 = client.get("/facturas?doc=111333555&estado=pendiente", headers=h)
    items = r2.json().get("items", [])
    return items[0]["id"] if items else None


@pytest.fixture(scope="module")
def factura_pagada_id(client, admin_token, factura_pendiente_id):
    """Paga la factura de factura_pendiente_id y devuelve su id."""
    if not factura_pendiente_id:
        return None
    h = {"Authorization": f"Bearer {admin_token}"}
    client.patch(f"/facturas/{factura_pendiente_id}/pagar?banco=Nequi", headers=h)
    return factura_pendiente_id


# ─── PERMISOS: EMPLEADO NO PUEDE VER REPORTES FINANCIEROS ────────────────────

def test_empleado_bloqueado_dashboard_clientes(client, empleado_token):
    r = client.get("/dashboard/clientes",
                   headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 403


def test_empleado_bloqueado_dashboard_cliente_especifico(client, empleado_token):
    r = client.get("/dashboard/cliente/TestCorp",
                   headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 403


# ─── PERMISOS: EMPLEADO NO PUEDE MODIFICAR CONFIG ────────────────────────────

def test_empleado_bloqueado_update_config(client, empleado_token):
    r = client.put("/config", json={"ibc_global": 9999999},
                   headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 403


# ─── REGRESIÓN: EMPLEADO PUEDE CRUD SEGUIMIENTO ARL ──────────────────────────

def test_empleado_puede_crear_seguimiento_arl(client, empleado_token):
    r = client.post("/seguimiento-arl", json={
        "nombre": "Test ARL", "documento": "999888777",
        "cliente": "TestCorp", "observaciones": "Pendiente revisión",
    }, headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 201


def test_empleado_puede_listar_seguimiento_arl(client, empleado_token):
    r = client.get("/seguimiento-arl",
                   headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_empleado_puede_editar_seguimiento_arl(client, empleado_token, admin_token):
    # Obtener un registro para editar
    h_emp = {"Authorization": f"Bearer {empleado_token}"}
    h_adm = {"Authorization": f"Bearer {admin_token}"}
    rows = client.get("/seguimiento-arl", headers=h_adm).json()
    if not rows:
        pytest.skip("No hay registros de seguimiento ARL")
    rid = rows[0]["id"]
    r = client.put(f"/seguimiento-arl/{rid}", json={"observaciones": "Actualizado por empleado"},
                   headers=h_emp)
    assert r.status_code == 200


def test_empleado_puede_eliminar_seguimiento_arl(client, empleado_token, admin_token):
    h_emp = {"Authorization": f"Bearer {empleado_token}"}
    h_adm = {"Authorization": f"Bearer {admin_token}"}
    # Crear un registro para luego borrarlo
    r = client.post("/seguimiento-arl", json={
        "nombre": "Borrar ARL", "documento": "111222333",
        "cliente": "TestCorp", "observaciones": "A borrar",
    }, headers=h_adm)
    rid = r.json()["id"]
    r2 = client.delete(f"/seguimiento-arl/{rid}", headers=h_emp)
    assert r2.status_code == 200


# ─── INTEGRIDAD CONTABLE: UTILIDAD RECALCULADA SERVER-SIDE ───────────────────

def test_utilidad_calculada_server_side(client, admin_token, factura_pendiente_id):
    """PUT /facturas/{id} ignora utilidad enviada — la recalcula: ingresos-costos-costo_adm+extra."""
    if not factura_pendiente_id:
        pytest.skip("No se pudo crear la factura de prueba")
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"/facturas/{factura_pendiente_id}", json={
        "ingresos": 200000,
        "costos": 80000,
        "costo_adm": 20000,
        "conceptos_extra": 0,
        "utilidad": 999999,  # valor manipulado — debe ignorarse
    }, headers=h)
    assert r.status_code == 200
    utilidad_real = r.json()["utilidad"]
    # 200000 - 80000 - 20000 + 0 = 100000
    assert utilidad_real == 100000, (
        f"Utilidad debe calcularse server-side como 100000, el server devolvió {utilidad_real}"
    )


# ─── INTEGRIDAD CONTABLE: FACTURA PAGADA NO CAMBIA PERÍODO ───────────────────

def test_factura_pagada_no_puede_cambiar_mes(client, admin_token, factura_pagada_id):
    """PUT /facturas/{id} con mes diferente en factura pagada → 400."""
    if not factura_pagada_id:
        pytest.skip("No se pudo obtener la factura pagada")
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"/facturas/{factura_pagada_id}", json={"mes": "Diciembre"},
                   headers=h)
    assert r.status_code == 400, (
        f"Esperaba 400 al cambiar mes de factura pagada, got {r.status_code}"
    )


def test_factura_pagada_no_puede_cambiar_anio(client, admin_token, factura_pagada_id):
    """PUT /facturas/{id} con anio diferente en factura pagada → 400."""
    if not factura_pagada_id:
        pytest.skip("No se pudo obtener la factura pagada")
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put(f"/facturas/{factura_pagada_id}", json={"anio": "2020"},
                   headers=h)
    assert r.status_code == 400, (
        f"Esperaba 400 al cambiar anio de factura pagada, got {r.status_code}"
    )


# ─── INTEGRIDAD CONTABLE: FACTURA PAGADA NO SE PUEDE BORRAR ──────────────────

def test_factura_pagada_no_puede_borrarse(client, admin_token, factura_pagada_id):
    """DELETE /facturas/{id} sin force=true en factura pagada → 400."""
    if not factura_pagada_id:
        pytest.skip("No se pudo obtener la factura pagada")
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.delete(f"/facturas/{factura_pagada_id}", headers=h)
    assert r.status_code == 400, (
        f"Esperaba 400 al borrar factura pagada sin force, got {r.status_code}"
    )


# ─── PORTAL: AISLAMIENTO POR CLIENTE ─────────────────────────────────────────

def test_portal_cliente_solo_ve_sus_afiliados(client, admin_token, cliente_token):
    """Cliente con cliente_ref=ClienteTestCorp no ve afiliados de TestCorp."""
    h_adm = {"Authorization": f"Bearer {admin_token}"}
    h_cli = {"Authorization": f"Bearer {cliente_token}"}

    # Crear afiliado en TestCorp (diferente empresa al cliente_ref del token)
    client.post("/afiliados", json={
        "nombre": "Otro Cliente Afiliado", "tipo_doc": "CC", "doc": "200300400",
        "empresa": "TestCorp", "servicios": [], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "cliente_txt": "TestCorp",
    }, headers=h_adm)

    r = client.get("/portal/afiliados", headers=h_cli)
    assert r.status_code == 200
    docs = [a["doc"] for a in r.json()]
    assert "200300400" not in docs, (
        "El cliente no debe ver afiliados de otro cliente"
    )


def test_portal_empleado_bloqueado(client, empleado_token):
    """Empleado no puede acceder al portal de cliente."""
    r = client.get("/portal/afiliados",
                   headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 403


# ─── REPORTES: EXCEL VÁLIDO ───────────────────────────────────────────────────

def test_reporte_afiliados_excel(client, admin_token):
    """GET /reportes/afiliados devuelve un archivo Excel válido."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/reportes/afiliados", headers=h)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "spreadsheetml" in ct or "octet-stream" in ct, (
        f"Content-Type esperado xlsx, got: {ct}"
    )
    assert len(r.content) > 100, "El archivo Excel no debe estar vacío"


def test_reporte_cobro_excel(client, admin_token):
    """GET /reportes/cobro devuelve un archivo Excel válido."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/reportes/cobro", headers=h)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "spreadsheetml" in ct or "octet-stream" in ct, (
        f"Content-Type esperado xlsx, got: {ct}"
    )
    assert len(r.content) > 100, "El archivo Excel no debe estar vacío"


# ─── RATE LIMITING: 429 TRAS SUPERAR LÍMITE ──────────────────────────────────

def test_rate_limit_devuelve_429(client, admin_token):
    """121 peticiones rápidas al mismo endpoint deben retornar al menos un 429."""
    h = {"Authorization": f"Bearer {admin_token}"}
    statuses = set()
    for _ in range(121):
        r = client.get("/afiliados", headers=h)
        statuses.add(r.status_code)
        if 429 in statuses:
            break
    assert 429 in statuses, (
        "Se esperaba al menos un 429 tras superar el límite de 60/min en /afiliados"
    )
