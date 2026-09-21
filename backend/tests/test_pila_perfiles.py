# -*- coding: utf-8 -*-
"""El subtipo del formulario decide la pension.

Los cinco valores del campo `subtipo` del formulario de afiliados —0, 3, 4, 20
y 22— son la forma en que el negocio ya venia clasificando a la gente por su
situacion pensional. Esta traduccion es la que hace que el archivo plano diga
lo correcto sin pedirle al usuario que aprenda el anexo.
"""
import pytest

from services.pila import perfiles, obligaciones as ob
from tests.test_pila_subtipo import _Afiliado, _Aportante
from services.pila.liquidacion import liquidar_afiliado


def _liquidar(subtipo, **cambios):
    af = _Afiliado()
    af.subtipo = subtipo
    af.subtipo_cotizante = "00"      # como queda en la base cuando no se toca
    af.servicios = '["EPS","CCF","ARL 1"]'
    af.cod_afp = "230301"
    for k, v in cambios.items():
        setattr(af, k, v)
    return liquidar_afiliado(af, _Aportante(), 2026, 9)


def test_subtipo_0_cotiza_pension_si_la_tiene_contratada():
    d = _liquidar("0", servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) > 0


def test_subtipo_0_sin_afp_contratada_no_liquida_pension():
    """El 0 no fuerza nada: sigue lo contratado."""
    assert int(_liquidar("0").cot_pension) == 0


@pytest.mark.parametrize("subtipo,esperado", [("3", "03"), ("4", "04")])
def test_los_exonerados_llevan_su_subtipo_de_cotizante(subtipo, esperado):
    d = _liquidar(subtipo)
    assert d.subtipo_cotizante == esperado
    assert int(d.cot_pension) == 0
    assert d.cod_afp == ""


def test_el_exonerado_no_cotiza_pension_ni_teniendola_contratada():
    """Estar exonerada manda sobre el formulario: por eso existe el subtipo."""
    d = _liquidar("4", servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) == 0


@pytest.mark.parametrize("subtipo", ["20", "22"])
def test_los_dos_grupos_de_extranjeria_salen_sin_pension(subtipo):
    """Su tipo de cotizante exigiria pension; la marca del campo 7 la levanta."""
    d = _liquidar(subtipo)
    assert d.extranjero_no_pension is True
    assert int(d.cot_pension) == 0
    assert d.cod_afp == ""


@pytest.mark.parametrize("subtipo", ["20", "22"])
def test_ni_teniendo_la_pension_contratada(subtipo):
    d = _liquidar(subtipo, servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) == 0


@pytest.mark.parametrize("subtipo", ["20", "22"])
def test_los_dos_grupos_de_extranjeria_salen_con_cedula_de_extranjeria(subtipo):
    assert perfiles.documento_sugerido(subtipo, "CC") == "CE"


@pytest.mark.parametrize("subtipo", ["0", "3", "4"])
def test_los_demas_conservan_su_documento(subtipo):
    assert perfiles.documento_sugerido(subtipo, "CC") == ""


def test_no_se_sugiere_el_documento_que_la_persona_ya_tiene():
    assert perfiles.documento_sugerido("22", "CE") == ""


def test_un_subtipo_desconocido_no_cambia_nada():
    """Inventar una regla sobre la pension de alguien es peor que no aplicarla."""
    d = _liquidar("99", servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) > 0
    assert d.subtipo_cotizante == "00"
    assert d.extranjero_no_pension is False


def test_un_subtipo_de_cotizante_puesto_a_mano_le_gana_al_perfil():
    """Si alguien escribio el subtipo del anexo, esa decision manda."""
    d = _liquidar("4", subtipo_cotizante="05")
    assert d.subtipo_cotizante == "05"


def test_el_22_con_cedula_de_ciudadania_avisa():
    """La marca del campo 7 no vale con CC, y el operador lo rechaza."""
    d = _liquidar("22")
    avisos = ob.revisar(d.tipo_cotizante, ob.liquidados(d),
                        extranjero_no_pension=d.extranjero_no_pension,
                        tipo_doc="CC", subtipo_cotizante=d.subtipo_cotizante)
    assert any("el documento es CC" in a for a in avisos)


def test_el_22_con_cedula_de_extranjeria_no_avisa_por_el_documento():
    d = _liquidar("22")
    avisos = ob.revisar(d.tipo_cotizante, ob.liquidados(d),
                        extranjero_no_pension=d.extranjero_no_pension,
                        tipo_doc="CE", subtipo_cotizante=d.subtipo_cotizante)
    assert not any("documento" in a for a in avisos)


def test_todos_los_subtipos_del_formulario_estan_mapeados():
    """Los del selector de Afiliados.jsx: si aparece uno nuevo, este test cae."""
    assert set(perfiles.PERFILES) == {"0", "3", "4", "20", "22"}


def test_cada_perfil_se_explica():
    for clave, p in perfiles.PERFILES.items():
        assert p.descripcion, clave
