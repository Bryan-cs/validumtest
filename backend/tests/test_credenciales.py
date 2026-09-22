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


# ─── Clave de API por empresa (Pago Simple / SuAporte) ───────────────────────

def test_clave_api_se_guarda_cifrada_y_no_sale_en_el_listado(
        client, admin_token, cred_payload):
    p = {**cred_payload, "portal": "Pago Simple", "numero_doc": "900111222",
         "usuario_portal": "CC900111222", "clave_portal": "pass-empresa",
         "clave_api": "api-key-de-esta-empresa", "entidad": "Empresa Uno"}
    r = client.post("/credenciales", json=p, headers=_h(admin_token))
    assert r.status_code == 201
    assert r.json().get("clave_api") in (None, False, "")
    listed = client.get("/credenciales", headers=_h(admin_token)).json()
    fila = next(x for x in listed if x["numero_doc"] == "900111222")
    assert fila.get("tiene_clave_api") is True
    assert "api-key" not in str(fila).lower()

    from conftest import TestingSession
    import models
    db = TestingSession()
    try:
        row = db.query(models.CredencialPortal).filter_by(numero_doc="900111222").first()
        assert row.clave_api
        assert row.clave_api != "api-key-de-esta-empresa"
    finally:
        db.close()


def test_cada_nit_resuelve_sus_propias_credenciales_de_simple(
        client, admin_token, cred_payload, db):
    """Dos empresas, dos keys. El envío de A no debe autenticar con las de B."""
    from routers.credenciales import credenciales_de_aportante
    from tenant import set_org, reset_org
    import models

    org = db.query(models.Organizacion).filter_by(slug="org-test").first()
    for nit, usuario, clave in (
        ("800111222", "CC800111222", "key-a"),
        ("800333444", "CC800333444", "key-b"),
    ):
        client.post("/credenciales", json={
            **cred_payload, "portal": "Pago Simple", "numero_doc": nit,
            "usuario_portal": usuario, "clave_portal": f"pass-{nit}",
            "clave_api": clave, "entidad": nit,
        }, headers=_h(admin_token))

    tok = set_org(org.id)
    try:
        ua, pa, ka = credenciales_de_aportante(db, "800111222")
        ub, pb, kb = credenciales_de_aportante(db, "800.333.444")  # NIT con puntos
        assert ua == "CC800111222" and ka == "key-a"
        assert ub == "CC800333444" and kb == "key-b"
        assert pa != pb
        assert credenciales_de_aportante(db, "999999999") is None
    finally:
        reset_org(tok)


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
