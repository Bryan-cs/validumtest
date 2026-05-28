"""Tests módulo Credenciales de Portales — CRUD, cifrado Fernet, RBAC, reveal."""
import pytest


@pytest.fixture
def cred_payload():
    return {
        "tipo_doc": "NIT",
        "numero_doc": "900123456",
        "titular": "TestCorp SAS",
        "portal": "EPS",
        "entidad": "Sura EPS",
        "usuario_portal": "admin@testcorp.co",
        "clave_portal": "S3cret!Pass#1",
        "obs": "Test note",
    }


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def test_crear_credencial_admin(client, admin_token, cred_payload):
    r = client.post("/credenciales", json=cred_payload, headers=_h(admin_token))
    assert r.status_code == 201
    body = r.json()
    assert body["portal"] == "EPS"
    assert body["entidad"] == "Sura EPS"
    # La clave NUNCA debe volver en respuesta de creación
    assert body["clave_portal"] is None


def test_crear_credencial_empleado(client, empleado_token, cred_payload):
    p = {**cred_payload, "numero_doc": "900222333", "usuario_portal": "emp@x.co"}
    r = client.post("/credenciales", json=p, headers=_h(empleado_token))
    assert r.status_code == 201


def test_crear_portal_invalido_rechazado(client, admin_token, cred_payload):
    p = {**cred_payload, "portal": "FAKE_PORTAL", "numero_doc": "999"}
    r = client.post("/credenciales", json=p, headers=_h(admin_token))
    assert r.status_code == 400
    assert "Portal" in r.json()["detail"]


def test_listar_no_expone_clave(client, admin_token, cred_payload):
    p = {**cred_payload, "numero_doc": "900444555", "usuario_portal": "list@x.co"}
    client.post("/credenciales", json=p, headers=_h(admin_token))
    r = client.get("/credenciales", headers=_h(admin_token))
    assert r.status_code == 200
    for c in r.json():
        assert c["clave_portal"] is None, "GET /credenciales nunca debe traer clave en claro"


def test_actualizar_clave_opcional(client, admin_token, cred_payload):
    p = {**cred_payload, "numero_doc": "900666777", "usuario_portal": "upd@x.co"}
    cred = client.post("/credenciales", json=p, headers=_h(admin_token)).json()

    # Update sin clave_portal: no rota la clave existente
    r = client.put(f"/credenciales/{cred['id']}",
                   json={"entidad": "Sura EPS Renamed"},
                   headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["entidad"] == "Sura EPS Renamed"

    # La clave original sigue funcionando para reveal
    rk = client.get(f"/credenciales/{cred['id']}/clave", headers=_h(admin_token))
    assert rk.status_code == 200
    assert rk.json()["clave"] == "S3cret!Pass#1"


# ─── Cifrado Fernet ───────────────────────────────────────────────────────────

def test_clave_persiste_cifrada(client, admin_token, cred_payload):
    """La clave en DB no debe ser legible en claro."""
    from conftest import TestingSession
    import models

    p = {**cred_payload, "numero_doc": "900888999", "usuario_portal": "enc@x.co",
         "clave_portal": "PlainTextSecret!"}
    client.post("/credenciales", json=p, headers=_h(admin_token))

    db = TestingSession()
    try:
        row = db.query(models.CredencialPortal).filter_by(numero_doc="900888999").first()
        assert row is not None
        assert row.clave_portal != "PlainTextSecret!"
        assert len(row.clave_portal) > 40, "Fernet token debe ser largo"
        # Fernet tokens are base64-url; deben tener prefijo de versión
        assert row.clave_portal.startswith("gAAAAA") or len(row.clave_portal) > 50
    finally:
        db.close()


def test_reveal_devuelve_clave_original(client, admin_token, cred_payload):
    p = {**cred_payload, "numero_doc": "901111222", "usuario_portal": "rev@x.co",
         "clave_portal": "RevealMe_2026!"}
    cred = client.post("/credenciales", json=p, headers=_h(admin_token)).json()

    r = client.get(f"/credenciales/{cred['id']}/clave", headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["clave"] == "RevealMe_2026!"


# ─── RBAC ─────────────────────────────────────────────────────────────────────

def test_eliminar_admin_ok(client, admin_token, cred_payload):
    p = {**cred_payload, "numero_doc": "902333444", "usuario_portal": "del@x.co"}
    cred = client.post("/credenciales", json=p, headers=_h(admin_token)).json()
    r = client.delete(f"/credenciales/{cred['id']}", headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_eliminar_empleado_prohibido(client, admin_token, empleado_token, cred_payload):
    p = {**cred_payload, "numero_doc": "902555666", "usuario_portal": "x@x.co"}
    cred = client.post("/credenciales", json=p, headers=_h(admin_token)).json()
    r = client.delete(f"/credenciales/{cred['id']}", headers=_h(empleado_token))
    assert r.status_code in (401, 403), "Empleado NO debe poder eliminar"


def test_endpoints_requieren_auth(client):
    assert client.get("/credenciales").status_code in (401, 403)
    assert client.post("/credenciales", json={}).status_code in (401, 403)
    assert client.get("/credenciales/1/clave").status_code in (401, 403)


def test_reveal_inexistente_404(client, admin_token):
    r = client.get("/credenciales/9999999/clave", headers=_h(admin_token))
    assert r.status_code == 404


# ─── Audit log ────────────────────────────────────────────────────────────────

def test_reveal_genera_audit(client, empleado_token, admin_token, cred_payload):
    """Cada reveal queda registrado en Actividad (empleado, no admin)."""
    from conftest import TestingSession
    import models

    p = {**cred_payload, "numero_doc": "903777888", "usuario_portal": "aud@x.co"}
    cred = client.post("/credenciales", json=p, headers=_h(admin_token)).json()

    db = TestingSession()
    try:
        before = db.query(models.Actividad).filter(
            models.Actividad.modulo == "Credenciales",
            models.Actividad.accion.contains("reveló"),
        ).count()
    finally:
        db.close()

    client.get(f"/credenciales/{cred['id']}/clave", headers=_h(empleado_token))

    db = TestingSession()
    try:
        after = db.query(models.Actividad).filter(
            models.Actividad.modulo == "Credenciales",
            models.Actividad.accion.contains("reveló"),
        ).count()
        assert after > before, "Reveal de empleado debe quedar en audit log"
    finally:
        db.close()
