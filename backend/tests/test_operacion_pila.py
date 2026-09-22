"""Cierre, rechazos y el porqué del monto. No toca la red ni el operador."""
from types import SimpleNamespace

from services.pila.operacion import (
    accion_de_avisos, accion_rechazo, explicar_monto, mismo_nombre, nivel_de_avisos,
)


def test_el_codigo_faltante_es_rojo_y_la_caja_en_100_no():
    rojo = "CC 1: la planilla liquida salud pero no tiene el código de la administradora. El operador lo rechaza como error"
    amarillo = "Caja con IBC 100: no hay caja contratada. Es la declaración mínima y no bloquea el envío."
    assert nivel_de_avisos([rojo]) == "rojo"
    assert nivel_de_avisos([amarillo]) == "amarillo"
    assert nivel_de_avisos([]) == "listo"
    assert "no bloquea" in accion_de_avisos([amarillo], "amarillo").lower() or "100" in accion_de_avisos([amarillo], "amarillo")


def test_el_rechazo_de_actividad_pide_anular():
    texto = accion_rechazo("El código de la actividad económica no coincide con el Decreto 768 de 2022")
    assert "Anula" in texto


def test_la_sucursal_no_se_arregla_por_la_api():
    assert "portal" in accion_rechazo("Sucursal no asociada").lower()


def test_sanitas_largo_es_la_misma_eps():
    assert mismo_nombre("EPS", "Sanitas", "ENTIDAD PROMOTORA DE SALUD SANITAS S.A.S.")


def test_el_porque_distingue_exoneracion_y_caja_minima():
    linea = " " * 512 + "4" + " " * 173 + "4661401"
    d = SimpleNamespace(
        ibc_salud=1750905, tarifa_salud="0.12500", cot_pension=280200,
        cot_arl=76200, tarifa_arl="0.04350", valor_ccf=100, valor_sena=35100,
        valor_icbf=52600, ibc_ccf=100, cod_ccf="CCF68", linea_plana=linea,
    )
    notas = " ".join(explicar_monto(d, exonerado_hoy=True))
    assert "12,5%" in notas
    assert "exoneración activa" in notas
    assert "IBC 100" in notas
    assert "4661401" in notas
