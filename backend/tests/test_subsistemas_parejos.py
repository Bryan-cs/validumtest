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
    assert d.clase_riesgo == "4"


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


# ─── IBC de caja 2400 ─────────────────────────────────────────────────────────
#
# Con CE y sin pensión, las cuatro combinaciones declaran caja con IBC 2400.
# Quien solo liquida EPS y ARL (aunque sea con CC) también: el operador
# rechaza parafiscales en cero (285 y 820).


@pytest.mark.parametrize("servicios", [
    ["EPS"],
    ["EPS", "CCF"],
    ["EPS", "ARL 4"],
    ["EPS", "CCF", "ARL 4"],
])
def test_ce_todas_las_combinaciones_ibc_ccf_2400(servicios):
    from services.pila import obligaciones as ob
    from services.pila import parametros as P
    from services.pila import plano
    d = _liquidar(servicios)
    assert d.tipo_doc == "CE"
    assert d.dias_ccf == d.dias_salud == d.dias_arl == 30
    assert int(d.ibc_ccf) == 2400
    assert int(d.valor_ccf) == int(P.aproximar_aporte(P.IBC_CCF_SIN_CONTRATO * P.TARIFA_CCF))
    assert int(d.valor_sena) == 0
    assert int(d.valor_icbf) == 0
    assert ob.revisar_subsistemas_parejos(d) == []
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "ibc_ccf")
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    assert linea[c.inicio - 1:c.inicio - 1 + c.longitud] == "000002400"


@pytest.mark.parametrize("clase", ["1", "2", "3", "4", "5"])
@pytest.mark.parametrize("con_caja", [False, True])
def test_ce_arl_1_a_5_cotiza_su_clase_y_caja_sigue_en_2400(clase, con_caja):
    """El 2400 es de caja. Riesgos usa el IBC real y la tarifa de su clase."""
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
    assert int(d.ibc_ccf) == 2400


def test_con_cc_y_caja_contratada_el_ibc_sigue_siendo_el_real():
    from services.pila.liquidacion import liquidar
    from tests.test_liquidacion import _Afiliado, _Aportante
    af = _Afiliado(servicios=["EPS", "CCF", "ARL 1"], clase_riesgo="1")
    d = liquidar([af], _Aportante(), 2026, 9).detalles[0]
    assert d.tipo_doc == "CC"
    assert int(d.ibc_ccf) == 1750905
    assert int(d.valor_ccf) > 100


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
