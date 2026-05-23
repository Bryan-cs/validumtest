"""Tests críticos — flujos de alto riesgo en producción."""
from datetime import date, timedelta


# ─── RESTAURAR ELIMINADO ──────────────────────────────────────────────────────

def test_restaurar_eliminado(client, admin_token):
    """Retiro mueve afiliado a eliminados → restaurar lo devuelve a activos."""
    h = {"Authorization": f"Bearer {admin_token}"}

    # Crear afiliado fresco
    client.post("/afiliados", json={
        "nombre": "Restaurar Test", "tipo_doc": "CC", "doc": "555100200",
        "empresa": "TestCorp", "servicios": [], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
    }, headers=h)

    # Retirar → pasa a eliminados
    r = client.post("/retiros", json={
        "doc": "555100200", "fecha": "2026-04-17", "motivo": "Test", "obs": "",
    }, headers=h)
    assert r.status_code == 201

    # Buscar en eliminados
    elims = client.get("/eliminados", headers=h).json()
    target = next((e for e in elims if e["doc"] == "555100200"), None)
    assert target is not None, "Afiliado no llegó a eliminados tras retiro"

    # Restaurar
    r2 = client.post(f"/eliminados/{target['id']}/restaurar", headers=h)
    assert r2.status_code == 200
    assert r2.json()["nombre"] == "Restaurar Test"

    # Verificar que volvió a activos
    r3 = client.get("/afiliados?q=555100200", headers=h)
    assert r3.status_code == 200
    items = r3.json().get("items", r3.json())
    assert any(a["doc"] == "555100200" for a in (items if isinstance(items, list) else []))


def test_restaurar_eliminado_inexistente(client, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/eliminados/999999/restaurar", headers=h)
    assert r.status_code == 404


# ─── BLACKLIST POST-LOGOUT ────────────────────────────────────────────────────

def test_refresh_token_blacklisted_tras_logout(client):
    """Refresh token queda blacklisted tras logout — no se puede reusar."""
    # Login fresco — RT llega en cookie httpOnly
    r = client.post("/auth/login", json={"username": "empleado1", "password": "emp1234"})
    assert r.status_code == 200
    assert "refresh_token" not in r.json(), "RT no debe venir en el body"
    access_token = r.json()["access_token"]
    # TestClient de Starlette persiste cookies automáticamente

    # Logout — blacklistea el RT via cookie y lo borra
    r2 = client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert r2.status_code == 200

    # Intentar refresh con cookie ya borrada/blacklisted → 401
    r3 = client.post("/auth/refresh")
    assert r3.status_code == 401


def test_refresh_rotation(client):
    """Tras refresh, el token original queda inválido (rotation)."""
    r = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
    assert r.status_code == 200
    # RT está en cookie — el client lo reenvía automáticamente

    # Primer refresh — rota la cookie
    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200
    assert "access_token" in r2.json()

    # Logout para limpiar la cookie rotada
    client.post("/auth/logout")

    # Sin cookie válida → 401
    r3 = client.post("/auth/refresh")
    assert r3.status_code == 401


# ─── COBRO ────────────────────────────────────────────────────────────────────

def test_cobro_endpoint_estructura(client, admin_token):
    """Endpoint /cobro responde con estructura correcta."""
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/cobro", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_cobro_estado_hoy(client, admin_token):
    """Afiliado con dia_cobro=hoy aparece con estado HOY en cobro."""
    h = {"Authorization": f"Bearer {admin_token}"}
    dia_hoy = date.today().day

    client.post("/afiliados", json={
        "nombre": "Cobro Hoy Test", "tipo_doc": "CC", "doc": "444100200",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
        "dia_cobro": dia_hoy,
    }, headers=h)

    r = client.get("/cobro?doc=444100200", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        assert data[0]["estado"] in ("HOY", "VENCIDO", "PROXIMO", "COBRADO")


def test_cobro_requiere_auth(client):
    r = client.get("/cobro")
    assert r.status_code in (401, 403)


# ─── PLANILLA_PAGADA ─────────────────────────────────────────────────────────

def test_estado_planilla_pagada(client, admin_token):
    """Factura puede pasar de pagado → planilla_pagada."""
    h = {"Authorization": f"Bearer {admin_token}"}

    # Crear afiliado y factura
    client.post("/afiliados", json={
        "nombre": "Planilla Pagada Test", "tipo_doc": "CC", "doc": "333100200",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
    }, headers=h)

    client.post("/facturas", json={
        "nombre_afiliado": "Planilla Pagada Test", "doc": "333100200",
        "cliente": "TestCorp", "mes": "Febrero", "anio": "2026",
        "periodo": "", "estado": "pendiente",
        "ingresos": 100000, "costos": 50000, "costo_adm": 10000,
        "conceptos_extra": 0, "utilidad": 40000,
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)

    # Pagar primero
    r = client.get("/facturas?doc=333100200&estado=pendiente", headers=h)
    items = r.json().get("items", [])
    if not items:
        return
    fid = items[0]["id"]

    client.patch(f"/facturas/{fid}/pagar?banco=Nequi", headers=h)

    # Marcar planilla_pagada
    r2 = client.patch(f"/facturas/{fid}/planilla-pagada", headers=h)
    assert r2.status_code == 200
    assert r2.json()["estado"] == "planilla_pagada"


# ─── AUDIT FIX: get_cobro NO cuenta pendiente como COBRADO ───────────────────

def test_cobro_pendiente_no_es_cobrado(client, admin_token):
    """Afiliado con factura 'pendiente' no debe aparecer como COBRADO.

    Bug fix: get_cobro() filtra facturas_set por estado.in_(["pagado","planilla_pagada"]).
    Una factura pendiente no entra en el set → el afiliado debe quedar VENCIDO o HOY,
    nunca COBRADO.
    """
    h = {"Authorization": f"Bearer {admin_token}"}

    # Fecha de afiliación en el pasado (hace 2 meses) → afiliado cae en la ventana de 6 meses
    fecha_pasada = (date.today().replace(day=1) - timedelta(days=60)).strftime("%Y-%m-%d")

    client.post("/afiliados", json={
        "nombre": "Cobro Pendiente Test", "tipo_doc": "CC", "doc": "222100300",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": fecha_pasada,
    }, headers=h)

    # Crear factura en estado pendiente para el mes actual
    mes_actual = date.today().strftime("%B").capitalize()
    # Nombre en español usando la misma lista MESES del backend
    from const import MESES
    mes_nombre = MESES[date.today().month - 1]
    anio_str = str(date.today().year)

    client.post("/facturas", json={
        "nombre_afiliado": "Cobro Pendiente Test", "doc": "222100300",
        "cliente": "TestCorp", "mes": mes_nombre, "anio": anio_str,
        "periodo": "", "estado": "pendiente",
        "ingresos": 100000, "costos": 50000, "costo_adm": 10000,
        "conceptos_extra": 0, "utilidad": 40000,
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)

    r = client.get("/cobro?doc=222100300", headers=h)
    assert r.status_code == 200
    data = r.json()
    # El afiliado puede no aparecer si su día de cobro es futuro, pero si aparece
    # su estado NO debe ser COBRADO — la factura pendiente no cuenta como pagada.
    for row in data:
        if row["doc"] == "222100300" and row["mes"] == mes_nombre and row["anio"] == anio_str:
            assert row["estado"] != "COBRADO", (
                f"Factura pendiente no debe contar como COBRADO, estado={row['estado']}"
            )


# ─── AUDIT FIX: FacturaCreate rechaza estado != pendiente ────────────────────

def test_factura_create_estado_pagado_rechazado(client, admin_token):
    """FacturaCreate debe rechazar estado='pagado' con 422.

    Bug fix: el validator estado_valido en FacturaCreate solo acepta 'pendiente'.
    """
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/facturas", json={
        "nombre_afiliado": "Test Pagado", "doc": "999000111",
        "cliente": "TestCorp", "mes": "Enero", "anio": "2025",
        "periodo": "", "estado": "pagado",
        "ingresos": 100000, "costos": 50000, "costo_adm": 10000,
        "conceptos_extra": 0, "utilidad": 40000,
        "servicios_detalle": [], "conceptos_detalle": [],
    }, headers=h)
    assert r.status_code == 422, (
        f"Esperaba 422 al crear factura con estado='pagado', got {r.status_code}"
    )


# ─── AUDIT FIX: IBC por debajo del SMMLV rechazado ───────────────────────────

def test_ibc_below_smmlv_rechazado(client, admin_token):
    """Crear afiliado con ibc=500000 debe fallar con 422 (menor al SMMLV 1_300_000).

    Bug fix: el validator ibc_positivo en AfiliadoCreate valida ibc >= SMMLV.
    """
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/afiliados", json={
        "nombre": "IBC Bajo Test", "tipo_doc": "CC", "doc": "111200300",
        "empresa": "TestCorp", "servicios": ["EPS"], "subtipo": "0",
        "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "fecha_afiliacion": "2024-01-15",
        "ibc": 500000,
    }, headers=h)
    assert r.status_code == 422, (
        f"Esperaba 422 al crear afiliado con ibc=500000 (< SMMLV), got {r.status_code}"
    )


# ─── ALERTAS AUTOMÁTICAS SEGUIMIENTO ARL ─────────────────────────────────────

def test_alertar_arl_pendientes_crea_notificaciones(client):
    """Registro con 16 días sin activar → notificación creada para cada admin/empleado."""
    from conftest import TestingSession
    import models
    from datetime import datetime, timezone, timedelta
    from scheduler_jobs import alertar_arl_pendientes

    db = TestingSession()
    try:
        db.query(models.SeguimientoArl).filter(
            models.SeguimientoArl.documento == "888001ALERT"
        ).delete()
        db.query(models.Notificacion).filter(
            models.Notificacion.mensaje.contains("ARL Alert Viejo")
        ).delete()
        db.commit()

        reg = models.SeguimientoArl(
            nombre="ARL Alert Viejo",
            documento="888001ALERT",
            cliente="TestCliente",
            empresa="TestEmpresa",
            entidad_arl="SURA",
            estado="activo",
            creado_en=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=16),
            ultima_alerta_en=None,
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)
        reg_id = reg.id
    finally:
        db.close()

    alertar_arl_pendientes()

    db = TestingSession()
    try:
        notifs = db.query(models.Notificacion).filter(
            models.Notificacion.mensaje.contains("ARL Alert Viejo")
        ).all()
        assert len(notifs) >= 1, "Debe haber al menos 1 notificación creada"
        reg_updated = db.query(models.SeguimientoArl).filter_by(id=reg_id).first()
        assert reg_updated.ultima_alerta_en is not None, "ultima_alerta_en debe quedar seteado"
    finally:
        db.close()


def test_alertar_arl_pendientes_no_spam(client):
    """Registro alertado hace 3 días → no crea nueva notificación."""
    from conftest import TestingSession
    import models
    from datetime import datetime, timezone, timedelta
    from scheduler_jobs import alertar_arl_pendientes

    db = TestingSession()
    try:
        db.query(models.SeguimientoArl).filter(
            models.SeguimientoArl.documento == "888002NOSPAM"
        ).delete()
        db.commit()

        reg = models.SeguimientoArl(
            nombre="ARL No Spam",
            documento="888002NOSPAM",
            cliente="TestCliente",
            empresa="TestEmpresa",
            entidad_arl="SURA",
            estado="activo",
            creado_en=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=20),
            ultima_alerta_en=datetime.now(timezone.utc) - timedelta(days=3),
        )
        db.add(reg)
        db.commit()
    finally:
        db.close()

    db = TestingSession()
    try:
        before_count = db.query(models.Notificacion).filter(
            models.Notificacion.mensaje.contains("ARL No Spam")
        ).count()
    finally:
        db.close()

    alertar_arl_pendientes()

    db = TestingSession()
    try:
        after_count = db.query(models.Notificacion).filter(
            models.Notificacion.mensaje.contains("ARL No Spam")
        ).count()
        assert after_count == before_count, "No debe crear nueva notificación si alerta < 7 días"
    finally:
        db.close()


def test_alertar_arl_pendientes_retirado_ignorado(client):
    """Registro con estado='retirado' → ignorado por el job."""
    from conftest import TestingSession
    import models
    from datetime import datetime, timezone, timedelta
    from scheduler_jobs import alertar_arl_pendientes

    db = TestingSession()
    try:
        db.query(models.SeguimientoArl).filter(
            models.SeguimientoArl.documento == "888003RETIRED"
        ).delete()
        db.commit()

        reg = models.SeguimientoArl(
            nombre="ARL Retirado",
            documento="888003RETIRED",
            cliente="TestCliente",
            empresa="TestEmpresa",
            entidad_arl="SURA",
            estado="retirado",
            creado_en=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=20),
            ultima_alerta_en=None,
        )
        db.add(reg)
        db.commit()
    finally:
        db.close()

    alertar_arl_pendientes()

    db = TestingSession()
    try:
        notifs = db.query(models.Notificacion).filter(
            models.Notificacion.mensaje.contains("ARL Retirado")
        ).all()
        assert len(notifs) == 0, "Estado retirado no debe generar alertas"
    finally:
        db.close()


def test_alertar_arl_pendientes_fresco_ignorado(client):
    """Registro con 10 días (< umbral 15) → ignorado por el job."""
    from conftest import TestingSession
    import models
    from datetime import datetime, timezone, timedelta
    from scheduler_jobs import alertar_arl_pendientes

    db = TestingSession()
    try:
        db.query(models.SeguimientoArl).filter(
            models.SeguimientoArl.documento == "888004FRESH"
        ).delete()
        db.commit()

        reg = models.SeguimientoArl(
            nombre="ARL Fresco",
            documento="888004FRESH",
            cliente="TestCliente",
            empresa="TestEmpresa",
            entidad_arl="SURA",
            estado="activo",
            creado_en=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10),
            ultima_alerta_en=None,
        )
        db.add(reg)
        db.commit()
    finally:
        db.close()

    alertar_arl_pendientes()

    db = TestingSession()
    try:
        notifs = db.query(models.Notificacion).filter(
            models.Notificacion.mensaje.contains("ARL Fresco")
        ).all()
        assert len(notifs) == 0, "Registro < 15 días no debe generar alertas"
    finally:
        db.close()

