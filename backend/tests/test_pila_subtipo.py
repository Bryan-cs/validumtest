# -*- coding: utf-8 -*-
"""Cotizantes obligados a pension que no cotizan a pension.

El caso lo planteo el negocio: hay personas tipo cotizante 01 "Dependiente",
que segun el anexo esta obligado a los cuatro subsistemas, a las que no se les
liquida pension. Con solo el tipo de cotizante eso no se puede expresar y el
operador rechaza la planilla.

La salida es el campo 6, subtipo de cotizante. `fixtures/plano_referencia_
subtipo_04.txt` es una planilla generada por otro sistema para exactamente ese
caso: tipo 01, subtipo 04 "requisitos cumplidos para pension", con la pension
apagada entera y todo lo demas liquidandose normal. Los tests contrastan campo
por campo contra ese archivo.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from services.pila import plano, obligaciones as ob


def _h(token):
    return {"Authorization": f"Bearer {token}"}
from services.pila.liquidacion import liquidar_afiliado


def _referencia():
    ruta = Path(__file__).parent / "fixtures" / "plano_referencia_subtipo_04.txt"
    lineas = [l for l in ruta.read_text(encoding="latin-1").splitlines() if l.strip()]
    return lineas[0], lineas[1]


class _Afiliado:
    """El cotizante del archivo de referencia."""
    id = 1; tipo_doc = "CE"; doc = "1014202750"
    nombre = "CRISTIAN GERMAN SARMIENTO MENDOZA"
    primer_apellido = "SARMIENTO"; segundo_apellido = "MENDOZA"
    primer_nombre = "CRISTIAN"; segundo_nombre = "GERMAN"
    tipo_cotizante = "01"; subtipo_cotizante = "04"
    cod_depto_labor = "11"; cod_municipio_labor = "001"
    cod_eps = "EPS005"; cod_afp = "230301"; cod_ccf = "CCF22"; cod_arl = "14-11"
    clase_riesgo = "1"; tarifa_arl = None; tipo_salario = "F"; centro_trabajo = ""
    servicios = '["EPS","CCF","ARL 1"]'; arl = "14-11"
    novedades = None; fecha_ingreso = None; fecha_afiliacion = None
    estado = "ACTIVO"
    extranjero_no_pension = False; colombiano_exterior = False
    ibc = 1750905; salario_basico = 1750905
    horas_laboradas = None; cotizante_principal_tipo_doc = None
    cotizante_principal_doc = None; fecha_nacimiento = None; sexo = "M"


class _Aportante:
    id = 1; razon_social = "PROTSECOOP"; num_doc = "901824484"; dv = "6"
    cod_depto = "11"; cod_municipio = "001"; clase_riesgo = "1"; cod_arl = "14-11"
    exonerado_parafiscales = True; actividad_economica = "1661401"
    tipo_aportante = "01"; cod_sucursal = "1"; nombre_sucursal = "1"


def _liquidar(**cambios):
    af = _Afiliado()
    for k, v in cambios.items():
        setattr(af, k, v)
    return liquidar_afiliado(af, _Aportante(), 2026, 9)


def _linea(d):
    return plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))


# ─── Contraste contra el archivo de referencia ────────────────────────────────

# Campo 27 es la novedad de licencia remunerada que trae esa persona, y los
# otros dos son su consecuencia: durante la licencia no hay aporte a riesgos.
# Nuestro cotizante no tiene esa novedad, asi que ahi difieren a proposito.
CAMPOS_DE_LA_LICENCIA = {27, 61, 63}


def test_reproducimos_el_archivo_de_referencia_campo_por_campo():
    _, referencia = _referencia()
    nuestra = _linea(_liquidar())
    assert len(nuestra) == len(referencia) == 693
    distintos = {c.numero for c in plano.CAMPOS_TIPO_2
                 if referencia[c.inicio - 1:c.inicio - 1 + c.longitud]
                 != nuestra[c.inicio - 1:c.inicio - 1 + c.longitud]}
    assert distintos == CAMPOS_DE_LA_LICENCIA


@pytest.mark.parametrize("campo,esperado", [
    ("tipo_doc", "CE"),
    ("tipo_cotizante", "01"),
    ("subtipo_cotizante", "04"),
    ("cod_afp", "      "),          # campo 31 vacio
    ("dias_pension", "00"),
    ("ibc_pension", "000000000"),
    ("tarifa_pension", "0.00000"),
    ("cot_pension", "000000000"),
    ("fsp_solidaridad", "000000000"),
    ("fsp_subsistencia", "000000000"),
    ("dias_salud", "30"),
    ("dias_ccf", "30"),
    ("ibc_salud", "001750905"),
    ("tarifa_salud", "0.04000"),
    ("cot_salud", "000070100"),
    ("tarifa_ccf", "0.04000"),
    ("valor_ccf", "000070100"),
    ("ibc_ccf", "001750905"),
])
def test_la_pension_se_apaga_y_lo_demas_no(campo, esperado):
    """Byte por byte contra el archivo que el otro sistema genero."""
    _, referencia = _referencia()
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == campo)
    trozo = slice(c.inicio - 1, c.inicio - 1 + c.longitud)
    assert referencia[trozo] == esperado, "cambio el archivo de referencia"
    assert _linea(_liquidar())[trozo] == esperado


def test_con_ce_y_caja_contratada_el_ibc_es_el_minimo():
    """Los planos ARUS de EPS+CCF y EPS+CCF+ARL cotizan caja sobre 1 SMLMV."""
    c_ibc = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "ibc_ccf")
    c_val = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "valor_ccf")
    linea = _linea(_liquidar())
    assert linea[c_ibc.inicio - 1:c_ibc.inicio - 1 + c_ibc.longitud] == "001750905"
    assert linea[c_val.inicio - 1:c_val.inicio - 1 + c_val.longitud] == "000070100"


def test_sin_subtipo_el_mismo_cotizante_queda_mal():
    """Sin el campo 6 no hay forma de expresarlo: es el punto del cambio."""
    d = _liquidar(subtipo_cotizante="")
    avisos = ob.revisar(d.tipo_cotizante, d.servicios,
                        subtipo_cotizante=d.subtipo_cotizante)
    assert len(avisos) == 1 and "pensión" in avisos[0]


def test_con_subtipo_no_hay_aviso():
    d = _liquidar()
    assert ob.revisar(d.tipo_cotizante, d.servicios,
                      subtipo_cotizante=d.subtipo_cotizante) == []


# ─── Los demas subtipos que levantan la obligacion ────────────────────────────

@pytest.mark.parametrize("subtipo", sorted(ob.SUBTIPOS_SIN_PENSION))
def test_todos_los_subtipos_sin_pension_la_apagan(subtipo):
    d = _liquidar(subtipo_cotizante=subtipo)
    assert int(d.cot_pension) == 0
    assert int(d.ibc_pension) == 0
    assert d.cod_afp == ""


@pytest.mark.parametrize("subtipo", sorted(ob.SUBTIPOS_SIN_SALUD))
def test_los_subtipos_sin_salud_la_apagan(subtipo):
    d = _liquidar(subtipo_cotizante=subtipo, servicios='["EPS","CCF","ARL 1"]')
    assert int(d.cot_salud) == 0


def test_el_subtipo_admite_uno_o_dos_digitos():
    assert int(_liquidar(subtipo_cotizante="4").cot_pension) == 0
    assert int(_liquidar(subtipo_cotizante="04").cot_pension) == 0


def test_un_subtipo_que_no_exime_no_cambia_nada():
    """El 11, conductor de taxi, cotiza a pension como cualquiera."""
    d = _liquidar(subtipo_cotizante="11", servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) > 0


def test_sin_subtipo_y_con_afp_la_pension_se_liquida():
    d = _liquidar(subtipo_cotizante="", servicios='["EPS","AFP","CCF","ARL 1"]')
    assert int(d.cot_pension) > 0
    assert d.cod_afp == "230301"


# ─── Regimen exceptuado: no se apaga, se reporta distinto ─────────────────────

def test_regimen_exceptuado_reporta_dias_e_ibc_con_tarifa_cero():
    """Subtipo 6: el anexo exige campos 36 y 42 llenos y el 46 en cero."""
    d = _liquidar(subtipo_cotizante="06")
    assert int(d.dias_pension) == 30
    assert int(d.ibc_pension) == 1750905
    assert Decimal(d.tarifa_pension) == 0
    assert int(d.cot_pension) == 0


def test_regimen_exceptuado_bajo_cuatro_salarios_deja_el_campo_31_vacio():
    d = _liquidar(subtipo_cotizante="06")     # IBC de 1 SMLMV
    assert d.cod_afp == ""
    assert int(d.fsp_solidaridad) == 0


def test_regimen_exceptuado_desde_cuatro_salarios_paga_el_fondo():
    """Desde 4 SMLMV el campo 31 lleva FSP001 y se aporta al Fondo."""
    d = _liquidar(subtipo_cotizante="06", ibc=8000000, salario_basico=8000000)
    assert d.cod_afp == ob.COD_FONDO_SOLIDARIDAD == "FSP001"
    assert int(d.fsp_solidaridad) > 0


def test_el_codigo_del_fondo_esta_en_el_catalogo():
    """Si no estuviera, la validacion de codigos rechazaria la planilla."""
    from services.pila import catalogos
    assert ob.COD_FONDO_SOLIDARIDAD in catalogos.CATALOGOS["AFP"]


# ─── Los campos PILA se pueden guardar sin romper los que ya estan ────────────

def test_actualizar_sin_mandar_los_campos_pila_no_los_borra(client, admin_token):
    """Un guardado desde el formulario viejo no puede vaciar los codigos."""
    creado = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "PRUEBA SUBTIPO", "doc": "99000111", "tipo_doc": "CC",
        "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
        "tipo_cotizante": "01", "subtipo_cotizante": "04",
        "cod_eps": "EPS005", "cod_ccf": "CCF22",
    })
    assert creado.status_code in (200, 201), creado.text
    id_ = creado.json()["id"]

    # El payload del formulario actual: ni un solo campo PILA.
    r = client.put(f"/afiliados/{id_}", headers=_h(admin_token), json={
        "nombre": "PRUEBA SUBTIPO", "doc": "99000111", "tipo_doc": "CC",
        "servicios": ["EPS", "CCF"], "fecha_afiliacion": "2026-01-01",
    })
    assert r.status_code == 200, r.text

    quedo = client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()
    assert quedo["subtipo_cotizante"] == "04"
    assert quedo["cod_eps"] == "EPS005"


def test_el_subtipo_se_puede_cambiar_por_la_api(client, admin_token):
    creado = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "PRUEBA CAMBIO", "doc": "99000222", "tipo_doc": "CC",
        "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
        "tipo_cotizante": "01", "subtipo_cotizante": "04",
    })
    id_ = creado.json()["id"]
    r = client.put(f"/afiliados/{id_}", headers=_h(admin_token), json={
        "nombre": "PRUEBA CAMBIO", "doc": "99000222", "tipo_doc": "CC",
        "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
        "subtipo_cotizante": "03",
    })
    assert r.status_code == 200, r.text
    assert client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()["subtipo_cotizante"] == "03"


# ─── Un PUT a medias no debe vaciar el resto ──────────────────────────────────
#
# Paso de verdad: un script mando un PUT con cuatro campos para corregir uno
# solo, y dejo en blanco la EPS, el cargo y el IBC de trece personas. Los
# campos PILA se salvaron porque ya tenian esta proteccion; los demas no.

def test_un_put_parcial_conserva_lo_que_no_manda(client, admin_token):
    creado = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "PARCIAL UNO", "doc": "98000111", "tipo_doc": "CC",
        "servicios": ["EPS", "ARL 4"], "fecha_afiliacion": "2026-01-01",
        "eps": "Sanitas", "cargo": "CONDUCTOR", "ibc": 1750905,
        "cod_eps": "EPS005", "clase_riesgo": "4",
    })
    assert creado.status_code in (200, 201), creado.text
    id_ = creado.json()["id"]

    # Lo que hacia el script: cambiar un campo mandando solo lo imprescindible.
    r = client.put(f"/afiliados/{id_}", headers=_h(admin_token), json={
        "nombre": "PARCIAL UNO", "doc": "98000111", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "actividad_economica": "",
    })
    assert r.status_code == 200, r.text

    quedo = client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()
    assert quedo["eps"] == "Sanitas"
    assert quedo["cargo"] == "CONDUCTOR"
    assert float(quedo["ibc"]) == 1750905
    assert quedo["servicios"] == ["EPS", "ARL 4"]
    assert quedo["cod_eps"] == "EPS005"


def test_vaciar_un_campo_a_proposito_sigue_funcionando(client, admin_token):
    """El formulario manda todos los campos: mandar "" es mandarlo."""
    creado = client.post("/afiliados", headers=_h(admin_token), json={
        "nombre": "PARCIAL DOS", "doc": "98000222", "tipo_doc": "CC",
        "servicios": ["EPS"], "fecha_afiliacion": "2026-01-01",
        "eps": "Sanitas", "cargo": "CONDUCTOR",
    })
    id_ = creado.json()["id"]
    r = client.put(f"/afiliados/{id_}", headers=_h(admin_token), json={
        "nombre": "PARCIAL DOS", "doc": "98000222", "tipo_doc": "CC",
        "fecha_afiliacion": "2026-01-01", "servicios": ["EPS"],
        "eps": "", "cargo": "",
    })
    assert r.status_code == 200, r.text
    quedo = client.get(f"/afiliados/{id_}", headers=_h(admin_token)).json()
    assert quedo["eps"] == ""
    assert quedo["cargo"] == ""
