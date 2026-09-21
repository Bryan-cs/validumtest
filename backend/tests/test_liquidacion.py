"""Tests de liquidación PILA — cálculo, archivo plano y endpoints."""
import itertools
import json
from pathlib import Path
from decimal import Decimal

import pytest

import models
from services.pila import parametros as P
from services.pila import liquidacion as motor
from services.pila import plano

SMLMV_2026 = Decimal("1750905")

_contador = itertools.count(1)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


class _Aportante:
    """Aportante mínimo para los tests del motor, sin pasar por la base."""
    def __init__(self, exonerado=False, clase_riesgo="1"):
        self.razon_social = "DEMO SAS"
        self.tipo_doc = "NI"
        self.num_doc = "900123456"
        self.dv = "8"
        self.tipo_aportante = "01"
        self.cod_arl = "14-11"
        self.clase_riesgo = clase_riesgo
        self.cod_depto = "05"
        self.cod_municipio = "001"
        self.cod_sucursal = ""
        self.nombre_sucursal = ""
        self.exonerado_parafiscales = exonerado


class _Afiliado:
    def __init__(self, **kw):
        self.id = kw.get("id")
        self.nombre = kw.get("nombre", "JUAN CARLOS PEREZ GOMEZ")
        self.tipo_doc = "CC"
        self.doc = kw.get("doc", "1017234567")
        self.primer_apellido = kw.get("primer_apellido", "PEREZ")
        self.segundo_apellido = kw.get("segundo_apellido", "GOMEZ")
        self.primer_nombre = kw.get("primer_nombre", "JUAN")
        self.segundo_nombre = kw.get("segundo_nombre", "CARLOS")
        self.tipo_cotizante = kw.get("tipo_cotizante", "01")
        # Lo contratado: es lo que decide qué subsistemas se liquidan.
        clase = kw.get("clase_riesgo", "1")
        self.servicios = json.dumps(kw.get(
            "servicios", ["EPS", "AFP", "CCF"] + ([f"ARL {clase}"] if clase else [])))
        self.arl = kw.get("arl", f"ARL {clase}" if clase else "")
        self.subtipo_cotizante = ""
        self.cod_depto_labor = ""
        self.cod_municipio_labor = ""
        self.cod_eps = kw.get("cod_eps", "EPS037")
        self.cod_afp = kw.get("cod_afp", "230301")
        self.cod_ccf = kw.get("cod_ccf", "CCF03")
        self.cod_arl = "14-11"
        self.clase_riesgo = kw.get("clase_riesgo", "1")
        self.tarifa_arl = kw.get("tarifa_arl")
        self.tipo_salario = "F"
        self.salario_basico = kw.get("salario_basico", SMLMV_2026)
        self.ibc = kw.get("ibc")
        self.centro_trabajo = ""
        self.fecha_ingreso = kw.get("fecha_ingreso", "2024-01-15")


# ─── Parámetros y redondeo ────────────────────────────────────────────────────

def test_smlmv_2026():
    assert P.parametros(2026).smlmv == SMLMV_2026
    assert P.parametros(2026).auxilio_transporte == Decimal("249095")


def test_redondeo_aritmetico_al_peso():
    """El anexo exige aproximar al peso desde .50, no truncar ni ir a la centena."""
    assert P.redondear_peso(Decimal("100.49")) == 100
    assert P.redondear_peso(Decimal("100.50")) == 101
    assert P.redondear_peso(Decimal("100.51")) == 101


def test_anio_sin_parametros_cae_al_mas_reciente():
    assert P.parametros(2099).smlmv == P.PARAMETROS_POR_ANIO[P.ANIO_MAS_RECIENTE].smlmv


# ─── Fondo de Solidaridad Pensional ───────────────────────────────────────────

@pytest.mark.parametrize("smlmvs,tarifa", [
    ("3.9", "0"), ("4", "0.010"), ("15", "0.010"),
    ("16", "0.012"), ("17", "0.014"), ("18", "0.016"),
    ("19", "0.018"), ("20", "0.020"), ("30", "0.020"),
])
def test_tramos_fsp(smlmvs, tarifa):
    ibc = SMLMV_2026 * Decimal(smlmvs)
    assert P.tarifa_fsp(ibc, SMLMV_2026) == Decimal(tarifa)


def test_fsp_se_reparte_entre_subcuentas():
    """El primer 1% es solidaridad; lo que exceda, subsistencia."""
    ibc = SMLMV_2026 * 20
    sol, sub = P.partir_fsp(ibc, SMLMV_2026)
    assert sol == P.aproximar_aporte(ibc * Decimal("0.01"))
    assert sub == P.aproximar_aporte(ibc * Decimal("0.01"))


def test_sin_fsp_bajo_cuatro_salarios():
    assert P.partir_fsp(SMLMV_2026 * 2, SMLMV_2026) == (Decimal("0"), Decimal("0"))


# ─── IBC ──────────────────────────────────────────────────────────────────────

def test_ibc_no_baja_del_minimo():
    d = motor.liquidar_afiliado(_Afiliado(salario_basico=Decimal("500000")),
                                _Aportante(), 2026, 9)
    assert d.ibc_salud == SMLMV_2026


def test_ibc_tiene_techo_de_25_salarios():
    d = motor.liquidar_afiliado(_Afiliado(salario_basico=SMLMV_2026 * 40),
                                _Aportante(), 2026, 9)
    assert d.ibc_salud == SMLMV_2026 * 25


def test_ibc_es_proporcional_a_los_dias():
    af = _Afiliado(salario_basico=SMLMV_2026 * 2, fecha_ingreso="2026-09-11")
    d = motor.liquidar_afiliado(af, _Aportante(), 2026, 9)
    assert d.dias_salud == 20                       # del 11 al 30
    assert d.ibc_salud == P.redondear_peso(SMLMV_2026 * 2 * 20 / 30)


def test_piso_del_ibc_tambien_es_proporcional():
    """Quien cotiza 20 días no puede quedar bajo 20/30 de un salario mínimo,
    pero tampoco se le exige uno completo."""
    af = _Afiliado(salario_basico=Decimal("100000"), fecha_ingreso="2026-09-11")
    d = motor.liquidar_afiliado(af, _Aportante(), 2026, 9)
    assert d.ibc_salud == P.redondear_peso(SMLMV_2026 * 20 / 30)


def test_mes_completo_sin_novedades():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    assert d.dias_salud == 30
    assert d.novedades == {}


# ─── Tarifas por subsistema ───────────────────────────────────────────────────

def test_tarifas_estandar():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    assert d.cot_pension == P.aproximar_aporte(SMLMV_2026 * Decimal("0.16"))
    assert d.cot_salud == P.aproximar_aporte(SMLMV_2026 * Decimal("0.125"))
    assert d.valor_ccf == P.aproximar_aporte(SMLMV_2026 * Decimal("0.04"))


@pytest.mark.parametrize("clase,tarifa", [
    ("1", "0.00522"), ("2", "0.01044"), ("3", "0.02436"),
    ("4", "0.04350"), ("5", "0.06960"),
])
def test_arl_por_clase_de_riesgo(clase, tarifa):
    d = motor.liquidar_afiliado(_Afiliado(clase_riesgo=clase), _Aportante(), 2026, 9)
    assert d.cot_arl == P.aproximar_aporte(SMLMV_2026 * Decimal(tarifa))


def test_exonerado_paga_solo_el_4_por_ciento_de_salud():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(exonerado=True), 2026, 9)
    assert d.exonerado is True
    assert d.tarifa_salud == Decimal("0.04")
    assert d.cot_salud == P.aproximar_aporte(SMLMV_2026 * Decimal("0.04"))


def test_exonerado_no_paga_sena_ni_icbf():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(exonerado=True), 2026, 9)
    assert d.valor_sena == 0
    assert d.valor_icbf == 0
    assert d.valor_ccf > 0, "la caja de compensación no la exonera el 114-1"


def test_exoneracion_no_aplica_sobre_diez_salarios():
    af = _Afiliado(salario_basico=SMLMV_2026 * 12)
    d = motor.liquidar_afiliado(af, _Aportante(exonerado=True), 2026, 9)
    assert d.exonerado is False
    assert d.tarifa_salud == Decimal("0.125")
    assert d.valor_sena > 0 and d.valor_icbf > 0


def test_aportante_no_exonerado_paga_todo():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(exonerado=False), 2026, 9)
    assert d.tarifa_salud == Decimal("0.125")
    assert d.valor_sena == P.aproximar_aporte(SMLMV_2026 * Decimal("0.02"))
    assert d.valor_icbf == P.aproximar_aporte(SMLMV_2026 * Decimal("0.03"))


# ─── Resumen ──────────────────────────────────────────────────────────────────

def test_totales_suman_los_detalles():
    afs = [_Afiliado(doc="1"), _Afiliado(doc="2"), _Afiliado(doc="3")]
    r = motor.liquidar(afs, _Aportante(), 2026, 9)
    assert r.total_cotizantes == 3
    assert r.total_salud == sum(d.cot_salud for d in r.detalles)
    assert r.total_general == sum(d.total for d in r.detalles)


def test_largos_de_los_registros():
    assert plano.LARGO_TIPO_1 == 359
    assert plano.LARGO_TIPO_2 == 693


def test_la_cadena_de_campos_no_deja_huecos():
    """Si cada campo no empieza donde acaba el anterior, el archivo se corre
    entero y el operador lo rechaza."""
    for campos in (plano.CAMPOS_TIPO_1, plano.CAMPOS_TIPO_2):
        pos = 1
        for c in campos:
            assert c.inicio == pos, f"campo {c.numero} ({c.nombre}) descuadrado"
            pos = c.inicio + c.longitud


def test_numericos_a_la_derecha_y_texto_a_la_izquierda():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert len(linea) == 693
    assert linea[0:2] == "02"                    # tipo de registro
    assert linea[2:7] == "00001"                 # secuencia rellena con ceros
    assert linea[9:25] == "1017234567      "     # documento a la izquierda
    assert linea[36:56] == "PEREZ".ljust(20)     # primer apellido


def test_posiciones_de_los_campos_calculados():
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert linea[153:159] == "230301"            # campo 31, admin. de pensiones
    assert linea[165:171] == "EPS037"            # campo 33, EPS
    assert linea[183:185] == "30"                # campo 36, días de pensión
    assert linea[237:244] == "0.16000"           # campo 46, tarifa de pensión
    assert int(linea[244:253]) == int(d.cot_pension)   # campo 47


def test_el_nombre_de_la_ficha_pisa_el_codigo_viejo_de_eps():
    """ADRES deja 'Famisanar' en la ficha y el código puede seguir en Nueva EPS."""
    af = _Afiliado()
    af.eps = "Famisanar"
    af.cod_eps = "EPS037"
    d = motor.liquidar_afiliado(af, _Aportante(), 2026, 9)
    assert d.cod_eps == "EPS017"
    """Formato verificado contra un plano real aceptado por el operador.

    Tres codificaciones sin punto —4, 5 y 6 decimales— fueron rechazadas con
    "Valor invalido para campo" antes de tener el archivo de referencia.
    """
    assert plano.formatear_tarifa("0.16", 7) == "0.16000"        # pensión 16%
    assert plano.formatear_tarifa("0.04", 7) == "0.04000"        # salud exonerada y CCF
    assert plano.formatear_tarifa("0.125", 7) == "0.12500"       # salud 12,5%
    assert plano.formatear_tarifa("0.0435", 9) == "0.0435000"    # ARL clase 4
    assert plano.formatear_tarifa("0.00522", 9) == "0.0052200"   # ARL clase 1


def test_tarifa_en_cero_no_va_en_ceros():
    """Un cero también se escribe como decimal: el campo es de tarifa."""
    assert plano.formatear_tarifa(0, 7) == "0.00000"
    assert plano.formatear_tarifa(0, 9) == "0.0000000"


def test_las_tarifas_llenan_su_campo_completo():
    for tarifa, largo in (("0.16", 7), ("0.125", 7), ("0.00522", 9), (0, 7)):
        assert len(plano.formatear_tarifa(tarifa, largo)) == largo


def test_tarifa_que_no_cabe_es_un_error():
    with pytest.raises(ValueError, match="no cabe"):
        plano.formatear_tarifa("15.5", 7)


def test_valor_que_no_cabe_es_un_error_explicito():
    with pytest.raises(ValueError, match="no cabe"):
        plano.registro_tipo_2({"secuencia": 123456789})


def test_marca_de_exonerado_va_en_S():
    """El anexo reporta el campo 76 en "S"; con "X" el operador lo rechaza."""
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(exonerado=True), 2026, 9)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert linea[505] == "S"                     # campo 76

    sin_exonerar = motor.liquidar_afiliado(_Afiliado(), _Aportante(exonerado=False), 2026, 9)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(sin_exonerar, 1))
    assert linea[505] == " "


def test_tarifas_en_su_posicion_dentro_del_registro():
    """Las posiciones que reportó el validador del operador: 238, 308, 381, 408."""
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert linea[237:244] == "0.16000"           # campo 46, pensión
    assert linea[307:314] == "0.12500"           # campo 54, salud
    assert linea[380:389] == "0.0052200"         # campo 61, riesgos
    assert linea[407:414] == "0.04000"           # campo 64, caja


# ─── Endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def afiliado_listo(client, db, admin_token):
    """Un afiliado con su empresa cargada como aportante, listo para liquidar."""
    n = next(_contador)
    cliente = f"LIQ-{n}"
    r = client.post("/aportantes", json={
        "cliente_ref": cliente, "razon_social": f"LIQUIDA {n} SAS",
        "tipo_doc": "NI", "num_doc": f"9005550{n:02d}", "tipo_aportante": "01",
        "cod_arl": "14-11", "clase_riesgo": "1", "cod_depto": "05",
        "cod_municipio": "001",
    }, headers=_h(admin_token))
    assert r.status_code == 201
    org = db.query(models.AportantePila).filter_by(id=r.json()["id"]).first().organizacion_id

    af = models.Afiliado(
        organizacion_id=org, nombre=f"JUAN PEREZ {n}", tipo_doc="CC",
        doc=f"10{n:04d}", cliente_txt=cliente, empresa=cliente,
        activo=True, estado="ACTIVO",
        primer_apellido="PEREZ", primer_nombre="JUAN",
        tipo_cotizante="01", cod_eps="EPS037", cod_afp="230301",
        cod_ccf="CCF03", clase_riesgo="1", salario_basico=SMLMV_2026,
        fecha_ingreso="2024-01-15",
        # Lo contratado decide qué se liquida.
        servicios=json.dumps(["EPS", "AFP"]), arl="",
    )
    db.add(af)
    db.commit()
    db.refresh(af)
    return {"afiliado_id": af.id, "doc": af.doc, "cliente": cliente}


def test_previsualizar_no_guarda_nada(client, admin_token, afiliado_listo, db):
    antes = db.query(models.PlanillaLiquidacion).count()
    r = client.post("/liquidacion/previsualizar", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"], "anio": 2026, "mes": 9})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["afiliado"]["doc"] == afiliado_listo["doc"]
    assert cuerpo["totales"]["general"] > 0
    assert db.query(models.PlanillaLiquidacion).count() == antes


def test_la_planilla_es_de_una_sola_persona(client, admin_token, afiliado_listo, db):
    """Aunque la empresa tenga más afiliados, la planilla lleva un cotizante."""
    af = db.query(models.Afiliado).filter_by(id=afiliado_listo["afiliado_id"]).first()
    db.add(models.Afiliado(
        organizacion_id=af.organizacion_id, nombre="OTRA PERSONA", tipo_doc="CC",
        doc=af.doc + "9", cliente_txt=af.cliente_txt, empresa=af.empresa,
        activo=True, estado="ACTIVO", primer_apellido="OTRA", primer_nombre="PERSONA",
        tipo_cotizante="01", cod_eps="EPS037", cod_afp="230301",
        # Lo contratado decide qué se liquida.
        servicios=json.dumps(["EPS", "AFP"]), arl="",
        clase_riesgo="1", salario_basico=SMLMV_2026, fecha_ingreso="2024-01-15"))
    db.commit()

    r = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"], "anio": 2026, "mes": 9})
    assert r.status_code == 201
    liq_id = r.json()["id"]

    detalles = db.query(models.PlanillaDetalle).filter_by(liquidacion_id=liq_id).all()
    assert len(detalles) == 1
    assert detalles[0].doc == afiliado_listo["doc"]

    liq = db.query(models.PlanillaLiquidacion).filter_by(id=liq_id).first()
    assert liq.afiliado_doc == afiliado_listo["doc"]
    assert liq.total_cotizantes == 1
    assert len(detalles[0].linea_plana) == 693


def test_no_se_liquida_dos_veces_a_la_misma_persona(client, admin_token, afiliado_listo):
    cuerpo = {"afiliado_id": afiliado_listo["afiliado_id"], "anio": 2026, "mes": 9}
    assert client.post("/liquidacion", json=cuerpo, headers=_h(admin_token)).status_code == 201
    r = client.post("/liquidacion", json=cuerpo, headers=_h(admin_token))
    assert r.status_code == 409
    assert "ya tiene una planilla" in r.json()["detail"]


def test_el_mismo_periodo_en_otra_persona_si_se_puede(client, admin_token, afiliado_listo, db):
    af = db.query(models.Afiliado).filter_by(id=afiliado_listo["afiliado_id"]).first()
    otro = models.Afiliado(
        organizacion_id=af.organizacion_id, nombre="SEGUNDA PERSONA", tipo_doc="CC",
        doc=af.doc + "7", cliente_txt=af.cliente_txt, empresa=af.empresa,
        activo=True, estado="ACTIVO", primer_apellido="SEGUNDA", primer_nombre="PERSONA",
        tipo_cotizante="01", cod_eps="EPS037", cod_afp="230301",
        # Lo contratado decide qué se liquida.
        servicios=json.dumps(["EPS", "AFP"]), arl="",
        clase_riesgo="1", salario_basico=SMLMV_2026, fecha_ingreso="2024-01-15")
    db.add(otro)
    db.commit()
    db.refresh(otro)

    for afiliado_id in (afiliado_listo["afiliado_id"], otro.id):
        r = client.post("/liquidacion", headers=_h(admin_token),
                        json={"afiliado_id": afiliado_id, "anio": 2026, "mes": 9})
        assert r.status_code == 201


def test_anular_permite_volver_a_liquidar(client, admin_token, afiliado_listo):
    cuerpo = {"afiliado_id": afiliado_listo["afiliado_id"], "anio": 2026, "mes": 9}
    liq_id = client.post("/liquidacion", json=cuerpo, headers=_h(admin_token)).json()["id"]
    assert client.post(f"/liquidacion/{liq_id}/anular",
                       headers=_h(admin_token)).status_code == 200
    assert client.post("/liquidacion", json=cuerpo, headers=_h(admin_token)).status_code == 201


def test_descargar_plano_de_una_persona(client, admin_token, afiliado_listo):
    liq_id = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"],
        "anio": 2026, "mes": 9}).json()["id"]

    r = client.get(f"/liquidacion/{liq_id}/plano", headers=_h(admin_token))
    assert r.status_code == 200
    assert afiliado_listo["doc"] in r.headers["content-disposition"]

    lineas = r.text.rstrip("\r\n").split("\r\n")
    assert len(lineas) == 2, "encabezado y un solo cotizante"
    assert len(lineas[0]) == 359 and lineas[0].startswith("01")
    assert len(lineas[1]) == 693 and lineas[1].startswith("02")
    assert lineas[1][9:25].strip() == afiliado_listo["doc"]


def test_descargar_plano_nomina_es_la_suma_de_ibc_ccf(client, admin_token, afiliado_listo):
    """Error 183: el encabezado debe coincidir con el IBC de parafiscales."""
    liq_id = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"],
        "anio": 2026, "mes": 9}).json()["id"]
    r = client.get(f"/liquidacion/{liq_id}/plano", headers=_h(admin_token))
    lineas = r.text.rstrip("\r\n").split("\r\n")
    c_nom = next(x for x in plano.CAMPOS_TIPO_1 if x.nombre == "valor_total_nomina")
    c_ccf = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "ibc_ccf")
    nomina = int(lineas[0][c_nom.inicio - 1:c_nom.inicio - 1 + c_nom.longitud])
    ibc_ccf = int(lineas[1][c_ccf.inicio - 1:c_ccf.inicio - 1 + c_ccf.longitud])
    assert ibc_ccf == 100
    assert nomina == ibc_ccf


def test_afiliado_sin_aportante_no_se_liquida(client, admin_token, db):
    """Sin la empresa cargada no hay NIT para el encabezado."""
    n = next(_contador)
    org = db.query(models.Organizacion).first().id
    af = models.Afiliado(
        organizacion_id=org, nombre="SIN EMPRESA", tipo_doc="CC", doc=f"77{n:04d}",
        cliente_txt=f"CLIENTE-INEXISTENTE-{n}", activo=True, estado="ACTIVO",
        primer_apellido="SIN", primer_nombre="EMPRESA", tipo_cotizante="01",
        cod_eps="EPS037", salario_basico=SMLMV_2026,
        servicios=json.dumps(["EPS"]), arl="")
    db.add(af)
    db.commit()
    db.refresh(af)

    r = client.post("/liquidacion/previsualizar", headers=_h(admin_token),
                    json={"afiliado_id": af.id, "anio": 2026, "mes": 9})
    assert r.status_code == 400
    assert "no tiene aportante cargado" in r.json()["detail"]


def test_afiliado_retirado_no_se_liquida(client, admin_token, afiliado_listo, db):
    af = db.query(models.Afiliado).filter_by(id=afiliado_listo["afiliado_id"]).first()
    af.activo = False
    db.commit()
    r = client.post("/liquidacion/previsualizar", headers=_h(admin_token),
                    json={"afiliado_id": af.id, "anio": 2026, "mes": 9})
    assert r.status_code == 400
    assert "retirado" in r.json()["detail"]


def test_pendientes_marca_quien_ya_tiene_planilla(client, admin_token, afiliado_listo):
    # La lista sale de las facturas del periodo: sin factura no hay fila que
    # marcar, porque primero se factura y despues se liquida.
    client.post("/facturas", headers=_h(admin_token), json={
        "doc": afiliado_listo["doc"], "anio": "2026", "mes": "Septiembre",
        "codigo": f"F{afiliado_listo['doc']}",
    })

    r = client.get("/liquidacion/pendientes?anio=2026&mes=9", headers=_h(admin_token))
    assert r.status_code == 200
    fila = next(x for x in r.json() if x["doc"] == afiliado_listo["doc"])
    assert fila["planilla_id"] is None

    client.post("/liquidacion", headers=_h(admin_token),
                json={"afiliado_id": afiliado_listo["afiliado_id"], "anio": 2026, "mes": 9})

    r = client.get("/liquidacion/pendientes?anio=2026&mes=9", headers=_h(admin_token))
    fila = next(x for x in r.json() if x["doc"] == afiliado_listo["doc"])
    assert fila["planilla_id"] is not None
    assert fila["estado"] == "generada"
    assert fila["total"] > 0


def test_descargar_con_otro_tipo_de_documento(client, admin_token, afiliado_listo):
    """Cambia solo el campo 3; el resto del registro queda igual."""
    liq_id = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"],
        "anio": 2026, "mes": 9}).json()["id"]

    original = client.get(f"/liquidacion/{liq_id}/plano",
                          headers=_h(admin_token)).text.rstrip("\r\n").split("\r\n")
    con_ce = client.get(f"/liquidacion/{liq_id}/plano?tipo_doc=CE",
                        headers=_h(admin_token)).text.rstrip("\r\n").split("\r\n")

    assert original[1][7:9] == "CC"
    assert con_ce[1][7:9] == "CE"
    assert original[1][9:] == con_ce[1][9:], "solo cambia el tipo de documento"
    assert original[0] == con_ce[0], "el encabezado no se toca"


def test_tipo_de_documento_invalido_al_descargar(client, admin_token, afiliado_listo):
    liq_id = client.post("/liquidacion", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"],
        "anio": 2026, "mes": 9}).json()["id"]
    r = client.get(f"/liquidacion/{liq_id}/plano?tipo_doc=ZZ", headers=_h(admin_token))
    assert r.status_code == 400


def test_afiliado_inexistente(client, admin_token):
    r = client.post("/liquidacion/previsualizar", headers=_h(admin_token),
                    json={"afiliado_id": 999999, "anio": 2026, "mes": 9})
    assert r.status_code == 404


def test_mes_invalido_rechazado(client, admin_token, afiliado_listo):
    r = client.post("/liquidacion/previsualizar", headers=_h(admin_token), json={
        "afiliado_id": afiliado_listo["afiliado_id"], "anio": 2026, "mes": 13})
    assert r.status_code == 422


def test_requiere_autenticacion(client):
    assert client.get("/liquidacion").status_code in (401, 403)


# ─── Contraste contra un plano real del operador ──────────────────────────────
#
# `tests/fixtures/plano_referencia_operador.txt` es una planilla tipo E generada
# por otro sistema y aceptada por el operador. Es la única fuente que dice cómo
# se escriben de verdad los campos que el anexo no detalla: el formato de las
# tarifas salió de aquí, después de que el validador rechazara tres
# codificaciones distintas.

def _referencia():
    ruta = Path(__file__).parent / "fixtures" / "plano_referencia_operador.txt"
    lineas = [l for l in ruta.read_text(encoding="latin-1").splitlines() if l.strip()]
    return lineas[0], lineas[1]


def test_la_referencia_tiene_los_largos_del_anexo():
    encabezado, detalle = _referencia()
    assert len(encabezado) == plano.LARGO_TIPO_1 == 359
    assert len(detalle) == plano.LARGO_TIPO_2 == 693


@pytest.mark.parametrize("campo,esperado", [
    ("tipo_registro", "02"),
    ("tipo_doc", "CC"),
    ("tipo_cotizante", "01"),
    ("primer_apellido", "CORONELL".ljust(20)),
    ("primer_nombre", "DUVAL".ljust(20)),
    ("cod_afp", "230201"),
    ("cod_eps", "EPSC07"),
    ("cod_ccf", "CCF68 "),
    ("salario_basico", "001750905"),
    ("ibc_pension", "000058364"),
    ("cot_pension", "000009400"),
    ("exonerado_salud_sena_icbf", "S"),
    ("nov_RET", "X"),
    ("fecha_RET", "2026-07-01"),
])
def test_el_mapa_de_campos_decodifica_la_referencia(campo, esperado):
    """Si el mapa estuviera corrido, estos valores caerían en otra posición."""
    _, detalle = _referencia()
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == campo)
    assert detalle[c.inicio - 1 : c.inicio - 1 + c.longitud] == esperado


@pytest.mark.parametrize("campo,tarifa", [
    ("tarifa_pension", "0.16"),
    ("tarifa_salud", "0.04"),
    ("tarifa_arl", "0.0435"),
    ("tarifa_ccf", "0.04"),
    ("tarifa_sena", 0),
    ("tarifa_icbf", 0),
    ("tarifa_esap", 0),
    ("tarifa_men", 0),
])
def test_las_tarifas_se_escriben_como_en_la_referencia(campo, tarifa):
    """Byte por byte: el formateador debe producir lo mismo que el operador aceptó."""
    _, detalle = _referencia()
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == campo)
    en_referencia = detalle[c.inicio - 1 : c.inicio - 1 + c.longitud]
    assert plano.formatear_tarifa(tarifa, c.longitud) == en_referencia


def test_el_encabezado_de_la_referencia_tambien_encaja():
    encabezado, _ = _referencia()
    esperados = {
        "tipo_registro": "01",
        "tipo_doc_aportante": "NI",
        "num_doc_aportante": "901760008".ljust(16),
        "dv_aportante": "7",
        "tipo_planilla": "E",
        "cod_arl": "14-11 ",
        "periodo_pago_otros": "2026-07",
        "periodo_pago_salud": "2026-08",
        "total_cotizantes": "00001",
        "tipo_aportante": "01",
    }
    for nombre, esperado in esperados.items():
        c = next(x for x in plano.CAMPOS_TIPO_1 if x.nombre == nombre)
        assert encabezado[c.inicio - 1 : c.inicio - 1 + c.longitud] == esperado, nombre

def test_sucursal_replica_la_referencia():
    """El operador exige sucursal aunque el anexo permita la forma "U".

    Con "U" y la sucursal en blanco devolvio: "Para la forma de presentacion S
    el codigo de sucursal es obligatorio".
    """
    class SinSucursal:
        cod_sucursal = ""
        nombre_sucursal = ""

    class ConSucursal:
        cod_sucursal = "07"
        nombre_sucursal = "MEDELLIN"

    assert plano.datos_sucursal(SinSucursal()) == ("S", "01", "01")
    assert plano.datos_sucursal(ConSucursal()) == ("S", "07", "MEDELLIN")


def test_el_encabezado_nunca_sale_sin_sucursal():
    class Aportante:
        razon_social = "DEMO SAS"
        tipo_doc = "NI"; num_doc = "900123456"; dv = "8"
        tipo_aportante = "01"; cod_arl = "14-11"
        cod_sucursal = ""; nombre_sucursal = ""

    forma, codigo, nombre = plano.datos_sucursal(Aportante())
    linea = plano.registro_tipo_1({
        "modalidad_planilla": 1, "secuencia": 1,
        "razon_social": "DEMO SAS", "tipo_doc_aportante": "NI",
        "num_doc_aportante": "900123456", "dv_aportante": 8,
        "tipo_planilla": "E", "forma_presentacion": forma,
        "cod_sucursal": codigo, "nombre_sucursal": nombre,
        "periodo_pago_otros": "2026-09", "periodo_pago_salud": "2026-10",
        "total_cotizantes": 1, "tipo_aportante": "01",
    })
    assert linea[247] == "S"                      # campo 11
    assert linea[248:258].strip() != ""           # campo 12, obligatorio con S

# ─── Valores que el operador corrigió en la validación ────────────────────────

def test_aportes_se_aproximan_a_la_centena_superior():
    """Cifras exactas del reporte de validación sobre un IBC de un salario mínimo."""
    assert P.aproximar_aporte(70036) == 70100      # salud 4%
    assert P.aproximar_aporte(280145) == 280200    # pensión 16%
    assert P.aproximar_aporte(9140) == 9200        # riesgos 0,522%


def test_la_aproximacion_es_hacia_arriba_no_a_la_mas_cercana():
    assert P.aproximar_aporte(70036) == 70100, "70.036 sube a 70.100, no baja a 70.000"
    assert P.aproximar_aporte(101) == 200
    assert P.aproximar_aporte(100) == 100, "un múltiplo exacto no se mueve"
    assert P.aproximar_aporte(0) == 0


def test_el_ibc_no_se_aproxima_a_la_centena():
    """La aproximación es de la cotización, no de la base."""
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    assert d.ibc_salud == SMLMV_2026            # 1.750.905, no 1.751.000


def test_cotizaciones_del_caso_validado():
    """El cotizante que pasó por el validador, con su empresa exonerada."""
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(exonerado=True), 2026, 9)
    assert d.cot_salud == 70100
    assert d.cot_pension == 280200
    assert d.cot_arl == 9200
    assert d.valor_ccf == 70100


# ─── Períodos del encabezado ──────────────────────────────────────────────────

def test_salud_lleva_el_mes_liquidado_y_los_demas_el_anterior():
    """El operador avisó: reportaba salud 2026-10 liquidando 2026-09."""
    assert plano.periodos_del_encabezado("2026-09") == ("2026-08", "2026-09")


def test_los_periodos_cruzan_bien_el_cambio_de_ano():
    assert plano.periodos_del_encabezado("2026-01") == ("2025-12", "2026-01")
    assert plano.periodos_del_encabezado("2026-12") == ("2026-11", "2026-12")


# ─── Campos que el operador no acepta vacíos ──────────────────────────────────

def test_las_horas_laboradas_nunca_son_cero():
    """"El número de horas laboradas no puede ser 0", dijo la validación."""
    d = motor.liquidar_afiliado(_Afiliado(), _Aportante(), 2026, 9)
    assert d.horas_laboradas == 240              # 30 días × 8

    parcial = motor.liquidar_afiliado(_Afiliado(fecha_ingreso="2026-09-11"),
                                      _Aportante(), 2026, 9)
    assert parcial.horas_laboradas == 160        # 20 días × 8


def test_campo_98_es_la_subactividad_economica():
    """No es una tarifa: el operador lo valida contra su tabla de actividades."""
    campo = next(c for c in plano.CAMPOS_TIPO_2 if c.numero == 98)
    assert campo.nombre == "subactividad_economica"

    class ConActividad(_Aportante):
        actividad_economica = "1649201"

    d = motor.liquidar_afiliado(_Afiliado(), ConActividad(), 2026, 9)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert linea[686:693] == "1649201"
