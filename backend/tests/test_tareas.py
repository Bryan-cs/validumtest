"""Tests del módulo Tareas — asignación por empleados y endpoint /tareas/asignables."""
import pytest


@pytest.fixture(scope="module")
def cliente_token(client, admin_token):
    """Crea un usuario rol=cliente y devuelve su access token."""
    h = {"Authorization": f"Bearer {admin_token}"}
    client.post("/usuarios", json={
        "nombre": "Cliente Test", "username": "clientetest",
        "password": "cli1234", "rol": "cliente", "cliente_ref": "CLIENTE DEMO",
    }, headers=h)
    r = client.post("/auth/login", json={"username": "clientetest", "password": "cli1234"})
    assert r.status_code == 200
    return r.json()["access_token"]


# ─── GET /tareas/asignables ───────────────────────────────────────────────────

def test_asignables_admin(client, admin_token):
    r = client.get("/tareas/asignables", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "admin" in usernames
    assert "empleado1" in usernames
    # Sin campos sensibles
    assert all("password" not in u for u in r.json())


def test_asignables_empleado(client, empleado_token):
    r = client.get("/tareas/asignables", headers={"Authorization": f"Bearer {empleado_token}"})
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())


def test_asignables_cliente_prohibido(client, cliente_token):
    r = client.get("/tareas/asignables", headers={"Authorization": f"Bearer {cliente_token}"})
    assert r.status_code == 403


def test_asignables_sin_auth(client):
    r = client.get("/tareas/asignables")
    assert r.status_code in (401, 403)


def test_asignables_excluye_clientes(client, admin_token, cliente_token):
    """Usuarios rol=cliente no aparecen en la lista de asignables."""
    r = client.get("/tareas/asignables", headers={"Authorization": f"Bearer {admin_token}"})
    assert all(u["rol"] in ("admin", "empleado") for u in r.json())
    assert not any(u["username"] == "clientetest" for u in r.json())


# ─── POST /tareas — empleado asigna a otros ───────────────────────────────────

def test_empleado_crea_publica_asignada_a_otro(client, empleado_token):
    h = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "Tarea asignada por empleado", "descripcion": "test",
        "asignado_a": "admin", "privada": False,
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["asignado_a"] == "admin"
    assert body["creado_por"] == "empleado1"
    assert body["privada"] is False


def test_empleado_ve_tarea_que_creo_para_otro(client, empleado_token):
    """Empleado debe ver en su board las tareas que creó aunque estén asignadas a otro."""
    h = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "Visible para creador", "asignado_a": "admin", "privada": False,
    }, headers=h)
    assert r.status_code == 201
    tarea_id = r.json()["id"]

    items = client.get("/tareas", headers=h).json()["items"]
    assert any(t["id"] == tarea_id for t in items)


def test_empleado_asigna_a_inexistente(client, empleado_token):
    h = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "Destino fantasma", "asignado_a": "noexiste999", "privada": False,
    }, headers=h)
    assert r.status_code == 400


def test_empleado_asigna_a_cliente_prohibido(client, empleado_token, cliente_token):
    h = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "No asignable a cliente", "asignado_a": "clientetest", "privada": False,
    }, headers=h)
    assert r.status_code == 400


def test_empleado_sin_asignado_se_autoasigna(client, empleado_token):
    h = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "Sin destinatario", "asignado_a": "", "privada": False,
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["asignado_a"] == "empleado1"


def test_empleado_privada_se_autoasigna(client, empleado_token):
    """Tarea privada siempre queda auto-asignada aunque mande otro username."""
    h = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "Privada propia", "asignado_a": "admin", "privada": True,
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["asignado_a"] == "empleado1"
    assert r.json()["privada"] is True


def test_cliente_forzado_a_privada_autoasignada(client, cliente_token):
    """Cliente no puede asignar a otros: su tarea se fuerza privada y auto-asignada."""
    h = {"Authorization": f"Bearer {cliente_token}"}
    r = client.post("/tareas", json={
        "titulo": "Tarea de cliente", "asignado_a": "admin", "privada": False,
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["asignado_a"] == "clientetest"
    assert r.json()["privada"] is True


def test_notificacion_al_asignado(client, admin_token, empleado_token):
    """Asignar tarea pública a otro genera notificación al destinatario."""
    h_emp = {"Authorization": f"Bearer {empleado_token}"}
    r = client.post("/tareas", json={
        "titulo": "Tarea con notificación", "asignado_a": "admin", "privada": False,
    }, headers=h_emp)
    assert r.status_code == 201

    h_adm = {"Authorization": f"Bearer {admin_token}"}
    notifs = client.get("/tareas/notificaciones", headers=h_adm).json()
    assert any("Tarea con notificación" in n["mensaje"] for n in notifs)
