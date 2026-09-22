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


def test_sin_caja_contratada_igual_hay_horas_si_se_declara_parafiscales():
    """EPS + ARL en un dependiente declara caja con IBC 100; las horas van."""
    d = _liquidar("01", servicios='["EPS","AFP","ARL 1"]')
    assert int(d.dias_ccf) == 30
    assert int(d.ibc_ccf) == 100
    assert d.horas_laboradas == 30 * 8


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


# ─── Codigos de administradora vacios ─────────────────────────────────────────
#
# "El codigo de la administradora de Salud no puede estar vacio para el tipo de
# cotizante 01". El operador lo devuelve como error, no como advertencia.

class _Det:
    """Lo que `codigos_faltantes` mira, sea un detalle vivo o uno guardado."""
    def __init__(self, **kw):
        self.dias_salud = self.dias_pension = self.dias_arl = self.dias_ccf = 0
        self.cot_salud = self.cot_pension = self.cot_arl = self.valor_ccf = 0
        self.cod_eps = self.cod_afp = self.cod_ccf = ""
        self.clase_riesgo = "1"
        self.__dict__.update(kw)


def test_falta_el_codigo_de_salud():
    d = _Det(dias_salud=30, cot_salud=70100)
    assert ob.codigos_faltantes(d) == ["salud"]


def test_faltan_varios():
    d = _Det(dias_salud=30, dias_ccf=30)
    assert ob.codigos_faltantes(d) == ["salud", "caja de compensacion familiar"]


def test_con_los_codigos_puestos_no_falta_nada():
    d = _Det(dias_salud=30, dias_ccf=30, cod_eps="EPS008", cod_ccf="CCF24")
    assert ob.codigos_faltantes(d) == []


def test_un_subsistema_que_no_se_liquida_no_pide_codigo():
    """A un cotizante exento de pension se le vacia el codigo a proposito."""
    d = _Det(dias_salud=30, cod_eps="EPS008")
    assert "pensiones" not in ob.codigos_faltantes(d)


def test_un_codigo_de_solo_espacios_cuenta_como_vacio():
    d = _Det(dias_salud=30, cod_eps="   ")
    assert ob.codigos_faltantes(d) == ["salud"]


def test_el_aviso_dice_que_es_error_y_no_advertencia():
    from services.pila.liquidacion import liquidar
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    af = _Afiliado()
    af.subtipo = "0"; af.subtipo_cotizante = ""
    af.servicios = '["EPS"]'; af.cod_eps = ""
    avisos = liquidar([af], _Aportante(), 2026, 9).avisos
    assert any("lo rechaza como error" in a for a in avisos)


# ─── Actividad economica vs clase de riesgo ───────────────────────────────────
#
# "El codigo registrado en el campo de actividad economica para ARL no coincide
# con la clase de riesgo del cotizante. Le sugerimos el codigo 5960901 teniendo
# en cuenta el Decreto 768 de 2022". El primer digito del codigo es la clase.

class _Act:
    def __init__(self, codigo, clase):
        self.subactividad_economica = codigo
        self.clase_riesgo = clase


def test_la_actividad_de_otra_clase_avisa():
    avisos = ob.revisar_actividad(_Act("1661401", "5"))
    assert len(avisos) == 1
    assert "clase de riesgo 1" in avisos[0] and "clase 5" in avisos[0]


def test_cuando_coinciden_no_avisa():
    assert ob.revisar_actividad(_Act("5960901", "5")) == []
    assert ob.revisar_actividad(_Act("1661401", "1")) == []


@pytest.mark.parametrize("codigo,clase", [("", "5"), ("1661401", ""), ("", "")])
def test_sin_datos_no_inventa_avisos(codigo, clase):
    assert ob.revisar_actividad(_Act(codigo, clase)) == []


def test_un_codigo_que_no_empieza_por_digito_se_ignora():
    assert ob.revisar_actividad(_Act("X661401", "5")) == []


# ─── Novedad de ingreso en periodos parciales ─────────────────────────────────

def _con_dias(dias, **cambios):
    """Un afiliado que entra el dia que deja justo esos dias cotizados."""
    from tests.test_pila_subtipo import _Afiliado, _Aportante
    from services.pila.liquidacion import liquidar_afiliado
    af = _Afiliado()
    af.subtipo = "0"; af.subtipo_cotizante = ""
    af.servicios = '["EPS","AFP","CCF","ARL 1"]'
    af.fecha_ingreso = f"2026-09-{31 - dias:02d}" if dias < 30 else "2024-01-15"
    for k, v in cambios.items():
        setattr(af, k, v)
    return liquidar_afiliado(af, _Aportante(), 2026, 9)


@pytest.mark.parametrize("dias", [1, 5, 15, 20, 29])
def test_un_periodo_parcial_siempre_lleva_novedad_de_ingreso(dias):
    d = _con_dias(dias)
    assert d.dias_salud == dias
    assert d.novedades.get("ING") == "X"
    assert d.fechas_novedades.get("ING")


def test_un_mes_completo_no_lleva_novedad():
    d = _con_dias(30)
    assert d.dias_salud == 30
    assert d.novedades.get("ING") is None


def test_la_fecha_sale_de_los_dias_declarados():
    """20 de 30 dias cotizados significa que el primero fue el 11."""
    d = _con_dias(20)
    assert d.fechas_novedades["ING"] == "2026-09-11"


def test_la_novedad_llega_al_archivo():
    d = _con_dias(20)
    linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, 1))
    c = next(x for x in plano.CAMPOS_TIPO_2 if x.nombre == "nov_ING")
    assert linea[c.inicio - 1] == "X"


def test_la_fecha_nunca_cae_fuera_del_mes():
    """PILA cuenta meses de 30 dias, pero la fecha tiene que existir."""
    from services.pila.liquidacion import _garantizar_novedad_de_ingreso
    from services.pila.liquidacion import DetalleLiquidado
    d = DetalleLiquidado(afiliado_id=1, tipo_doc="CC", doc="1", dias_salud=1)
    _garantizar_novedad_de_ingreso(d, 2026, 2)      # febrero tiene 28
    assert d.fechas_novedades["ING"] == "2026-02-28"


def test_no_se_pisa_una_novedad_ya_puesta():
    from services.pila.liquidacion import _garantizar_novedad_de_ingreso
    from services.pila.liquidacion import DetalleLiquidado
    d = DetalleLiquidado(afiliado_id=1, tipo_doc="CC", doc="1", dias_salud=10)
    d.novedades = {"RET": "X"}
    d.fechas_novedades = {"RET": "2026-09-10"}
    _garantizar_novedad_de_ingreso(d, 2026, 9)
    assert "ING" not in d.novedades


# ─── Actividad economica propia del afiliado ──────────────────────────────────

def test_la_actividad_del_afiliado_le_gana_a_la_del_aportante():
    """El CIIU es el de la ficha. El primer dígito queda en la clase reportada."""
    d = _liquidar("01", actividad_economica="5960901")
    assert d.subactividad_economica[1:] == "960901"
    assert d.subactividad_economica[0] == d.clase_riesgo


def test_arl_de_otra_clase_lleva_el_mismo_ciiu_con_su_digito():
    """ARL 4 sobre el CIIU de la empresa no puede salir con un código de clase 1."""
    d = _liquidar("01", servicios='["EPS","CCF","ARL 4"]', clase_riesgo="4")
    assert d.clase_riesgo == "4"
    assert d.subactividad_economica == "4" + _Aportante.actividad_economica[1:]
    assert ob.revisar_actividad(d) == []


def test_sin_actividad_propia_hereda_la_del_aportante():
    d = _liquidar("01", actividad_economica=None)
    assert d.subactividad_economica == _Aportante.actividad_economica


def test_con_la_actividad_propia_correcta_no_hay_aviso():
    d = _liquidar("01", actividad_economica="1960901", clase_riesgo="1")
    assert ob.revisar_actividad(d) == []


# ─── Las dos formas del detalle ───────────────────────────────────────────────
#
# El motor produce un `DetalleLiquidado` y la base guarda un `PlanillaDetalle`,
# y no tienen las mismas columnas. `enviar` revisa el guardado y reventaba con
# "'PlanillaDetalle' object has no attribute 'clase_riesgo'". Los tests no lo
# vieron porque usaban un doble que si tenia el campo.

def test_las_funciones_del_detalle_sirven_para_el_modelo_guardado():
    """Contra el modelo de verdad, no contra un doble que yo controle."""
    import models
    guardado = models.PlanillaDetalle(
        secuencia=1, tipo_doc="CC", doc="1",
        dias_salud=30, cot_salud=70100, dias_ccf=30, valor_ccf=70100,
        cod_eps="", cod_ccf="CCF24",
    )
    assert "EPS" in ob.liquidados(guardado)
    assert ob.codigos_faltantes(guardado) == ["salud"]
    assert ob.revisar_actividad(guardado) == []      # no tiene esos campos


def test_el_modelo_guardado_no_tiene_todas_las_columnas_del_motor():
    """Deja constancia de cuales faltan, para que el dia que se agreguen se vea."""
    import dataclasses, models
    from services.pila.liquidacion import DetalleLiquidado
    columnas = {c.name for c in models.PlanillaDetalle.__table__.columns}
    campos = {f.name for f in dataclasses.fields(DetalleLiquidado)}
    ausentes = {c for c in ("clase_riesgo", "subactividad_economica")
                if c in campos and c not in columnas}
    assert ausentes == {"clase_riesgo", "subactividad_economica"}, (
        "cambio que columnas guarda PlanillaDetalle: revisa que "
        "`liquidados` y `revisar_actividad` sigan leyendolas con getattr")


def test_las_dos_formas_dan_el_mismo_resultado_cuando_tienen_los_datos():
    import models
    d_motor = _liquidar("01")
    guardado = models.PlanillaDetalle(
        secuencia=1, tipo_doc="CC", doc="1",
        dias_salud=d_motor.dias_salud, cot_salud=int(d_motor.cot_salud),
        dias_pension=d_motor.dias_pension, cot_pension=int(d_motor.cot_pension),
        dias_arl=d_motor.dias_arl, cot_arl=int(d_motor.cot_arl),
        dias_ccf=d_motor.dias_ccf, valor_ccf=int(d_motor.valor_ccf),
        cod_eps=d_motor.cod_eps, cod_afp=d_motor.cod_afp, cod_ccf=d_motor.cod_ccf,
    )
    assert ob.codigos_faltantes(guardado) == ob.codigos_faltantes(d_motor)
