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


def test_la_planilla_Y_tiene_su_propia_lista():
    """Salio de los nueve casos que enumera su seccion en el anexo."""
    assert ob.revisar_planilla("59", "Y") == []
    assert ob.revisar_planilla("59", "E") != []
    # Un dependiente no cabe ahi: la Y es de independientes.
    assert ob.revisar_planilla("01", "Y") != []


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


# ─── Cooperativas y asociaciones que pagan por sus asociados ──────────────────
#
# El cuarto caso de la planilla Y:
#
#   "Aportante que sea agremiaciones, asociaciones o congregaciones religiosas
#    autorizadas por este Ministerio que pagan los aportes de los trabajadores
#    independientes agremiados o asociados a ellas para los tipos de cotizantes
#    16 - Independiente agremiado o asociado y 57 - Independiente Voluntario a
#    Riesgos Laborales"
#
# Y el tipo 16: "esta obligado a aportar a los Sistemas Generales de Salud y
# Pension, el pago de aportes al Sistema General de Riesgos laborales y a Cajas
# de Compensacion Familiar es voluntario".
#
# Es la figura de una cooperativa que cotiza por sus asociados independientes,
# donde cada uno elige su cobertura.

import json


def _asociado(servicios, planilla="Y"):
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.tipo_cotizante = "16"; af.subtipo = "0"; af.subtipo_cotizante = ""
    af.servicios = json.dumps(servicios)
    af.arl = ""; af.cod_arl = ""; af.clase_riesgo = ""; af.cod_ccf = "CCF24"
    af.ibc = af.salario_basico = 1750905
    ap = _Aportante()
    ap.tipo_aportante = "04"; ap.cod_arl = ""; ap.clase_riesgo = ""
    return liquidar([af], ap, 2026, 9, tipo_planilla=planilla)


def test_el_16_esta_en_la_planilla_Y():
    assert "16" in ob.TIPOS_POR_PLANILLA["Y"]
    assert ob.revisar_planilla("16", "Y") == []


def test_el_16_no_va_en_la_planilla_E():
    """La lista oficial de la E no lo incluye, y el operador lo rechaza."""
    assert "16" not in ob.TIPOS_POR_PLANILLA["E"]
    assert ob.revisar_planilla("16", "E") != []


def test_un_asociado_con_salud_y_pension_pasa():
    """Riesgos y caja son voluntarios: no tenerlos no es un error."""
    r = _asociado(["EPS", "AFP"])
    avisos = [a for a in r.avisos if "no tiene planilla" not in a]
    assert avisos == []
    assert int(r.total_salud) > 0 and int(r.total_pension) > 0
    assert int(r.total_arl) == 0 and int(r.total_ccf) == 0


def test_un_asociado_sin_pension_si_avisa():
    """La pension si es obligatoria para el 16."""
    r = _asociado(["EPS"])
    assert any("pensión" in a for a in r.avisos)


def test_un_asociado_sin_salud_tambien():
    r = _asociado(["AFP"])
    assert any("salud" in a for a in r.avisos)


def test_puede_aportar_riesgos_y_caja_si_quiere():
    """Voluntario no es prohibido: quien los contrate, los paga."""
    r = _asociado(["EPS", "AFP", "ARL 4", "CCF"])
    assert int(r.total_arl) > 0 and int(r.total_ccf) > 0


def test_el_asociado_paga_la_tarifa_plena_de_salud():
    """No hay empleador que ponga la otra parte: aporta el 12,5%."""
    from services.pila import parametros as P
    d = _asociado(["EPS", "AFP"]).detalles[0]
    assert d.tarifa_salud == P.TARIFA_SALUD


def test_el_57_tambien_cabe_en_la_Y():
    """El mismo caso del anexo nombra los dos tipos."""
    assert ob.revisar_planilla("57", "Y") == []
