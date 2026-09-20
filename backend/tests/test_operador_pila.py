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


def _con_cifrado(manejador):
    """Envuelve un manejador para que resuelva solo la llamada de cifrado."""
    def envuelto(request):
        if "cifrar-datos" in str(request.url):
            return httpx.Response(200, json={"datoCifrado": "CIFRADO=="})
        return manejador(request)
    return envuelto


def _con_aportante(manejador, aportante_id=4005036):
    """Igual, pero resolviendo también la consulta del aportante."""
    def envuelto(request):
        if "/aportante/" in str(request.url):
            return httpx.Response(200, json={"id": aportante_id, "razonSocial": "X"})
        return manejador(request)
    return envuelto


def test_login_guarda_los_cinco_headers_de_sesion(modo_real):
    def responder(request):
        assert request.headers["clave-secreta"] == "clave-de-prueba"
        assert json.loads(request.content)["usuario"] == "CC8487324"
        return httpx.Response(200, headers={
            "token": "T1", "faces": "F1", "refresh-token": "R1",
            "refresh-token-date": "D1", "refresh-token-ttl": "3600"})

    with _cliente_falso(_con_cifrado(responder)) as c:
        sesion = operador.autenticar(c)
    assert sesion.sesion == {"token": "T1", "faces": "F1", "refresh-token": "R1",
                             "refresh-token-date": "D1", "refresh-token-ttl": "3600"}
    assert sesion.simulada is False


def test_los_headers_se_leen_sin_importar_mayusculas(modo_real):
    def responder(request):
        return httpx.Response(200, headers={"Token": "T1", "Refresh-Token": "R1",
                                            "faces": "F1"})
    with _cliente_falso(_con_cifrado(responder)) as c:
        sesion = operador.autenticar(c)
    assert sesion.sesion["token"] == "T1"
    assert sesion.sesion["refresh-token"] == "R1"


def test_login_sin_token_es_error(modo_real):
    def responder(request):
        return httpx.Response(200, headers={"faces": "F1"})
    with _cliente_falso(_con_cifrado(responder)) as c:
        with pytest.raises(operador.ErrorOperador, match="token"):
            operador.autenticar(c)


def test_credenciales_rechazadas(modo_real):
    def responder(request):
        return httpx.Response(401, text="usuario o clave incorrectos")
    with _cliente_falso(_con_cifrado(responder)) as c:
        with pytest.raises(operador.ErrorOperador, match="401"):
            operador.autenticar(c)


def test_autorizacion_negada_sobre_el_aportante(modo_real):
    def responder(request):
        return httpx.Response(401)
    sesion = operador.Sesion(sesion={"token": "T1"})
    with _cliente_falso(_con_aportante(responder)) as c:
        with pytest.raises(operador.ErrorOperador, match="no está autorizado"):
            operador.autorizar(sesion, "NI", "900123456", c)


def test_autorizacion_agrega_sus_cuatro_headers(modo_real):
    def responder(request):
        assert request.headers["token"] == "T1"
        return httpx.Response(200, headers={"profiles": "P", "contributor": "C",
                                            "appId": "A", "refrescar": "false"})
    sesion = operador.Sesion(sesion={"token": "T1"})
    with _cliente_falso(_con_aportante(responder)) as c:
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

# ─── Lo que enseñó el primer contacto con el operador real ────────────────────

def test_la_contrasena_va_cifrada(modo_real):
    """El login rechaza el texto plano con "El dato no tiene formato de cifrado
    válido", aunque la documentación diga que admite ambas formas."""
    llamadas = []

    def responder(request):
        llamadas.append(str(request.url))
        if "cifrar-datos" in str(request.url):
            assert json.loads(request.content)["datoACifrar"] == "0000"
            return httpx.Response(200, json={"datoCifrado": "CIFRADO=="})
        assert json.loads(request.content)["contrasena"] == "CIFRADO=="
        return httpx.Response(200, headers={"token": "T1"})

    with _cliente_falso(responder) as c:
        operador.autenticar(c)
    assert any("cifrar-datos" in u for u in llamadas), "se cifra antes de autenticar"


def test_se_puede_desactivar_el_cifrado(modo_real, monkeypatch):
    monkeypatch.setenv("SUAPORTE_CIFRAR", "0")

    def responder(request):
        assert "cifrar-datos" not in str(request.url)
        assert json.loads(request.content)["contrasena"] == "0000"
        return httpx.Response(200, headers={"token": "T1"})

    with _cliente_falso(responder) as c:
        operador.autenticar(c)


def test_la_autorizacion_usa_el_id_interno_no_el_documento(modo_real):
    """El servicio recibe un entero. Mandarle el documento devuelve
    "El aportante no existe"."""
    def responder(request):
        if "/aportante/NI/901760008" in str(request.url):
            return httpx.Response(200, json={"id": 4005036, "razonSocial": "CARSECOOP"})
        assert dict(request.url.params)["id"] == "4005036"
        return httpx.Response(200, headers={"profiles": "P", "contributor": "C",
                                            "appId": "A", "refrescar": "true"})

    sesion = operador.Sesion(sesion={"token": "T1"})
    with _cliente_falso(responder) as c:
        operador.autorizar(sesion, "NI", "901760008", c)
    assert sesion.autorizada


def test_sin_permisos_sobre_el_aportante_se_sabe_en_la_consulta(modo_real):
    def responder(request):
        return httpx.Response(400, json={"message": "No cuenta con permisos para "
                                                    "este aportante"})
    sesion = operador.Sesion(sesion={"token": "T1"})
    with _cliente_falso(responder) as c:
        with pytest.raises(operador.ErrorOperador, match="No cuenta con permisos"):
            operador.consultar_aportante(sesion, "CC", "8487324", c)


def test_la_cadena_tls_incluye_el_intermedio_que_el_operador_omite():
    """El servidor envía solo su hoja; sin el intermedio falla la verificación."""
    ctx = operador.contexto_tls()
    emisores = [c["issuer"] for c in ctx.get_ca_certs()]
    assert any("DigiCert Global Root G2" in str(e) for e in emisores)

# ─── Interpretar lo que responde el operador ──────────────────────────────────
#
# Respuesta real del primer envío: el operador recibe la planilla, le asigna un
# código y la deja sin numerar mientras tenga errores. Todo viene anidado en
# `validacionPlanillas`, no en la raíz.

RESPUESTA_REAL = {
    "estadoValidacion": "OK",
    "validacionPlanillas": [{
        "codigoPlanilla": 287149577,
        "numeroPlanilla": 0,
        "cantidadErroresCotizante": 1,
        "cantidadErroresEmpresa": 1,
        "cantidadAdvertencias": 2,
        "erroresCotizantePlanilla": [{
            "idRegla": "eo.val.2.262",
            "descripcion": "El cotizante aportará a la administradora de pension 230301 "
                           "PORVENIR, pero se encuentra afiliado a la administradora "
                           "230201 PROTECCION",
            "identificacion": "CC1017234567", "autocorreccion": "Si",
            "campoInicial": "154", "campoFinal": "159", "linea": "2"}],
        "erroresEmpresaPlanilla": [{
            "idRegla": "eo.val.1.018",
            "descripcion": "El usuario no se encuentra asociado a la sucursal 01",
            "identificacion": "", "autocorreccion": "No",
            "campoInicial": "249", "campoFinal": "258", "linea": "1"}],
        "advertenciasPlanilla": [{
            "idRegla": "eo.val.2.380",
            "descripcion": "el aporte a salud se realizará a la MIN002 ADRES",
            "identificacion": "CC1017234567", "autocorreccion": "No",
            "campoInicial": "8", "campoFinal": "13", "linea": "2"}],
    }],
}


def test_saca_el_codigo_de_planilla_aunque_venga_anidado():
    r = operador.interpretar_validacion(RESPUESTA_REAL)
    assert r["codigo_planilla"] == "287149577"
    assert r["estado_validacion"] == "OK"


def test_numero_en_cero_significa_sin_numerar():
    """Con errores pendientes el operador asigna código pero no número."""
    r = operador.interpretar_validacion(RESPUESTA_REAL)
    assert r["numero_planilla"] == ""


def test_junta_los_errores_de_empresa_y_de_cotizante():
    r = operador.interpretar_validacion(RESPUESTA_REAL)
    assert len(r["errores"]) == 2
    assert {e["tipo"] for e in r["errores"]} == {"empresa", "cotizante"}
    assert len(r["advertencias"]) == 1


def test_cada_error_dice_donde_y_si_se_autocorrige():
    r = operador.interpretar_validacion(RESPUESTA_REAL)
    afp = next(e for e in r["errores"] if e["regla"] == "eo.val.2.262")
    assert afp["campos"] == "154-159", "el campo 31 del registro tipo 2, la AFP"
    assert afp["linea"] == "2"
    assert afp["autocorrige"] is True

    sucursal = next(e for e in r["errores"] if e["regla"] == "eo.val.1.018")
    assert sucursal["autocorrige"] is False


def test_respuesta_sin_validaciones_no_revienta():
    assert operador.interpretar_validacion({"estadoValidacion": "OK"})["estado_validacion"] == "OK"
    assert operador.interpretar_validacion({})["estado_validacion"] == ""
    assert operador.interpretar_validacion(None) == {}
