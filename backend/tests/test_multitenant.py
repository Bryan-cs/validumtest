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


def test_superadmin_no_accede_a_datos(client, orgs):
    """El superadmin no tiene organización → no accede a rutas de datos (sin god mode).
    Para trabajar en una organización debe autenticarse como usuario de esa organización."""
    su = orgs["su"]
    for ep in ["/afiliados", "/dashboard", "/usuarios"]:
        r = client.get(ep, headers=_h(su))
        assert r.status_code == 403, f"{ep} debería ser 403 para superadmin, fue {r.status_code}"
    # El header X-Org-Id ya no da acceso (god mode eliminado).
    r = client.get("/afiliados", headers=_h(su, orgs["g"]))
    assert r.status_code == 403


def test_admin_no_puede_escapar_con_header(client, orgs):
    """gamma_admin envía X-Org-Id de Delta → el header es inerte, sigue viendo solo Gamma."""
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    r = client.get("/afiliados", headers=_h(g_tok, orgs["d"]))
    assert _nombres(r) == ["Gina Gamma"]


def test_usuarios_aislados_por_organizacion(client, orgs):
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    r = client.get("/usuarios", headers=_h(g_tok))
    assert r.status_code == 200
    usernames = sorted(u["username"] for u in r.json())
    assert usernames == ["gamma_admin"]


def test_dashboard_organizaciones_superadmin(client, orgs):
    """El dashboard del superadmin muestra estados de afiliados agregados por organización."""
    su = orgs["su"]
    r = client.get("/organizaciones/dashboard", headers=_h(su))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "organizaciones" in data and "totales" in data
    por_id = {o["id"]: o for o in data["organizaciones"]}
    g = por_id[orgs["g"]]
    # Gina Gamma creada con estado_srv por defecto ACTIVO
    assert g["total"] >= 1 and g["activos"] >= 1
    assert set(g.keys()) >= {"total", "activos", "suspendidos", "no_encontrados", "otros", "usuarios"}
    # admin normal NO accede al dashboard de organizaciones
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    assert client.get("/organizaciones/dashboard", headers=_h(g_tok)).status_code == 403


def test_ingresos_organizaciones(client, orgs):
    """Ingresos: el ingreso del SaaS es la UTILIDAD del mes de cada organización."""
    from datetime import datetime, timezone, timedelta
    hoy = datetime.now(timezone(timedelta(hours=-5)))
    MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    su = orgs["su"]
    r = client.get("/organizaciones/ingresos", headers=_h(su))
    assert r.status_code == 200, r.text
    data = r.json()
    g = {o["id"]: o for o in data["organizaciones"]}[orgs["g"]]
    # Sin facturas del mes la utilidad es 0, y el ingreso la sigue
    assert g["utilidad_mes"] == 0
    assert g["ingreso_mensual"] == g["utilidad_mes"]
    assert g["ingreso_anual"] == g["ingreso_mensual"] * 12

    # Emitir una factura con utilidad conocida: 500.000 - 300.000 - 20.000 + 5.000 = 185.000
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    r = client.post("/facturas", headers=_h(g_tok), json={
        "doc": "77700001", "mes": MESES[hoy.month], "anio": str(hoy.year),
        "cliente": "Cliente Gamma", "ingresos": 500_000, "costos": 300_000,
        "costo_adm": 20_000, "conceptos_extra": 5_000,
    })
    assert r.status_code == 201, r.text

    r = client.get("/organizaciones/ingresos", headers=_h(su))
    g = {o["id"]: o for o in r.json()["organizaciones"]}[orgs["g"]]
    assert g["utilidad_mes"] == 185_000, g
    assert g["ingreso_mensual"] == 185_000
    assert g["ingreso_anual"] == 185_000 * 12
    if g["afiliados"]:
        assert g["utilidad_por_afiliado"] == 185_000 / g["afiliados"]

    # precio_afiliado sigue existiendo como campo editable aunque ya no define el ingreso
    r = client.patch(f"/organizaciones/{orgs['g']}", headers=_h(su), json={"precio_afiliado": 45_000})
    assert r.status_code == 200, r.text
    # precio negativo rechazado
    r = client.patch(f"/organizaciones/{orgs['g']}", headers=_h(su), json={"precio_afiliado": -5})
    assert r.status_code == 422
    # admin normal no ve ingresos
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    assert client.get("/organizaciones/ingresos", headers=_h(g_tok)).status_code == 403


def test_ingresos_mensuales_snapshot(client, orgs):
    """El resumen mensual crea/refresca el snapshot del mes en curso por organización."""
    from datetime import datetime, timezone, timedelta
    hoy = datetime.now(timezone(timedelta(hours=-5)))
    su = orgs["su"]
    r = client.get("/organizaciones/ingresos-mensuales", headers=_h(su))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["anio"] == hoy.year
    mes_actual = next((m for m in data["meses"] if m["mes"] == hoy.month), None)
    assert mes_actual is not None, "Debe existir snapshot del mes en curso"
    # Gamma aparece en el desglose; el ingreso guardado es la utilidad del mes, no
    # afiliados × precio (el snapshot refleja lo mismo que muestra /ingresos)
    g = next((o for o in mes_actual["organizaciones"] if o["id"] == orgs["g"]), None)
    assert g is not None and g["afiliados"] >= 1
    ing = next(o for o in client.get("/organizaciones/ingresos", headers=_h(su)).json()
               ["organizaciones"] if o["id"] == orgs["g"])
    assert g["ingreso"] == ing["utilidad_mes"]
    # Segunda consulta: idempotente (upsert, no duplica)
    r2 = client.get("/organizaciones/ingresos-mensuales", headers=_h(su))
    m2 = next(m for m in r2.json()["meses"] if m["mes"] == hoy.month)
    ids = [o["id"] for o in m2["organizaciones"]]
    assert len(ids) == len(set(ids)), "No debe duplicar snapshots por organización"
    # admin normal no accede
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    assert client.get("/organizaciones/ingresos-mensuales", headers=_h(g_tok)).status_code == 403


def test_facturar_organizacion(client, orgs):
    """Facturar emite UNA factura por org/mes por la utilidad; pagable y no duplicable."""
    su = orgs["su"]
    ing = next(o for o in client.get("/organizaciones/ingresos", headers=_h(su)).json()
               ["organizaciones"] if o["id"] == orgs["g"])
    # emitir factura del mes en curso para Gamma
    r = client.post(f"/organizaciones/{orgs['g']}/facturar", headers=_h(su))
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["afiliados"] >= 1
    # el monto debe cuadrar con lo que muestra el panel, no con afiliados × precio
    assert f["monto"] == ing["utilidad_mes"]
    assert f["estado"] == "pendiente"
    # duplicado del mismo período → rechazado
    r2 = client.post(f"/organizaciones/{orgs['g']}/facturar", headers=_h(su))
    assert r2.status_code == 400
    # listado con totales
    r3 = client.get("/organizaciones/facturas", headers=_h(su))
    assert r3.status_code == 200
    data = r3.json()
    assert any(x["id"] == f["id"] for x in data["facturas"])
    assert data["totales"]["pendiente"] >= f["monto"]
    # marcar pagada
    r4 = client.patch(f"/organizaciones/facturas/{f['id']}/pagar", headers=_h(su))
    assert r4.status_code == 200 and r4.json()["estado"] == "pagada"
    # anular
    assert client.delete(f"/organizaciones/facturas/{f['id']}", headers=_h(su)).status_code == 200
    # admin normal no factura
    g_tok, _ = _login(client, "gamma_admin", "gamma123")
    assert client.post(f"/organizaciones/{orgs['g']}/facturar", headers=_h(g_tok)).status_code == 403


def test_borrar_organizacion_limpia_datos_y_permite_recrear(client, orgs):
    """Borrar una org elimina TODOS sus datos (Config/Listas/afiliados/usuarios), sin dejar
    filas huérfanas que colisionen al recrear (regresión del 500 UNIQUE config.organizacion_id)."""
    su = orgs["su"]
    # crear org temporal con su admin
    r = client.post("/organizaciones", headers=_h(su), json={
        "nombre": "Org Temp", "admin_username": "temp_admin", "admin_password": "temp123"})
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    # el admin crea un afiliado
    t_tok, _ = _login(client, "temp_admin", "temp123")
    assert _crear_afiliado(client, t_tok, "Tito Temp", "70001").status_code in (200, 201)
    # borrar la org
    assert client.delete(f"/organizaciones/{org_id}", headers=_h(su)).status_code == 200
    # recrear con el MISMO username → no debe fallar por datos huérfanos
    r2 = client.post("/organizaciones", headers=_h(su), json={
        "nombre": "Org Temp 2", "admin_username": "temp_admin", "admin_password": "temp123"})
    assert r2.status_code == 201, f"recrear falló: {r2.status_code} {r2.text}"
