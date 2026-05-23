"""Tests de facturación y planilla — lógica crítica de negocio."""


# ─── FACTURACIÓN ─────────────────────────────────────────────────────────────

def test_crear_factura(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # Crear afiliado primero
    client.post("/afiliados", json={
        "nombre": "Factura Test", "tipo_doc": "CC", "doc": "888000111",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
    }, headers=h)

    r = client.post("/facturas", json={
        "nombre_afiliado": "Factura Test", "doc": "888000111",
        "cliente": "TestCorp", "mes": "Enero", "anio": "2026",
        "periodo": "", "estado": "pendiente",
        "ingresos": 100000, "costos": 50000, "costo_adm": 10000,
        "conceptos_extra": 0, "utilidad": 40000,
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)
    assert r.status_code == 201
    data = r.json()
    assert data["doc"] == "888000111"
    assert data["codigo"].startswith("FVE")


def test_factura_duplicada_mismo_mes(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/facturas", json={
        "nombre_afiliado": "Factura Test", "doc": "888000111",
        "cliente": "TestCorp", "mes": "Enero", "anio": "2026",
        "ingresos": 100000, "costos": 50000,
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)
    assert r.status_code == 400
    assert "Ya existe" in r.json()["detail"]


def test_factura_doc_vacio_rechazada(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/facturas", json={
        "nombre_afiliado": "X", "doc": "", "mes": "Enero",
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)
    assert r.status_code == 422  # validación Pydantic


def test_listar_facturas(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/facturas", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "items" in body
    assert body["total"] >= 1


def test_pagar_factura(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # Obtener la primera factura pendiente
    r = client.get("/facturas?estado=pendiente", headers=h)
    items = r.json()["items"]
    if not items:
        return  # no hay facturas pendientes para probar
    fid = items[0]["id"]
    r2 = client.patch(f"/facturas/{fid}/pagar?banco=Nequi", headers=h)
    assert r2.status_code == 200
    assert r2.json()["estado"] == "pagado"
    assert r2.json()["banco"] == "Nequi"


def test_pagar_factura_idempotente(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/facturas?estado=pagado", headers=h)
    items = r.json()["items"]
    if not items:
        return
    fid = items[0]["id"]
    r2 = client.patch(f"/facturas/{fid}/pagar", headers=h)
    assert r2.status_code == 200
    assert r2.json()["estado"] == "pagado"


# ─── PLANILLA (cálculo de costos por servicios) ─────────────────────────────

def test_planilla_calculo(client, admin_token):
    """Verifica endpoint calc-planilla (fuente única para el frontend)."""
    h = {"Authorization": f"Bearer {admin_token}"}
    client.post("/afiliados", json={
        "nombre": "Planilla Test", "tipo_doc": "CC", "doc": "777000111",
        "empresa": "TestCorp", "servicios": ["EPS", "AFP", "ARL 1"],
        "subtipo": "0", "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
        "arl": "1",
    }, headers=h)
    afils = client.get("/afiliados", params={"q": "777000111"}, headers=h).json()
    afil_id = afils["items"][0]["id"]
    r = client.get("/facturas/calc-planilla", params={"afiliado_id": afil_id, "dias": 30}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "detalle" in data and len(data["detalle"]) >= 2
    assert data["total"] > 0
    servicios = {d["servicio"] for d in data["detalle"]}
    assert "EPS" in servicios


# ─── RETIROS ─────────────────────────────────────────────────────────────────

def test_crear_retiro(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # Crear afiliado para retirar
    client.post("/afiliados", json={
        "nombre": "Retiro Test", "tipo_doc": "CC", "doc": "666000111",
        "empresa": "TestCorp", "servicios": [], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
    }, headers=h)
    r = client.post("/retiros", json={
        "doc": "666000111", "fecha": "2026-03-26", "motivo": "Renuncia", "obs": "",
    }, headers=h)
    assert r.status_code == 201
    assert "retiro" in r.json()


def test_retiro_duplicado(client, admin_token):
    # Desde el cambio de flujo, al aplicar retiro el afiliado pasa directo a eliminados.
    # Un segundo intento devuelve 404 porque ya no existe en activos.
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/retiros", json={
        "doc": "666000111", "fecha": "2026-03-26", "motivo": "Renuncia", "obs": "",
    }, headers=h)
    assert r.status_code == 404


def test_retiro_afiliado_inexistente(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/retiros", json={
        "doc": "000000000", "fecha": "2026-03-26", "motivo": "Renuncia", "obs": "",
    }, headers=h)
    assert r.status_code == 404


# ─── REFRESH TOKEN ───────────────────────────────────────────────────────────

def test_refresh_token(client):
    # Login — RT llega en cookie httpOnly, TestClient la persiste automáticamente
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    assert r.status_code == 200
    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200
    assert "access_token" in r2.json()
    client.post("/auth/logout")


def test_refresh_token_invalido(client):
    # Sin cookie → 401
    r = client.post("/auth/refresh")
    assert r.status_code == 401


def test_access_token_no_sirve_como_refresh(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    at = r.json()["access_token"]
    # Borrar cookie para aislar el test, luego enviar AT como cookie manualmente
    client.cookies.clear()
    client.cookies.set("refresh_token", at)
    r2 = client.post("/auth/refresh")
    assert r2.status_code == 401
    client.cookies.clear()


# ─── ACTIVIDAD (paginación) ─────────────────────────────────────────────────

def test_actividad_paginacion(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/actividad?limit=5", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "items" in body
    assert len(body["items"]) <= 5


# ─── CONFIG ──────────────────────────────────────────────────────────────────

def test_config_lectura(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/config", headers=h)
    assert r.status_code == 200
    cfg = r.json()
    assert "ibc_global" in cfg
    assert "porcentajes" in cfg


# ─── HEALTH CHECK ────────────────────────────────────────────────────────────

def test_health_incluye_db(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
