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
    avisos = liquidar([af], _Aportante(), 2026, 9).avisos
    assert any("van los tres o no va ninguno" in a for a in avisos)
