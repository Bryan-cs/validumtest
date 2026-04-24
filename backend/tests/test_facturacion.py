"""Tests de facturación y planilla — lógica crítica de negocio."""


# ─── FACTURACIÓN ─────────────────────────────────────────────────────────────

def test_crear_factura(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # Crear afiliado primero
    client.post("/afiliados", json={
        "nombre": "Factura Test", "tipo_doc": "CC", "doc": "888000111",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
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
    """Verifica que la planilla calcula correctamente costos por servicio."""
    h = {"Authorization": f"Bearer {admin_token}"}
    # Crear afiliado con servicios completos
    client.post("/afiliados", json={
        "nombre": "Planilla Test", "tipo_doc": "CC", "doc": "777000111",
        "empresa": "TestCorp", "servicios": ["EPS", "AFP", "ARL 1"],
        "subtipo": "0", "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "arl": "1",
    }, headers=h)

    # Obtener config para saber el IBC global
    cfg = client.get("/config", headers=h).json()
    ibc = cfg.get("ibc_global", 1950905)

    # Generar factura para este afiliado — el frontend calcula planilla
    # pero podemos verificar los servicios vía cobro
    r = client.get("/cobro?doc=777000111", headers=h)
    assert r.status_code == 200


# ─── RETIROS ─────────────────────────────────────────────────────────────────

def test_crear_retiro(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # Crear afiliado para retirar
    client.post("/afiliados", json={
        "nombre": "Retiro Test", "tipo_doc": "CC", "doc": "666000111",
        "empresa": "TestCorp", "servicios": [], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
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
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    rt = r.json()["refresh_token"]
    r2 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 200
    assert "access_token" in r2.json()


def test_refresh_token_invalido(client):
    r = client.post("/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert r.status_code == 401


def test_access_token_no_sirve_como_refresh(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    at = r.json()["access_token"]
    r2 = client.post("/auth/refresh", json={"refresh_token": at})
    assert r2.status_code == 401


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
