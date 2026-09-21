# -*- coding: utf-8 -*-
"""Campos que solo valen para ciertos tipos de cotizante.

Estas cuatro reglas salieron de un rechazo real. El operador devolvio, en el
texto de cada error, la lista completa de tipos permitidos, que es mas de lo
que trae el anexo junto en un solo lugar:

  "El cotizante registra horas laboradas pero no realiza aportes a CCF"
  "El tipo cotizante 23 no permite exoneracion de pago parafiscales, los
   permitidos son 1, 2, 18, 20, 22, 30, 32, 55, 31, 68, 71"
  "El tipo cotizante 23 no puede tener marcado el campo tipo de salario"
  "El tipo de cotizante 23 no es valido en el tipo de planilla E"
"""
import pytest

from services.pila import obligaciones as ob, plano
from services.pila.liquidacion import liquidar_afiliado, liquidar
from tests.test_pila_subtipo import _Afiliado, _Aportante


def _liquidar(tipo_cotizante="01", **cambios):
    af = _Afiliado()
    af.tipo_cotizante = tipo_cotizante
    af.subtipo_cotizante = ""
    af.subtipo = "0"
    af.servicios = '["EPS","AFP","CCF","ARL 1"]'
    for k, v in cambios.items():
        setattr(af, k, v)
    return liquidar_afiliado(af, _Aportante(), 2026, 9)


# ─── Campo 96: horas laboradas ────────────────────────────────────────────────

@pytest.mark.parametrize("tipo", sorted(ob.TIPOS_CON_HORAS))
def test_los_tipos_que_admiten_horas_las_reportan(tipo):
    assert _liquidar(tipo).horas_laboradas == 30 * 8


@pytest.mark.parametrize("tipo", ["03", "12", "19", "21", "23", "42", "59"])
def test_los_demas_no_reportan_horas(tipo):
    assert _liquidar(tipo).horas_laboradas == 0


def test_sin_aportes_a_caja_no_hay_horas():
    """El operador avisa cuando hay horas reportadas y no hay aportes a CCF."""
    d = _liquidar("01", servicios='["EPS","AFP","ARL 1"]')
    assert int(d.dias_ccf) == 0
    assert d.horas_laboradas == 0


# ─── Campo 76: exoneracion de parafiscales ────────────────────────────────────

@pytest.mark.parametrize("tipo", ["01", "02", "18", "22", "30"])
def test_los_tipos_permitidos_llevan_la_exoneracion(tipo):
    assert _liquidar(tipo).exonerado is True


@pytest.mark.parametrize("tipo", ["03", "12", "19", "21", "23", "42", "59"])
def test_los_demas_no_la_llevan_aunque_el_aportante_este_exonerado(tipo):
    assert _liquidar(tipo).exonerado is False


def test_la_lista_es_la_que_devolvio_el_operador():
    assert ob.TIPOS_CON_EXONERACION == {
        "01", "02", "18", "20", "22", "30", "31", "32", "55", "68", "71"}


def test_sin_exoneracion_la_tarifa_de_salud_es_la_completa():
    """No es solo la marca: cambia lo que se paga."""
    from services.pila import parametros as P
    assert _liquidar("03").tarifa_salud == P.TARIFA_SALUD
    assert _liquidar("01").tarifa_salud == P.TARIFA_SALUD_TRABAJADOR


# ─── Campo 41: tipo de salario ────────────────────────────────────────────────

@pytest.mark.parametrize("tipo", sorted(ob.TIPOS_CON_TIPO_SALARIO))
def test_los_tipos_con_salario_lo_reportan(tipo):
    assert _liquidar(tipo).tipo_salario == "F"


@pytest.mark.parametrize("tipo", ["03", "12", "19", "21", "23", "42", "59"])
def test_los_demas_dejan_el_campo_en_blanco(tipo):
    assert _liquidar(tipo).tipo_salario == ""


def test_el_campo_sale_en_blanco_en_el_archivo():
    d = _liquidar("23")
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "tipo_salario")
    assert linea[c.inicio - 1] == " "


# ─── Tipos de cotizante validos en cada planilla ──────────────────────────────

def test_el_23_no_cabe_en_una_planilla_E():
    avisos = ob.revisar_planilla("23", "E")
    assert len(avisos) == 1
    assert "planilla tipo E" in avisos[0]


@pytest.mark.parametrize("tipo", ["01", "12", "18", "19", "20", "22", "30", "51"])
def test_los_validos_no_avisan(tipo):
    assert ob.revisar_planilla(tipo, "E") == []


def test_una_planilla_sin_lista_no_valida_nada():
    """Solo esta cargada la E; inventar las otras seria peor que no validar."""
    assert ob.revisar_planilla("23", "S") == []
    assert ob.revisar_planilla("23", "") == []


def test_el_aviso_llega_al_resumen():
    af = _Afiliado()
    af.tipo_cotizante = "23"; af.subtipo = "0"; af.subtipo_cotizante = ""
    af.servicios = '["ARL 1"]'
    resumen = liquidar([af], _Aportante(), 2026, 9)
    assert any("planilla tipo E" in a for a in resumen.avisos)


# ─── Advertencia de primera planilla ──────────────────────────────────────────

def test_el_mes_anterior_cruza_bien_el_ano():
    from routers.liquidacion import _mes_anterior
    assert _mes_anterior(2026, 1) == "2025-12"
    assert _mes_anterior(2026, 9) == "2026-08"
    assert _mes_anterior(2026, 12) == "2026-11"
