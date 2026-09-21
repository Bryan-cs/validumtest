"""Parámetros normativos de la liquidación PILA.

Todo lo que cambia por decreto vive aquí: salario mínimo, auxilio de transporte,
tarifas por subsistema y los tramos del Fondo de Solidaridad Pensional. Cuando
el Gobierno expida el decreto del año siguiente se agrega una entrada y nada más
se toca.

El redondeo va en dos pasos y los dos importan: el Anexo Técnico 2 exige
aproximación aritmética al peso —dos decimales, desde .50 sube—, y encima de
eso el operador espera la cotización de cada subsistema aproximada a la
centena superior. Lo segundo no está en la norma; salió del reporte de
validación. Equivocarse hace que los totales no cuadren.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple


class ParametrosAnio(NamedTuple):
    smlmv: Decimal
    auxilio_transporte: Decimal
    decreto: str


# Decretos 1469 y 1470 de 2025 para 2026; 1572 y 1573 de 2024 para 2025.
PARAMETROS_POR_ANIO = {
    2025: ParametrosAnio(Decimal("1423500"), Decimal("200000"), "Decretos 1572 y 1573 de 2024"),
    2026: ParametrosAnio(Decimal("1750905"), Decimal("249095"), "Decretos 1469 y 1470 de 2025"),
}

ANIO_MAS_RECIENTE = max(PARAMETROS_POR_ANIO)

# Tarifas de cotización sobre el IBC.
TARIFA_SALUD = Decimal("0.125")
TARIFA_PENSION = Decimal("0.16")
TARIFA_CCF = Decimal("0.04")
TARIFA_SENA = Decimal("0.02")
TARIFA_ICBF = Decimal("0.03")

# IBC de caja cuando se declara parafiscales sin pagarlos: los planos de ARUS
# que el operador acepta llevan 100, no el salario. Si CCF sí está contratada
# se usa el IBC real (piso de 1 SMLMV).
IBC_CCF_SIN_CONTRATO = Decimal("100")

# Error 256: si hay aporte a caja el código no puede ir vacío. Quien no
# contrata CCF no tiene caja en la ficha; ARUS declara CCF68 en esos planos.
COD_CCF_SIN_CONTRATO = "CCF68"

# La parte patronal de salud es la que exonera el artículo 114-1 del Estatuto
# Tributario; el 4% del trabajador se sigue pagando siempre.
TARIFA_SALUD_PATRONAL = Decimal("0.085")
TARIFA_SALUD_TRABAJADOR = Decimal("0.04")

# Riesgos laborales por clase de riesgo (Decreto 1772 de 1994, tarifas mínimas).
TARIFA_ARL_POR_CLASE = {
    "1": Decimal("0.00522"),
    "2": Decimal("0.01044"),
    "3": Decimal("0.02436"),
    "4": Decimal("0.04350"),
    "5": Decimal("0.06960"),
}

# Topes en número de salarios mínimos.
TOPE_IBC_SMLMV = 25
DIAS_MES_PILA = 30

# Exoneración de parafiscales: aplica a los cotizantes por debajo de este tope.
TOPE_EXONERACION_SMLMV = 10

# Fondo de Solidaridad Pensional (Ley 797 de 2003, art. 8). El primer 1% va
# siempre a la subcuenta de solidaridad; lo que exceda de ese 1% va a la de
# subsistencia. Cada tramo es (limite_inferior_smlmv, limite_superior, tarifa).
# El límite superior None significa "sin tope".
TRAMOS_FSP = [
    (Decimal("4"),  Decimal("16"), Decimal("0.010")),
    (Decimal("16"), Decimal("17"), Decimal("0.012")),
    (Decimal("17"), Decimal("18"), Decimal("0.014")),
    (Decimal("18"), Decimal("19"), Decimal("0.016")),
    (Decimal("19"), Decimal("20"), Decimal("0.018")),
    (Decimal("20"), None,          Decimal("0.020")),
]

TARIFA_FSP_SOLIDARIDAD = Decimal("0.010")


def parametros(anio: int) -> ParametrosAnio:
    """Parámetros del año pedido.

    Si el año todavía no tiene decreto cargado se usan los del más reciente y se
    deja constancia en el log: es preferible liquidar con el valor del año
    anterior —y que se note— a fallar en silencio.
    """
    if anio in PARAMETROS_POR_ANIO:
        return PARAMETROS_POR_ANIO[anio]
    import logging
    logging.getLogger("bbcfile").warning(
        f"PILA: no hay parámetros para {anio}; se usan los de {ANIO_MAS_RECIENTE}")
    return PARAMETROS_POR_ANIO[ANIO_MAS_RECIENTE]


def redondear_peso(valor) -> Decimal:
    """Aproximación aritmética al peso, como la exige el Anexo Técnico 2.

    Aplica a los valores intermedios: el IBC y las bases. La cotización final
    de cada subsistema lleva además `aproximar_aporte`.
    """
    return Decimal(valor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def aproximar_aporte(valor) -> Decimal:
    """Aproxima una cotización a la centena superior.

    Verificado contra el validador del operador, que sobre un IBC de un salario
    mínimo esperaba:

        salud    4%      70.036  ->  70.100
        pensión  16%    280.145  -> 280.200
        riesgos  0,522%   9.140  ->   9.200

    Siempre hacia arriba, nunca al múltiplo más cercano: 70.036 sube a 70.100
    y no baja a 70.000. El anexo solo habla de aproximar al peso, que es el
    paso anterior; esta segunda aproximación no está en la norma y salió del
    reporte de validación.
    """
    entero = Decimal(valor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if entero % 100 == 0:
        return entero
    return (entero // 100 + 1) * 100


def tarifa_fsp(ibc: Decimal, smlmv: Decimal) -> Decimal:
    """Tarifa total del Fondo de Solidaridad Pensional para un IBC dado."""
    if smlmv <= 0:
        return Decimal("0")
    en_smlmv = ibc / smlmv
    for inferior, superior, tarifa in TRAMOS_FSP:
        if en_smlmv >= inferior and (superior is None or en_smlmv < superior):
            return tarifa
    return Decimal("0")


def partir_fsp(ibc: Decimal, smlmv: Decimal):
    """Reparte el aporte al FSP entre sus dos subcuentas.

    El 1% inicial es de solidaridad; el excedente, de subsistencia. Devuelve
    (solidaridad, subsistencia) ya redondeados al peso.
    """
    total = tarifa_fsp(ibc, smlmv)
    if total == 0:
        return Decimal("0"), Decimal("0")
    solidaridad = aproximar_aporte(ibc * TARIFA_FSP_SOLIDARIDAD)
    subsistencia = aproximar_aporte(ibc * (total - TARIFA_FSP_SOLIDARIDAD))
    return solidaridad, subsistencia
