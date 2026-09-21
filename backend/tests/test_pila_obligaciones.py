# -*- coding: utf-8 -*-
"""El choque entre el tipo de cotizante y lo contratado.

Estos casos salieron de un rechazo real: un dependiente con solo EPS
contratada subio al operador y volvio con nueve errores que eran uno solo.
"""
import pytest

from services.pila import obligaciones as ob


def test_dependiente_con_solo_eps_avisa_los_tres_que_faltan():
    avisos = ob.revisar("01", ["EPS"])
    assert len(avisos) == 1
    texto = avisos[0]
    for esperado in ("pensión", "riesgos laborales", "caja de compensación familiar"):
        assert esperado in texto
    # Las dos salidas posibles, porque cualquiera de los dos datos puede estar mal.
    assert "agrega el servicio" in texto and "corrige el tipo de cotizante" in texto


def test_dependiente_completo_no_avisa():
    assert ob.revisar("01", ["EPS", "AFP", "ARL 2", "CCF"]) == []


def test_la_arl_se_reconoce_con_la_clase_pegada():
    """`_servicios_afiliado` devuelve "ARL 2", no "ARL"."""
    assert "riesgos" not in " ".join(ob.revisar("01", ["EPS", "AFP", "ARL 5", "CCF"]))


def test_independiente_sin_caja_no_avisa_porque_es_voluntaria():
    assert ob.revisar("03", ["EPS", "AFP"]) == []


def test_independiente_solo_salud_con_pension_contratada_sobra():
    avisos = ob.revisar("42", ["EPS", "AFP"])
    assert len(avisos) == 1
    assert "no cotiza a pensión" in avisos[0]
    assert "quita el servicio" in avisos[0]


def test_tiempo_parcial_no_exige_salud():
    """El 51 cotiza a pension, riesgos y caja; la salud va subsidiada."""
    assert ob.revisar("51", ["AFP", "ARL 1", "CCF"]) == []


def test_tipo_desconocido_no_inventa_reglas():
    """Sin entrada en la tabla no se valida: mejor callar que bloquear de mas."""
    assert ob.revisar("99", []) == []
    assert ob.revisar("", ["EPS"]) == []


def test_el_tipo_llega_con_o_sin_cero_a_la_izquierda():
    assert ob.revisar("1", ["EPS"]) == ob.revisar("01", ["EPS"])


@pytest.mark.parametrize("tipo,reglas", sorted(ob.OBLIGACIONES.items()))
def test_la_tabla_esta_bien_formada(tipo, reglas):
    assert len(tipo) == 2 and tipo.isdigit()
    assert len(reglas) == len(ob.SUBSISTEMAS)
    assert set(reglas) <= {ob.OBLIGATORIO, ob.VOLUNTARIO, ob.NO_APLICA}
    assert tipo in ob.NOMBRES_TIPO


def test_toda_la_tabla_tiene_al_menos_un_subsistema():
    """Un tipo que no cotice a nada no tendria por que estar en una planilla."""
    for tipo, reglas in ob.OBLIGACIONES.items():
        assert ob.NO_APLICA != set(reglas), tipo
        assert any(r != ob.NO_APLICA for r in reglas), tipo


def test_la_frase_enumera_en_castellano():
    assert ob._y(["a"]) == "a"
    assert ob._y(["a", "b"]) == "a y b"
    assert ob._y(["a", "b", "c"]) == "a, b y c"


# ─── Salario básico e IBC son campos distintos ────────────────────────────────

class _Afiliado:
    """Lo mínimo que `liquidar_afiliado` mira, para no depender de la base."""
    id = 1; tipo_doc = "CC"; doc = "52987123"; nombre = "CLAUDIA MARTINEZ"
    primer_apellido = "MARTINEZ"; segundo_apellido = ""
    primer_nombre = "CLAUDIA"; segundo_nombre = ""
    tipo_cotizante = "01"; subtipo_cotizante = ""
    cod_depto_labor = "05"; cod_municipio_labor = "001"
    cod_afp = "230201"; cod_eps = "EPS037"; cod_ccf = "CCF03"; cod_arl = "14-11"
    clase_riesgo = "2"; tipo_salario = "F"; centro_trabajo = ""
    servicios = '["EPS","AFP","CCF","ARL 2"]'
    arl = "14-11"; novedades = None; fecha_ingreso = None; fecha_afiliacion = None
    estado = "ACTIVO"; extranjero_no_pension = False; colombiano_exterior = False
    ibc = None; salario_basico = None; tarifa_arl = None
    extranjero_no_pension = False; colombiano_exterior = False
    horas_laboradas = None; cotizante_principal_tipo_doc = None
    cotizante_principal_doc = None; fecha_nacimiento = None; sexo = "F"


class _Aportante:
    id = 1; razon_social = "X"; num_doc = "901760008"; dv = "7"
    cod_depto = "05"; cod_municipio = "001"; clase_riesgo = "2"
    cod_arl = "14-11"; exonerado_parafiscales = False; actividad_economica = ""
    tipo_aportante = "01"; cod_sucursal = "001"; nombre_sucursal = "X"


def _liquidar(ibc, salario):
    from services.pila.liquidacion import liquidar_afiliado
    af = _Afiliado()
    af.ibc, af.salario_basico = ibc, salario
    return liquidar_afiliado(af, _Aportante(), 2026, 8)


def test_el_salario_basico_no_es_el_ibc():
    """Con IBC individual por debajo del salario, cada campo lleva lo suyo."""
    d = _liquidar(ibc=1750905, salario=4500000)
    assert int(d.salario_basico) == 4500000
    assert int(d.ibc_salud) == 1750905


def test_sin_salario_cargado_el_campo_cae_al_ibc():
    """La mayoría de afiliados viejos no tienen el salario; algo hay que poner."""
    d = _liquidar(ibc=2000000, salario=None)
    assert int(d.salario_basico) == 2000000


def test_sin_ibc_individual_el_salario_manda():
    d = _liquidar(ibc=None, salario=3000000)
    assert int(d.salario_basico) == 3000000
    assert int(d.ibc_salud) == 3000000


# ─── Marcas de los campos 7 y 8 ───────────────────────────────────────────────

def test_extranjero_no_obligado_a_pension_no_reclama_pension():
    """Sigue siendo dependiente, pero la ley no le exige pension."""
    avisos = ob.revisar("01", ["EPS", "ARL 2", "CCF"],
                        extranjero_no_pension=True, tipo_doc="CE")
    assert avisos == []


def test_sin_la_marca_el_mismo_caso_si_reclama_pension():
    avisos = ob.revisar("01", ["EPS", "ARL 2", "CCF"], tipo_doc="CE")
    assert len(avisos) == 1 and "pensión" in avisos[0]


def test_la_marca_de_extranjero_exige_documento_de_extranjero():
    avisos = ob.revisar("01", ["EPS", "ARL 2", "CCF"],
                        extranjero_no_pension=True, tipo_doc="CC")
    assert len(avisos) == 1
    assert "el documento es CC" in avisos[0]
    for doc in ("CE", "PA", "CD", "SC", "PE"):
        assert doc in avisos[0]


@pytest.mark.parametrize("doc", ["CE", "PA", "CD", "SC", "PE"])
def test_los_cinco_documentos_del_anexo_pasan(doc):
    assert ob.revisar("01", ["EPS", "ARL 2", "CCF"],
                      extranjero_no_pension=True, tipo_doc=doc) == []


def test_colombiano_en_el_exterior_no_reclama_salud():
    assert ob.revisar("01", ["AFP", "ARL 2", "CCF"], colombiano_exterior=True) == []


def test_el_motor_apaga_la_pension_y_vacia_el_codigo_de_afp():
    """Campos 31, 36, 42 y 46 al 53 tienen que salir vacios."""
    from services.pila import plano
    af = _Afiliado()
    af.ibc, af.salario_basico = 3000000, 3000000
    af.extranjero_no_pension = True
    af.tipo_doc = "CE"
    d = _liquidar_af(af)
    assert int(d.cot_pension) == 0
    assert int(d.ibc_pension) == 0
    assert d.cod_afp == ""
    assert int(d.fsp_solidaridad) == 0 and int(d.fsp_subsistencia) == 0
    # Y la salud sigue liquidandose: solo se cae la pension.
    assert int(d.cot_salud) > 0

    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    c7 = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "extranjero_no_pension")
    assert linea[c7.inicio - 1] == "X"


def test_colombiano_en_el_exterior_apaga_la_salud():
    af = _Afiliado()
    af.ibc, af.salario_basico = 3000000, 3000000
    af.colombiano_exterior = True
    d = _liquidar_af(af)
    assert int(d.cot_salud) == 0
    assert int(d.cot_pension) > 0


def _liquidar_af(af):
    from services.pila.liquidacion import liquidar_afiliado
    return liquidar_afiliado(af, _Aportante(), 2026, 8)
