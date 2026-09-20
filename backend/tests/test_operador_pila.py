"""Tests del cliente del operador PILA — modo simulación, sesión y envío.

Ninguno sale a la red. El modo real se prueba con un transporte falso de httpx,
no contra el operador: mandarle una planilla crea un registro de verdad.
"""
import json

import httpx
import pytest

from services.pila import operador


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def con_credenciales(monkeypatch):
    monkeypatch.setenv("SUAPORTE_USUARIO", "CC8487324")
    monkeypatch.setenv("SUAPORTE_CONTRASENA", "0000")
    monkeypatch.setenv("SUAPORTE_CLAVE_SECRETA", "clave-de-prueba")


@pytest.fixture
def modo_real(monkeypatch, con_credenciales):
    monkeypatch.setenv("SUAPORTE_MODO", "real")


# ─── Modo simulación ──────────────────────────────────────────────────────────

def test_por_defecto_no_sale_a_la_red(monkeypatch, con_credenciales):
    """Enviar crea un registro real en el operador: el default no envía."""
    monkeypatch.delenv("SUAPORTE_MODO", raising=False)
    assert operador.modo_real() is False

    def explota(*a, **k):
        raise AssertionError("no debería abrirse ninguna conexión en simulación")

    monkeypatch.setattr(httpx.Client, "post", explota)
    monkeypatch.setattr(httpx.Client, "get", explota)

    sesion = operador.autenticar()
    assert sesion.simulada
    operador.autorizar(sesion, "NI", "900123456")
    r = operador.validar_planilla(sesion, "0110001...", "PILA.txt")
    assert r["simulado"] is True
    assert "no se envió" in r["mensaje"].lower()


def test_la_simulacion_registra_los_parametros(monkeypatch, con_credenciales):
    monkeypatch.delenv("SUAPORTE_MODO", raising=False)
    sesion = operador.autenticar()
    r = operador.validar_planilla(sesion, "x" * 693, "PILA_1.txt", tipo_archivo="I")
    assert r["parametros"] == {"planillaUGPP": False,
                               "planillaNSoloNovedades": False,
                               "tipoArchivo": "I"}
    assert r["bytes"] == 693


def test_modo_real_solo_con_la_variable_exacta(monkeypatch):
    for valor, esperado in (("real", True), ("REAL", True), ("simulacion", False),
                            ("", False), ("si", False)):
        monkeypatch.setenv("SUAPORTE_MODO", valor)
        assert operador.modo_real() is esperado


# ─── Credenciales ─────────────────────────────────────────────────────────────

def test_sin_credenciales_falla_con_mensaje_accionable(monkeypatch):
    """Solo en modo real: la simulación debe correr en una máquina sin secretos."""
    for v in ("SUAPORTE_USUARIO", "SUAPORTE_CONTRASENA", "SUAPORTE_CLAVE_SECRETA"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SUAPORTE_MODO", "real")
    assert operador.hay_credenciales() is False
    with pytest.raises(operador.ErrorOperador, match="SUAPORTE_USUARIO"):
        operador.autenticar()


def test_la_simulacion_corre_sin_credenciales(monkeypatch):
    for v in ("SUAPORTE_USUARIO", "SUAPORTE_CONTRASENA", "SUAPORTE_CLAVE_SECRETA"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.delenv("SUAPORTE_MODO", raising=False)
    assert operador.autenticar().simulada is True


def test_la_contrasena_no_se_escribe_en_el_log(monkeypatch, con_credenciales, caplog):
    monkeypatch.delenv("SUAPORTE_MODO", raising=False)
    with caplog.at_level("INFO"):
        operador.autenticar()
    registrado = " ".join(r.message for r in caplog.records)
    assert "0000" not in registrado
    assert "clave-de-prueba" not in registrado


# ─── Sesión contra un operador simulado ───────────────────────────────────────

def _cliente_falso(manejador):
    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_login_guarda_los_cinco_headers_de_sesion(modo_real):
    def responder(request):
        assert request.headers["clave-secreta"] == "clave-de-prueba"
        assert json.loads(request.content)["usuario"] == "CC8487324"
        return httpx.Response(200, headers={
            "token": "T1", "faces": "F1", "refresh-token": "R1",
            "refresh-token-date": "D1", "refresh-token-ttl": "3600"})

    with _cliente_falso(responder) as c:
        sesion = operador.autenticar(c)
    assert sesion.sesion == {"token": "T1", "faces": "F1", "refresh-token": "R1",
                             "refresh-token-date": "D1", "refresh-token-ttl": "3600"}
    assert sesion.simulada is False


def test_los_headers_se_leen_sin_importar_mayusculas(modo_real):
    def responder(request):
        return httpx.Response(200, headers={"Token": "T1", "Refresh-Token": "R1",
                                            "faces": "F1"})
    with _cliente_falso(responder) as c:
        sesion = operador.autenticar(c)
    assert sesion.sesion["token"] == "T1"
    assert sesion.sesion["refresh-token"] == "R1"


def test_login_sin_token_es_error(modo_real):
    def responder(request):
        return httpx.Response(200, headers={"faces": "F1"})
    with _cliente_falso(responder) as c:
        with pytest.raises(operador.ErrorOperador, match="token"):
            operador.autenticar(c)


def test_credenciales_rechazadas(modo_real):
    def responder(request):
        return httpx.Response(401, text="usuario o clave incorrectos")
    with _cliente_falso(responder) as c:
        with pytest.raises(operador.ErrorOperador, match="401"):
            operador.autenticar(c)


def test_autorizacion_negada_sobre_el_aportante(modo_real):
    def responder(request):
        return httpx.Response(401)
    sesion = operador.Sesion(sesion={"token": "T1"})
    with _cliente_falso(responder) as c:
        with pytest.raises(operador.ErrorOperador, match="no está autorizado"):
            operador.autorizar(sesion, "NI", "900123456", c)


def test_autorizacion_agrega_sus_cuatro_headers(modo_real):
    def responder(request):
        assert request.headers["token"] == "T1"
        return httpx.Response(200, headers={"profiles": "P", "contributor": "C",
                                            "appId": "A", "refrescar": "false"})
    sesion = operador.Sesion(sesion={"token": "T1"})
    with _cliente_falso(responder) as c:
        operador.autorizar(sesion, "NI", "900123456", c)
    assert sesion.autorizada
    assert set(sesion.autorizacion) == {"profiles", "contributor", "appId", "refrescar"}
    assert sesion.headers["token"] == "T1", "la sesión se arrastra a las llamadas siguientes"


def test_no_se_envia_sin_autorizar(modo_real):
    sesion = operador.Sesion(sesion={"token": "T1"})     # sin autorización
    with pytest.raises(operador.ErrorOperador, match="autorizar"):
        operador.validar_planilla(sesion, "linea", "PILA.txt")


def test_el_archivo_viaja_como_multipart(modo_real):
    def responder(request):
        assert "multipart/form-data" in request.headers["content-type"]
        assert b"PILA_1.txt" in request.content
        assert b"0110001" in request.content
        parametros = json.loads(dict(request.url.params)["parametros"])
        assert parametros["tipoArchivo"] == "I"
        return httpx.Response(200, json={"numeroPlanilla": "123456789"})

    sesion = operador.Sesion(sesion={"token": "T1"}, autorizacion={"profiles": "P"})
    with _cliente_falso(responder) as c:
        r = operador.validar_planilla(sesion, "0110001CARSECOOP", "PILA_1.txt", cliente=c)
    assert r["numeroPlanilla"] == "123456789"


def test_planilla_rechazada_conserva_el_mensaje_del_operador(modo_real):
    def responder(request):
        return httpx.Response(422, text="Valor invalido para campo Tarifa de aportes")
    sesion = operador.Sesion(sesion={"token": "T1"}, autorizacion={"profiles": "P"})
    with _cliente_falso(responder) as c:
        with pytest.raises(operador.ErrorOperador, match="Tarifa de aportes"):
            operador.validar_planilla(sesion, "x", "PILA.txt", cliente=c)


def test_url_de_pago(modo_real):
    def responder(request):
        return httpx.Response(200, json={"url": "https://pago.operador/pse/abc"})
    sesion = operador.Sesion(sesion={"token": "T1"}, autorizacion={"profiles": "P"})
    with _cliente_falso(responder) as c:
        assert operador.url_pago(sesion, "123", c) == "https://pago.operador/pse/abc"


# ─── Endpoints ────────────────────────────────────────────────────────────────

def test_estado_del_operador(client, admin_token, monkeypatch):
    monkeypatch.delenv("SUAPORTE_MODO", raising=False)
    r = client.get("/liquidacion/operador/estado", headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["modo"] == "simulacion"


def test_enviar_en_simulacion_no_numera_la_planilla(client, admin_token, db, monkeypatch):
    import itertools
    import models
    from decimal import Decimal

    monkeypatch.delenv("SUAPORTE_MODO", raising=False)
    n = next(itertools.count(9000))
    cliente_ref = f"ENVIO-{n}"
    ap_id = client.post("/aportantes", json={
        "cliente_ref": cliente_ref, "razon_social": "ENVIO SAS",
        "tipo_doc": "NI", "num_doc": "900888777", "tipo_aportante": "01",
        "cod_arl": "14-11", "clase_riesgo": "1",
    }, headers=_h(admin_token)).json()["id"]
    org = db.query(models.AportantePila).filter_by(id=ap_id).first().organizacion_id

    af = models.Afiliado(
        organizacion_id=org, nombre="ENVIO PRUEBA", tipo_doc="CC", doc=f"88{n}",
        cliente_txt=cliente_ref, empresa=cliente_ref, activo=True, estado="ACTIVO",
        primer_apellido="PRUEBA", primer_nombre="ENVIO", tipo_cotizante="01",
        cod_eps="EPS037", cod_afp="230301", clase_riesgo="1",
        salario_basico=Decimal("1750905"), fecha_ingreso="2024-01-15")
    db.add(af); db.commit(); db.refresh(af)

    liq_id = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": af.id, "anio": 2026, "mes": 9}).json()["id"]

    r = client.post(f"/liquidacion/{liq_id}/enviar", headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["simulado"] is True
    assert r.json()["numero_planilla"] is None

    fila = db.query(models.PlanillaLiquidacion).filter_by(id=liq_id).first()
    db.refresh(fila)
    assert fila.estado == "generada", "la simulación no cambia el estado"
    assert fila.respuesta_operador, "pero sí deja rastro de lo que se habría enviado"
