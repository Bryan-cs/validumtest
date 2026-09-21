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


def test_el_22_sale_sin_pension_por_la_marca_del_campo_7():
    """Es extranjera de verdad: su tipo de cotizante exigiria pension y la ley no."""
    d = _liquidar("22")
    assert d.extranjero_no_pension is True
    assert int(d.cot_pension) == 0
    assert d.cod_afp == ""


def test_el_22_no_cotiza_pension_ni_teniendola_contratada():
    d = _liquidar("22", servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) == 0


@pytest.mark.parametrize("subtipo", ["20", "22"])
def test_los_dos_grupos_de_extranjeria_no_cotizan_pension(subtipo):
    """Ninguno cotiza pension, pero por mecanismos distintos."""
    d = _liquidar(subtipo, servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) == 0
    assert d.cod_afp == ""


def test_el_20_usa_el_subtipo_de_cotizante_04():
    """Medido contra el validador del operador, una variable a la vez.

    Con el campo 7 y subtipo 00, los mismos datos sin caja devuelven "dias
    cotizados a riesgos y parafiscales deben ser iguales". Con subtipo 04 y el
    campo 7 en blanco, pasan sin un error. El campo 7 exime solo de pension;
    el 04 es el que permite liquidar sin caja.
    """
    d = _liquidar("20", servicios='["EPS","ARL 1"]')
    assert d.subtipo_cotizante == "04"
    assert d.extranjero_no_pension is False


def test_el_22_conserva_la_marca_del_campo_7():
    """Es gente con documento de extranjeria de verdad: la marca los describe."""
    d = _liquidar("22", servicios='["EPS","ARL 1"]')
    assert d.extranjero_no_pension is True


@pytest.mark.parametrize("subtipo", ["20", "22"])
def test_los_dos_salen_con_cedula_de_extranjeria(subtipo):
    assert perfiles.documento_sugerido(subtipo, "CC") == "CE"


def test_solo_el_22_sale_con_cedula_de_extranjeria():
    assert perfiles.documento_sugerido("22", "CC") == "CE"


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


# ─── El documento lo decide el servidor, no quien llame ───────────────────────
#
# Un envio salio con cedula de ciudadania y el operador lo rechazo: "El
# cotizante CC1017234567 no puede ser marcado como extranjero no obligado a
# cotizar pensiones". El frontend mandaba el documento correcto pero el envio
# no dependia de eso, y no debe depender.

def test_una_cedula_de_ciudadania_no_sirve_con_la_marca():
    """Solo el 22 pide documento de extranjeria, y solo si no lo tiene ya."""
    assert perfiles.documento_sugerido("22", "CC") == "CE"


def test_la_tarjeta_de_identidad_tampoco():
    assert perfiles.documento_sugerido("22", "TI") == "CE"


@pytest.mark.parametrize("doc", ["CE", "PA", "CD", "SC", "PE", "PT", "PC"])
def test_un_documento_que_el_operador_acepta_se_respeta(doc):
    """No se pisa el documento real de alguien por poner CE porque si."""
    assert perfiles.documento_sugerido("22", doc) == ""


def test_la_lista_es_la_que_devolvio_el_operador():
    """"solo son permitidos PA, CE, CD, SC, PE, PT y PC" — dos mas que el anexo."""
    assert set(ob.DOCS_EXTRANJERO) == {"CE", "PA", "CD", "SC", "PE", "PT", "PC"}


def test_los_documentos_aceptados_se_pueden_pedir_en_el_plano():
    """De nada sirve aceptarlos si el endpoint del plano los rechaza."""
    from routers.liquidacion import TIPOS_DOC_COTIZANTE
    assert set(ob.DOCS_EXTRANJERO) <= TIPOS_DOC_COTIZANTE


# ─── Regla del negocio: toda persona lleva salud ──────────────────────────────
#
# Aqui no se manejan afiliaciones de solo riesgos ni de solo pension. Una ficha
# sin EPS no es un caso valido, es un dato a medio llenar.

def test_sin_eps_contratada_se_avisa():
    avisos = perfiles.revisar_salud_contratada(["ARL 4"])
    assert len(avisos) == 1
    assert "toda persona lleva EPS" in avisos[0]


@pytest.mark.parametrize("servicios", [
    ["EPS"],
    ["EPS", "ARL 4"],
    ["EPS", "AFP", "CCF", "ARL 1"],
])
def test_con_eps_no_se_avisa(servicios):
    assert perfiles.revisar_salud_contratada(servicios) == []


def test_solo_pension_tampoco_vale():
    assert perfiles.revisar_salud_contratada(["AFP"]) != []


def test_sin_nada_contratado_tambien_avisa():
    assert perfiles.revisar_salud_contratada([]) != []
    assert perfiles.revisar_salud_contratada(None) != []


def test_el_aviso_llega_al_resumen():
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "0"; af.subtipo_cotizante = ""
    af.servicios = '["ARL 4"]'; af.clase_riesgo = "4"
    avisos = liquidar([af], _Aportante(), 2026, 9).avisos
    assert any("toda persona lleva EPS" in a for a in avisos)
