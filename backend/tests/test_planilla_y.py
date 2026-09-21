# -*- coding: utf-8 -*-
"""Planilla Y, independientes empresas.

El anexo la define asi: para aportantes "que tengan personas vinculadas a
traves de un contrato de prestacion de servicios... con una duracion superior
a un mes... y que su actividad este catalogada en las clases de riesgo IV o
V", donde "es obligatorio el aporte al Sistema General de Riesgos Laborales y
opcional efectuar en nombre de su contratista, los aportes a Salud y Pension,
asi como tambien los aportes a cajas de compensacion familiar... caso en el
cual el aportante debera reportar el tipo de cotizante 59".

Eso importa porque el 59, fuera de la planilla Y, tiene salud y pension
obligatorias. Dentro de ella solo debe riesgos.
"""
import pytest

from services.pila import obligaciones as ob


def test_el_59_con_solo_riesgos_pasa_en_la_planilla_Y():
    assert ob.revisar("59", ["ARL 4"], tipo_planilla="Y") == []


def test_el_mismo_caso_en_la_planilla_E_se_queja():
    """Fuera de la Y, el 59 debe salud y pension."""
    avisos = ob.revisar("59", ["ARL 4"], tipo_planilla="E")
    assert len(avisos) == 1
    assert "salud y pensión" in avisos[0]


def test_en_la_planilla_Y_la_caja_sigue_siendo_voluntaria():
    assert ob.revisar("59", ["ARL 4", "CCF"], tipo_planilla="Y") == []


def test_en_la_planilla_Y_se_puede_aportar_salud_y_pension():
    """Son opcionales, no prohibidas: el aportante puede hacerlos."""
    assert ob.revisar("59", ["EPS", "AFP", "ARL 4", "CCF"], tipo_planilla="Y") == []


def test_los_riesgos_si_son_obligatorios_en_la_Y():
    avisos = ob.revisar("59", ["EPS"], tipo_planilla="Y")
    assert len(avisos) == 1
    assert "riesgos laborales" in avisos[0]


def test_sin_decir_la_planilla_se_usan_las_reglas_generales():
    assert ob.reglas_de("59") == ob.OBLIGACIONES["59"]
    assert ob.reglas_de("59", "Y") == ("V", "V", "O", "V")


def test_la_regla_propia_solo_afecta_al_59():
    """Un dependiente sigue debiendo lo mismo en cualquier planilla."""
    assert ob.reglas_de("01", "Y") == ob.OBLIGACIONES["01"]


def test_la_planilla_Y_no_valida_que_tipos_acepta():
    """No tenemos su lista autorizada, y inventarla bloquearia planillas buenas.

    De la E si la tenemos, porque el operador la devolvio en el texto de un
    rechazo. Cuando devuelva la de la Y, se agrega.
    """
    assert "Y" not in ob.TIPOS_POR_PLANILLA
    assert ob.revisar_planilla("59", "Y") == []
    assert ob.revisar_planilla("59", "E") != []


def test_liquidar_en_planilla_Y_no_reclama_salud_ni_pension():
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.tipo_cotizante = "59"; af.subtipo = "0"; af.subtipo_cotizante = ""
    af.servicios = '["ARL 4"]'; af.clase_riesgo = "4"
    af.ibc = af.salario_basico = 1750905
    resumen = liquidar([af], _Aportante(), 2026, 9, tipo_planilla="Y")
    assert not any("obligado a cotizar" in a for a in resumen.avisos)
    assert int(resumen.total_arl) > 0
