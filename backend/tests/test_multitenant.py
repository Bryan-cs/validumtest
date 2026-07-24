"""Tests de aislamiento multi-tenant (organizaciones).

Verifican que:
- El superadmin crea organizaciones y sus admins.
- Cada organización solo ve sus propios datos.
- Dos organizaciones pueden tener el mismo documento de afiliado (unicidad compuesta).
- El superadmin (god mode) accede vía header X-Org-Id.
- Un admin NO puede escapar de su organización aunque envíe X-Org-Id de otra.
"""
import pytest


def _login(client, u, p):
    r = client.post("/auth/login", json={"username": u, "password": p, "remember_me": True})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], r.json()


def _h(tok, org=None):
    d = {"Authorization": f"Bearer {tok}"}
    if org is not None:
        d["X-Org-Id"] = str(org)
    return d


def _crear_afiliado(client, tok, nombre, doc, org=None):
    return client.post("/afiliados", headers=_h(tok, org), json={
        "nombre": nombre, "tipo_doc": "CC", "doc": doc, "empresa": "EMP",
        "cliente_txt": "CLI", "servicios": [], "fecha_afiliacion": "2026-01-15"})


def _nombres(resp):
    d = resp.json()
    items = d.get("items", d) if isinstance(d, dict) else d
    return sorted(x.get("nombre") for x in items)


@pytest.fixture(scope="module")
def orgs(client):
    """Crea dos organizaciones nuevas (Gamma y Delta) con sus admins vía superadmin."""
    su_tok, su = _login(client, "superadmin", "super1234")
    assert su["rol"] == "superadmin" and su["organizacion_id"] is None

    r = client.post("/organizaciones", headers=_h(su_tok), json={
        "nombre": "Org Gamma", "admin_username": "gamma_admin", "admin_password": "gamma123"})
    assert r.status_code == 201, r.text
    org_g = r.json()["id"]

    r = client.post("/organizaciones", headers=_h(su_tok), json={
        "nombre": "Org Delta", "admin_username": "delta_admin", "admin_password": "delta123"})
    assert r.status_code == 201, r.text
    org_d = r.json()["id"]

    return {"su": su_tok, "g": org_g, "d": org_d}


def test_admins_tienen_su_organizacion(client, orgs):
    _, g = _login(client, "gamma_admin", "gamma123")
    _, d = _login(client, "delta_admin", "delta123")
    assert g["organizacion_id"] == orgs["g"]
    assert d["organizacion_id"] == orgs["d"]


def test_mismo_documento_en_dos_organizaciones(client, orgs):
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    d_tok, _ = _login(client, "delta_admin", "delta123")
    rg = _crear_afiliado(client, g_tok, "Gina Gamma", "90001")
    rd = _crear_afiliado(client, d_tok, "Dario Delta", "90001")  # mismo doc, otra org
    assert rg.status_code in (200, 201), rg.text
    assert rd.status_code in (200, 201), rd.text


def test_aislamiento_lectura(client, orgs):
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    d_tok, _ = _login(client, "delta_admin", "delta123")
    lg = client.get("/afiliados", headers=_h(g_tok))
    ld = client.get("/afiliados", headers=_h(d_tok))
    assert _nombres(lg) == ["Gina Gamma"]
    assert _nombres(ld) == ["Dario Delta"]


def test_superadmin_god_mode(client, orgs):
    su = orgs["su"]
    lg = client.get("/afiliados", headers=_h(su, orgs["g"]))
    ld = client.get("/afiliados", headers=_h(su, orgs["d"]))
    assert _nombres(lg) == ["Gina Gamma"]
    assert _nombres(ld) == ["Dario Delta"]


def test_superadmin_sin_org_header_rechazado(client, orgs):
    su = orgs["su"]
    r = client.get("/afiliados", headers=_h(su))  # sin X-Org-Id
    assert r.status_code == 400


def test_admin_no_puede_escapar_con_header(client, orgs):
    """gamma_admin envía X-Org-Id de Delta → el header debe ignorarse, sigue viendo solo Gamma."""
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    r = client.get("/afiliados", headers=_h(g_tok, orgs["d"]))
    assert _nombres(r) == ["Gina Gamma"]


def test_usuarios_aislados_por_organizacion(client, orgs):
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    r = client.get("/usuarios", headers=_h(g_tok))
    assert r.status_code == 200
    usernames = sorted(u["username"] for u in r.json())
    assert usernames == ["gamma_admin"]
