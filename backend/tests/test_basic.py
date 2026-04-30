"""Tests básicos de BBC File — cubren flujos críticos sin mocks de DB."""


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── AUTENTICACIÓN ────────────────────────────────────────────────────────────

def test_login_ok(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["rol"] == "admin"


def test_login_bad_password(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrongpass"})
    assert r.status_code == 401


def test_login_user_not_found(client):
    r = client.post("/auth/login", json={"username": "noexiste", "password": "x"})
    assert r.status_code == 401


def test_no_token_returns_403(client):
    r = client.get("/afiliados")
    assert r.status_code in (401, 403)


# ─── AFILIADOS ────────────────────────────────────────────────────────────────

def test_list_afiliados_admin(client, admin_token):
    r = client.get("/afiliados", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


def test_create_and_get_afiliado(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "nombre": "Test Afiliado",
        "tipo_doc": "CC",
        "doc": "999000111",
        "empresa": "TestCorp",
        "cargo": "Tester",
        "eps": "Sura EPS",
        "afp": "Porvenir",
        "ccf": "N/A",
        "arl": "N/A",
        "subtipo": "0",
        "estado": "ACTIVO",
        "estado_srv": "ACTIVO",
        "servicios": ["EPS"],
        "tel": "3001234567",
        "email": "test@test.com",
    }
    r = client.post("/afiliados", json=payload, headers=headers)
    assert r.status_code == 201
    created = r.json()
    assert created["doc"] == "999000111"

    # Verificar que aparece en la lista
    r2 = client.get("/afiliados?q=999000111", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["total"] >= 1


def test_create_afiliado_doc_duplicado(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "nombre": "Duplicado",
        "tipo_doc": "CC",
        "doc": "999000111",  # mismo doc que el test anterior
        "empresa": "X",
        "servicios": [],
        "subtipo": "0",
        "estado": "ACTIVO",
        "estado_srv": "ACTIVO",
    }
    r = client.post("/afiliados", json=payload, headers=headers)
    assert r.status_code == 400


# ─── CONTROL DE ACCESO ────────────────────────────────────────────────────────

def test_empleado_puede_ver_eliminados(client, empleado_token):
    # Empleados tienen acceso a todos los tabs de afiliados incluyendo eliminados
    r = client.get("/eliminados", headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 200


def test_empleado_no_puede_crear_usuario(client, empleado_token):
    r = client.post("/usuarios", json={"username": "x", "password": "x", "rol": "admin"},
                    headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 403


# ─── PORTAL ───────────────────────────────────────────────────────────────────

def test_portal_requiere_rol_cliente_o_admin(client, empleado_token):
    r = client.get("/portal/afiliados",
                   headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 403


def test_portal_admin_puede_ver_afiliados(client, admin_token):
    r = client.get("/portal/afiliados",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_portal_exportar_excel_admin(client, admin_token):
    r = client.get("/portal/exportar-excel",
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("content-type", "")
