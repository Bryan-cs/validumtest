# -*- coding: utf-8 -*-
"""Salud, riesgos y caja van juntos o no van.

No es una lectura del anexo: es lo que el validador del operador devolvio
probando las combinaciones una a una, con los mismos datos y cambiando un
subsistema cada vez.

    solo EPS          819 "dias cotizados a riesgos no pueden ser 0"
                      283 "dias de salud (30) y riesgos (0) deben ser iguales"
                      691 "los IBC de salud y riesgos deben ser iguales"
    EPS + ARL         285 "dias de riesgos y parafiscales deben ser iguales"
                      820 "dias a parafiscales no pueden ser 0"
    EPS + ARL + CCF   0 errores

La pension es la excepcion, y por eso se puede apagar sola con el subtipo de
cotizante 04 sin que el operador reclame.
"""
import pytest

from services.pila import obligaciones as ob


class _Det:
    def __init__(self, tipo="01", salud=0, arl=0, ccf=0):
        self.tipo_cotizante = tipo
        self.dias_salud, self.dias_arl, self.dias_ccf = salud, arl, ccf


def test_los_tres_con_los_mismos_dias_pasan():
    assert ob.revisar_subsistemas_parejos(_Det(salud=30, arl=30, ccf=30)) == []


def test_solo_salud_avisa():
    avisos = ob.revisar_subsistemas_parejos(_Det(salud=30))
    assert len(avisos) == 1
    assert "riesgos laborales" in avisos[0] and "caja" in avisos[0]


def test_salud_y_riesgos_sin_caja_avisa():
    avisos = ob.revisar_subsistemas_parejos(_Det(salud=30, arl=30))
    assert "caja de compensación" in avisos[0]


def test_salud_y_caja_sin_riesgos_avisa():
    avisos = ob.revisar_subsistemas_parejos(_Det(salud=30, ccf=30))
    assert "riesgos laborales" in avisos[0]


def test_dias_distintos_entre_subsistemas_avisa():
    avisos = ob.revisar_subsistemas_parejos(_Det(salud=30, arl=20, ccf=30))
    assert "no coinciden" in avisos[0]
    assert "riesgos laborales 20" in avisos[0]


def test_un_periodo_parcial_parejo_no_avisa():
    """Veinte dias en los tres esta bien: lo que importa es que coincidan."""
    assert ob.revisar_subsistemas_parejos(_Det(salud=20, arl=20, ccf=20)) == []


def test_sin_liquidar_nada_no_avisa_por_aqui():
    """De eso ya se queja el aviso de servicios contratados."""
    assert ob.revisar_subsistemas_parejos(_Det()) != []


@pytest.mark.parametrize("tipo", ["03", "12", "19", "21", "42", "57"])
def test_los_tipos_que_no_deben_los_tres_quedan_fuera(tipo):
    """La regla es de quien esta obligado a los tres, no de todo el mundo."""
    assert ob.revisar_subsistemas_parejos(_Det(tipo=tipo, salud=30)) == []


def test_un_tipo_desconocido_no_inventa_reglas():
    assert ob.revisar_subsistemas_parejos(_Det(tipo="99", salud=30)) == []


def test_el_aviso_llega_al_resumen():
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "20"; af.subtipo_cotizante = ""
    af.servicios = '["EPS"]'; af.arl = ""
    af.cod_arl = ""; af.clase_riesgo = ""
    ap = _Aportante(); ap.cod_arl = ""; ap.clase_riesgo = ""
    avisos = liquidar([af], ap, 2026, 9).avisos
    assert any("van los tres o no va ninguno" in a for a in avisos)


# ─── Riesgos reportados sin aporte ────────────────────────────────────────────
#
# Quien esta afiliado a una ARL pero no cotiza riesgos este periodo se reporta
# con sus dias e IBC y la tarifa en cero. El archivo dice "esta afiliado, no
# hay aporte", que es cierto, y satisface las tres reglas que el operador
# exige juntas: 819, 283 y 691.

import json


def _liquidar(servicios, **cambios):
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "20"; af.subtipo_cotizante = ""
    af.arl = ""; af.clase_riesgo = "4"; af.cod_arl = "14-11"; af.cod_ccf = "CCF24"
    af.servicios = json.dumps(servicios)
    af.ibc = af.salario_basico = 1750905
    for k, v in cambios.items():
        setattr(af, k, v)
    return liquidar([af], _Aportante(), 2026, 9).detalles[0]


def test_sin_riesgos_contratados_se_reporta_la_afiliacion():
    d = _liquidar(["EPS", "CCF"])
    assert d.dias_arl == d.dias_salud == 30
    assert int(d.ibc_arl) == int(d.ibc_salud)
    assert int(d.tarifa_arl) == 0
    assert int(d.cot_arl) == 0
    assert d.cod_arl == "14-11"
    assert d.clase_riesgo == "1"


def test_con_riesgos_contratados_se_cobra_normal():
    d = _liquidar(["EPS", "CCF", "ARL 4"])
    assert float(d.tarifa_arl) == 0.0435
    assert int(d.cot_arl) > 0


def test_salud_y_caja_sin_riesgos_ya_no_avisa():
    """Era el caso que no se podia generar: ahora cuadra solo."""
    from services.pila import obligaciones as ob
    d = _liquidar(["EPS", "CCF"])
    assert ob.revisar_subsistemas_parejos(d) == []


def test_la_afiliacion_puede_venir_del_aportante():
    """La ARL la contrata la empresa: si el afiliado no la tiene, es la suya."""
    d = _liquidar(["EPS", "CCF"], cod_arl="", clase_riesgo="")
    assert d.dias_arl == 30
    assert d.cod_arl == "14-11"          # la del aportante


def test_sin_clase_la_arl_de_la_empresa_igual_declara_riesgos_y_caja():
    """Una ficha de solo EPS en una empresa sin departamento ni clase.

    Antes los días de riesgos quedaban en 0, la caja no se declaraba y el
    departamento salía vacío. El operador lo rechaza en bloque. Con el código
    de ARL de la empresa alcanza para reportar lo mismo que en las demás.
    """
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "20"
    af.subtipo_cotizante = ""
    af.arl = ""
    af.cod_arl = ""
    af.clase_riesgo = ""
    af.cod_ccf = ""
    af.ccf = ""
    af.cod_depto_labor = ""
    af.cod_municipio_labor = ""
    af.servicios = json.dumps(["EPS"])
    af.ibc = af.salario_basico = 1750905
    ap = _Aportante()
    ap.cod_arl = "14-11"
    ap.clase_riesgo = ""
    ap.cod_depto = ""
    ap.cod_municipio = ""
    d = liquidar([af], ap, 2026, 9).detalles[0]
    assert d.dias_arl == d.dias_salud == d.dias_ccf == 30
    assert int(d.ibc_arl) == int(d.ibc_salud)
    assert int(d.tarifa_arl) == 0
    assert d.cod_ccf == "CCF68"
    assert d.cod_depto_labor == "99"
    assert d.cod_municipio_labor == "773"


def test_sin_afiliacion_en_ningun_lado_no_se_inventa_una():
    """Rellenar los dias con una ARL que no existe seria otra cosa."""
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "20"; af.subtipo_cotizante = ""; af.arl = ""
    af.cod_arl = ""; af.clase_riesgo = ""
    af.servicios = json.dumps(["EPS", "CCF"])
    af.ibc = af.salario_basico = 1750905
    ap = _Aportante(); ap.cod_arl = ""; ap.clase_riesgo = ""
    d = liquidar([af], ap, 2026, 9).detalles[0]
    assert d.dias_arl == 0
    assert d.cod_arl == ""


def test_el_ibc_de_riesgos_sigue_al_de_salud_en_periodos_parciales():
    """La regla 691 pide que sean iguales, tambien con menos dias."""
    d = _liquidar(["EPS", "CCF"], fecha_ingreso="2026-09-11")
    assert d.dias_arl == d.dias_salud == 20
    assert int(d.ibc_arl) == int(d.ibc_salud)


# ─── IBC de caja según los planos ARUS que el operador acepta ──────────────────
#
# Sin CCF contratada: IBC caja 100 y aporte 100 (tarifa 4%).
# Con CCF contratada: IBC caja = 1 SMLMV y aporte 70.100.
# ARL contratada cotiza su clase; si no, tarifa 0 y cotización 0.
# Salud, riesgos y caja siempre con los mismos días.


@pytest.mark.parametrize("servicios,ibc_caja,arl_cero", [
    (["EPS"], 100, True),
    (["EPS", "ARL 4"], 100, False),
    (["EPS", "CCF"], 1750905, True),
    (["EPS", "CCF", "ARL 4"], 1750905, False),
])
def test_ce_sigue_los_planos_arus(servicios, ibc_caja, arl_cero):
    from services.pila import obligaciones as ob
    from services.pila import parametros as P
    from services.pila import plano
    d = _liquidar(servicios)
    assert d.tipo_doc == "CE"
    assert d.dias_ccf == d.dias_salud == d.dias_arl == 30
    assert int(d.ibc_ccf) == ibc_caja
    assert int(d.valor_ccf) == int(P.aproximar_aporte(d.ibc_ccf * P.TARIFA_CCF))
    assert int(d.valor_sena) == 0
    assert int(d.valor_icbf) == 0
    if arl_cero:
        assert int(d.tarifa_arl) == 0
        assert int(d.cot_arl) == 0
    else:
        assert float(d.tarifa_arl) == 0.0435
        assert int(d.cot_arl) > 0
    assert ob.revisar_subsistemas_parejos(d) == []
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "ibc_ccf")
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert linea[c.inicio - 1:c.inicio - 1 + c.longitud] == f"{ibc_caja:09d}"


def test_suma_ibc_parafiscales_ignora_ibc_salud():
    """Error 183: la nómina del tipo 1 no es el IBC de salud."""
    from services.pila import plano

    class D:
        def __init__(self, ibc_ccf, ibc_salud=1750905):
            self.ibc_ccf = ibc_ccf
            self.ibc_salud = ibc_salud
            self.ibc_pension = ibc_salud

    assert plano.suma_ibc_parafiscales([D(100)]) == 100
    assert plano.suma_ibc_parafiscales([D(100), D(1750905)]) == 100 + 1750905
    assert plano.suma_ibc_parafiscales([D(0)]) == 0


class _Liq:
    periodo_cotizacion = "2026-09"
    tipo_planilla = "E"
    numero_planilla = 0
    fecha_limite_pago = ""


def _nomina_del_encabezado(texto):
    from services.pila import plano
    c = next(x for x in plano.CAMPOS_TIPO_1 if x.nombre == "valor_total_nomina")
    return int(texto.splitlines()[0][c.inicio - 1:c.inicio - 1 + c.longitud])


def test_encabezado_nomina_del_solo_eps_es_ibc_ccf_no_salud():
    """Solo EPS: IBC caja 100, IBC salud 1.750.905. El 183 pide la suma de caja."""
    from services.pila.liquidacion import liquidar
    from services.pila import plano
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "20"; af.subtipo_cotizante = ""
    af.arl = ""; af.clase_riesgo = "4"; af.cod_arl = "14-11"; af.cod_ccf = "CCF24"
    af.servicios = json.dumps(["EPS"])
    af.ibc = af.salario_basico = 1750905
    ap = _Aportante(); ap.tipo_doc = "NI"
    resumen = liquidar([af], ap, 2026, 9)
    d = resumen.detalles[0]
    assert int(d.ibc_ccf) == 100
    assert int(d.ibc_salud) == 1750905
    assert _nomina_del_encabezado(plano.generar(ap, _Liq(), resumen)) == 100


def test_encabezado_nomina_con_paquete_completo_sigue_siendo_el_ibc_real():
    """Con CCF y pensión el IBC de caja ya es el salario: la nómina no cambia."""
    from services.pila.liquidacion import liquidar
    from services.pila import plano
    from tests.test_liquidacion import _Afiliado, _Aportante
    af = _Afiliado(servicios=["EPS", "AFP", "CCF", "ARL 1"], clase_riesgo="1")
    ap = _Aportante()
    resumen = liquidar([af], ap, 2026, 9)
    assert int(resumen.detalles[0].ibc_ccf) == 1750905
    assert _nomina_del_encabezado(plano.generar(ap, _Liq(), resumen)) == 1750905


@pytest.mark.parametrize("clase", ["1", "2", "3", "4", "5"])
@pytest.mark.parametrize("con_caja", [False, True])
def test_ce_arl_1_a_5_cotiza_su_clase(clase, con_caja):
    """Riesgos usa el IBC real y su tarifa. Caja: 100 si no se paga, SMLMV si sí."""
    from services.pila import parametros as P
    servicios = ["EPS", f"ARL {clase}"]
    if con_caja:
        servicios.append("CCF")
    d = _liquidar(servicios, clase_riesgo=clase)
    tarifa = P.TARIFA_ARL_POR_CLASE[clase]
    assert d.clase_riesgo == clase
    assert d.tarifa_arl == tarifa
    assert int(d.ibc_arl) == 1750905
    assert int(d.cot_arl) == int(P.aproximar_aporte(d.ibc_arl * tarifa))
    assert int(d.ibc_ccf) == (1750905 if con_caja else 100)


def test_con_cc_y_caja_contratada_sin_pension_el_ibc_sigue_siendo_el_real():
    from services.pila.liquidacion import liquidar
    from tests.test_liquidacion import _Afiliado, _Aportante
    af = _Afiliado(servicios=["EPS", "CCF", "ARL 1"], clase_riesgo="1")
    d = liquidar([af], _Aportante(), 2026, 9).detalles[0]
    assert d.tipo_doc == "CC"
    assert int(d.ibc_ccf) == 1750905
    assert int(d.valor_ccf) > 100


def _con_pension(servicios, **kw):
    from services.pila.liquidacion import liquidar
    from tests.test_liquidacion import _Afiliado, _Aportante
    af = _Afiliado(servicios=servicios, clase_riesgo=kw.get("clase_riesgo", "1"))
    return liquidar([af], _Aportante(), 2026, 9).detalles[0]


def test_eps_y_pension_declara_caja_con_ibc_100():
    d = _con_pension(["EPS", "AFP"])
    assert int(d.cot_pension) > 0
    assert d.dias_ccf == d.dias_salud == d.dias_arl == 30
    assert int(d.ibc_ccf) == 100
    assert int(d.tarifa_arl) == 0


def test_eps_pension_y_caja_usa_el_ibc_minimo():
    """Se paga CCF: la base es 1 SMLMV, no 2400."""
    d = _con_pension(["EPS", "AFP", "CCF"])
    assert int(d.cot_pension) > 0
    assert d.dias_ccf == d.dias_salud == d.dias_arl == 30
    assert int(d.ibc_ccf) == 1750905
    assert int(d.valor_ccf) > 100
    assert int(d.tarifa_arl) == 0
    assert int(d.cot_arl) == 0


def test_eps_pension_y_arl_declara_caja_con_ibc_100():
    from services.pila import parametros as P
    d = _con_pension(["EPS", "AFP", "ARL 1"])
    assert int(d.cot_pension) > 0
    assert int(d.cot_arl) == int(P.aproximar_aporte(d.ibc_arl * P.TARIFA_ARL_POR_CLASE["1"]))
    assert int(d.ibc_ccf) == 100


def test_paquete_completo_con_pension_usa_el_ibc_real_de_caja():
    d = _con_pension(["EPS", "AFP", "CCF", "ARL 1"])
    assert int(d.cot_pension) > 0
    assert int(d.ibc_ccf) == 1750905
    assert int(d.valor_ccf) > 100


@pytest.mark.parametrize("clase", ["1", "2", "3", "4", "5"])
def test_eps_pension_arl_1_a_5_cotiza_su_clase_y_caja_en_100(clase):
    from services.pila import parametros as P
    d = _con_pension(["EPS", "AFP", f"ARL {clase}"], clase_riesgo=clase)
    tarifa = P.TARIFA_ARL_POR_CLASE[clase]
    assert d.clase_riesgo == clase
    assert int(d.cot_arl) == int(P.aproximar_aporte(d.ibc_arl * tarifa))
    assert int(d.ibc_ccf) == 100


def test_solo_eps_declara_ccf68_en_el_99_como_arus():
    """El ejemplo que cobra $0 de ARL y $100 de COMCAJA usa 99/773."""
    d = _liquidar(["EPS"], cod_ccf="CCF03", cod_depto_labor="76")
    assert d.cod_ccf == "CCF68"
    assert d.cod_depto_labor == "99"
    assert d.cod_municipio_labor == "773"
    assert int(d.ibc_ccf) == 100
    assert int(d.valor_ccf) == 100
    assert d.clase_riesgo == "1"
    assert int(d.tarifa_arl) == 0
    assert int(d.cot_arl) == 0
    assert d.novedades.get("VAC") == "L"


def test_con_arl_contratada_no_se_inventa_la_licencia():
    d = _liquidar(["EPS", "ARL 4"])
    assert int(d.cot_arl) > 0
    assert d.novedades.get("VAC") != "L"


def test_solo_eps_sin_caja_en_la_ficha_tambien_usa_ccf68():
    d = _liquidar(["EPS"], cod_ccf="", cod_depto_labor="11")
    assert d.cod_ccf == "CCF68"
    assert d.cod_depto_labor == "99"


def test_colsubsidio_se_reporta_aunque_el_aportante_este_en_otro_depto():
    """La caja de la ficha se paga. El DANE pasa a uno que esa caja cubre."""
    d = _liquidar(["EPS", "CCF"], cod_ccf="CCF22", cod_depto_labor="08",
                  cod_municipio_labor="573")
    assert d.cod_ccf == "CCF22"
    assert d.cod_depto_labor == "11"
    assert d.cod_municipio_labor == "001"
    assert int(d.ibc_ccf) == 1750905


def test_compensar_fuera_de_bogota_se_queda_y_el_dane_pasa_a_bogota():
    d = _liquidar(["EPS", "CCF"], cod_ccf="CCF24", cod_depto_labor="76")
    assert d.cod_ccf == "CCF24"
    assert d.cod_depto_labor == "11"
    assert d.cod_municipio_labor == "001"


def test_compensar_en_bogota_se_queda():
    d = _liquidar(["EPS", "CCF"], cod_ccf="CCF24", cod_depto_labor="11",
                  cod_municipio_labor="001")
    assert d.cod_ccf == "CCF24"
    assert d.cod_depto_labor == "11"
    assert d.cod_municipio_labor == "001"


def test_un_tipo_que_no_cotiza_a_caja_no_se_la_inventa():
    """El 20 (estudiante) tiene caja en N: mandarla seria otro rechazo."""
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.tipo_cotizante = "20"; af.subtipo = "0"; af.subtipo_cotizante = ""
    af.arl = ""; af.clase_riesgo = "4"; af.cod_arl = "14-11"; af.cod_ccf = "CCF24"
    af.servicios = json.dumps(["EPS", "ARL 4"])
    af.ibc = af.salario_basico = 1750905
    d = liquidar([af], _Aportante(), 2026, 9).detalles[0]
    assert int(d.dias_ccf) == 0
    assert int(d.ibc_ccf) == 0
