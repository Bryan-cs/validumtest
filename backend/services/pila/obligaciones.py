# -*- coding: utf-8 -*-
"""A qué subsistemas obliga cada tipo de cotizante.

El motor liquida según los servicios contratados en el formulario, que es lo
que pidió el negocio. Pero el operador valida otra cosa: que lo liquidado
cubra lo que el tipo de cotizante exige. Un dependiente al que solo se le
contrató EPS sale del motor con pensión, riesgos y caja en cero, y ARUS lo
devuelve con nueve errores que en realidad son uno.

Esta tabla existe para decir eso antes, en la previsualización, donde todavía
se puede corregir. No cambia la liquidación: solo avisa.

Fuente: Anexo Técnico 2, sección 2.1.2.3.1 "Campo 5 - Tipo de cotizante",
donde cada tipo trae su propio párrafo de obligaciones.

  "O" obligatorio   el operador lo exige; si falta, rechaza
  "V" voluntario    se puede o no; nunca es error
  "N" no aplica     el tipo no cotiza a ese subsistema; mandarlo es error

Los tipos cuyo párrafo no deja clara la obligación quedan fuera a propósito:
sin entrada no se valida nada, que es mejor que inventar una regla y bloquear
una planilla correcta. SENA e ICBF no están en la tabla porque no son
servicios que el cliente contrate: el motor los deduce de la exoneración.
"""

OBLIGATORIO, VOLUNTARIO, NO_APLICA = "O", "V", "N"

# tipo cotizante -> (salud, pension, riesgos, caja)
OBLIGACIONES = {
    "01": ("O", "O", "O", "O"),  # Dependiente
    "02": ("O", "O", "O", "O"),  # Servicio doméstico
    "03": ("O", "O", "N", "V"),  # Independiente
    "04": ("O", "V", "N", "V"),  # Madre sustituta
    "12": ("O", "N", "N", "N"),  # Aprendiz en etapa lectiva
    "16": ("O", "O", "V", "V"),  # Independiente agremiado o asociado
    "18": ("O", "O", "O", "O"),  # Servidor público sin tope de IBC
    "19": ("O", "N", "O", "N"),  # Aprendiz en etapa productiva
    "20": ("O", "O", "O", "N"),  # Estudiante Ley 789 de 2002
    "21": ("O", "N", "O", "N"),  # Estudiante de postgrado en salud
    "22": ("O", "O", "O", "O"),  # Profesor de establecimiento particular
    "23": ("N", "N", "O", "N"),  # Estudiante aporte solo riesgos
    "30": ("O", "O", "O", "O"),  # Dependiente de régimen especial o de excepción
    "31": ("O", "O", "O", "O"),  # Cooperado de CTA
    "32": ("V", "V", "V", "V"),  # Carrera diplomática o consular
    "33": ("O", "O", "V", "V"),  # Beneficiario del Fondo de Solidaridad Pensional
    "35": ("O", "O", "O", "V"),  # Concejal sin póliza de salud
    "36": ("O", "O", "O", "V"),  # Concejal o edil beneficiario del FSP
    "42": ("O", "N", "N", "N"),  # Independiente pago solo salud
    "43": ("N", "O", "N", "N"),  # Pensiones con pago por tercero
    "47": ("O", "O", "N", "O"),  # Dependiente de entidad beneficiaria del SGP
    "51": ("N", "O", "O", "O"),  # Trabajador de tiempo parcial
    "52": ("O", "O", "N", "N"),  # Beneficiario del mecanismo de protección al cesante
    "56": ("V", "N", "N", "N"),  # Prepensionado con aporte voluntario en salud
    "57": ("N", "N", "O", "N"),  # Independiente voluntario a riesgos laborales
    "59": ("O", "O", "O", "V"),  # Independiente con contrato de prestación de servicios
    "63": ("N", "O", "O", "N"),  # Beneficiario de prestación humanitaria
}

# El orden de la tupla, con el nombre del servicio que lo representa en el
# formulario y el nombre que usa el operador en sus mensajes.
SUBSISTEMAS = (
    ("EPS", "salud"),
    ("AFP", "pensión"),
    ("ARL", "riesgos laborales"),
    ("CCF", "caja de compensación familiar"),
)

NOMBRES_TIPO = {
    "01": "Dependiente", "02": "Servicio doméstico", "03": "Independiente",
    "04": "Madre sustituta", "12": "Aprendiz en etapa lectiva",
    "16": "Independiente agremiado", "18": "Servidor público sin tope de IBC",
    "19": "Aprendiz en etapa productiva", "20": "Estudiante Ley 789",
    "21": "Estudiante de postgrado en salud", "22": "Profesor de establecimiento particular",
    "23": "Estudiante aporte solo riesgos", "30": "Dependiente de régimen especial",
    "31": "Cooperado de CTA", "32": "Carrera diplomática o consular",
    "33": "Beneficiario del FSP", "35": "Concejal sin póliza de salud",
    "36": "Concejal o edil beneficiario del FSP", "42": "Independiente pago solo salud",
    "43": "Pensiones con pago por tercero", "47": "Dependiente de entidad beneficiaria del SGP",
    "51": "Trabajador de tiempo parcial", "52": "Beneficiario del mecanismo de protección al cesante",
    "56": "Prepensionado con aporte voluntario en salud",
    "57": "Independiente voluntario a riesgos", "59": "Independiente por prestación de servicios",
    "63": "Beneficiario de prestación humanitaria",
}


def liquidados(detalle) -> list:
    """Los subsistemas que el archivo va a declarar.

    No es lo mismo que lo contratado. Alguien del subtipo 20 no tiene la
    pensión contratada y aun así se le liquida, porque está obligada; alguien
    del subtipo 4 la tiene y no se le liquida, porque está exonerada. El
    operador valida el archivo, no el formulario, así que lo que hay que
    revisar es esto.

    El régimen exceptuado reporta días e IBC de pensión con tarifa cero: eso
    cuenta como declarar el subsistema, y por eso se mira el día y no el valor.
    """
    presentes = []
    if detalle.dias_salud or detalle.cot_salud:
        presentes.append("EPS")
    if detalle.dias_pension or detalle.cot_pension:
        presentes.append("AFP")
    if detalle.dias_arl or detalle.cot_arl:
        presentes.append(f"ARL {detalle.clase_riesgo or ''}".strip())
    if detalle.dias_ccf or detalle.valor_ccf:
        presentes.append("CCF")
    return presentes


def _contrata(servicios, sigla: str) -> bool:
    """Si el afiliado tiene contratado ese subsistema.

    ARL llega como "ARL 1".."ARL 5" porque la clase de riesgo va pegada.
    """
    if sigla == "ARL":
        return any(s.startswith("ARL") for s in servicios)
    return sigla in servicios


def nombre_tipo(tipo_cotizante: str) -> str:
    tipo = (tipo_cotizante or "").strip().zfill(2)
    return NOMBRES_TIPO.get(tipo, f"tipo {tipo}")


# ── Subtipos de cotizante (campo 6) ───────────────────────────────────────────
#
# El subtipo no reemplaza al tipo: lo matiza. Alguien sigue siendo tipo 01
# "Dependiente", con todo lo que eso obliga, y el subtipo levanta una de esas
# obligaciones por una razón personal suya —ya se pensionó, ya cumplió los
# requisitos, ya le devolvieron los saldos—. Sin esto no hay forma de liquidar
# a un dependiente que no cotiza a pensión sin que el operador lo rechace.
# Sección 2.1.2.3.2 del anexo. No existen los subtipos 7 ni 8.
SUBTIPOS_SIN_PENSION = {
    "01",   # Dependiente pensionado por vejez, jubilación o invalidez activo
    "02",   # Independiente pensionado activo
    "03",   # No obligado a cotización a pensiones por edad
    "04",   # Requisitos cumplidos para pensión o indemnización sustitutiva
    "05",   # Indemnización sustitutiva o devolución de saldos reconocida
    "09",   # Pensionado con mesada igual o superior a 25 SMLMV
    "12",   # Conductor de taxi no obligado a cotizar a pensión
}

SUBTIPOS_SIN_SALUD = {
    "09",   # Pensionado con mesada >= 25 SMLMV: no aporta ni a pensión ni a salud
    "10",   # Residente en el exterior
}

# El régimen exceptuado es distinto de los demás: tampoco aporta a pensión,
# pero el anexo exige reportar los días y el IBC de pensión con tarifa 0, y
# pagar el Fondo de Solidaridad Pensional cuando el IBC llega a 4 SMLMV. Por
# eso no está en SUBTIPOS_SIN_PENSION: no se apaga, se reporta distinto.
SUBTIPO_REGIMEN_EXCEPTUADO = "06"

COD_FONDO_SOLIDARIDAD = "FSP001"


def normalizar_subtipo(subtipo) -> str:
    """"4" y "04" son el mismo subtipo; "" y "00" son ninguno."""
    s = str(subtipo or "").strip()
    if not s or s == "0":
        return ""
    s = s.zfill(2)
    return "" if s == "00" else s


def exenciones(subtipo, extranjero_no_pension: bool = False,
               colombiano_exterior: bool = False) -> set:
    """Qué subsistemas quedan exentos para este cotizante.

    Devuelve un subconjunto de {"pension", "salud"}. Junta las dos fuentes de
    exención que existen: el subtipo de cotizante (campo 6) y las marcas de
    los campos 7 y 8.
    """
    sub = normalizar_subtipo(subtipo)
    exentos = set()
    if sub in SUBTIPOS_SIN_PENSION:
        exentos.add("pension")
    if sub in SUBTIPOS_SIN_SALUD:
        exentos.add("salud")
    if extranjero_no_pension:
        exentos.add("pension")
    if colombiano_exterior:
        exentos.add("salud")
    return exentos


def es_regimen_exceptuado(subtipo) -> bool:
    return normalizar_subtipo(subtipo) == SUBTIPO_REGIMEN_EXCEPTUADO


# Documentos que el anexo acepta para un extranjero no obligado a pensión
# (sección 2.1.2.3.3). Con cédula de ciudadanía la marca no tiene sentido.
DOCS_EXTRANJERO = ("CE", "PA", "CD", "SC", "PE")


def revisar(tipo_cotizante: str, servicios, extranjero_no_pension: bool = False,
            colombiano_exterior: bool = False, tipo_doc: str = "",
            subtipo_cotizante: str = "") -> list:
    """Choques entre el tipo de cotizante y lo contratado.

    Devuelve una lista de frases, vacía si todo cuadra. Cada frase dice qué
    falta o qué sobra y las dos salidas posibles, porque cualquiera de los dos
    datos puede ser el equivocado: puede faltar el servicio en el formulario, o
    puede estar mal el tipo de cotizante.

    Las marcas de los campos 7 y 8 levantan la obligación que corresponda: un
    extranjero no obligado a cotizar a pensiones sigue siendo un dependiente,
    pero reclamarle pensión sería reclamar algo que la ley no le exige. Igual
    con la salud del colombiano en el exterior.
    """
    tipo = (tipo_cotizante or "").strip().zfill(2)
    reglas = OBLIGACIONES.get(tipo)
    if not reglas:
        return []

    exentos = exenciones(subtipo_cotizante, extranjero_no_pension, colombiano_exterior)
    if exentos or es_regimen_exceptuado(subtipo_cotizante):
        reglas = list(reglas)
        if "salud" in exentos:
            reglas[0] = NO_APLICA
        if "pension" in exentos or es_regimen_exceptuado(subtipo_cotizante):
            reglas[1] = NO_APLICA

    servicios = list(servicios or [])
    etiqueta = f"tipo de cotizante {tipo} ({nombre_tipo(tipo)})"
    problemas = []

    faltan = [nombre for (sigla, nombre), regla in zip(SUBSISTEMAS, reglas)
              if regla == OBLIGATORIO and not _contrata(servicios, sigla)]
    if faltan:
        problemas.append(
            f"el {etiqueta} está obligado a cotizar a {_y(faltan)}, "
            f"y la planilla no lo está liquidando. El operador la va a rechazar: "
            f"revisa los servicios contratados, el subtipo o el tipo de cotizante.")

    # Lo que el subtipo exime no "sobra": alguien pensionado puede seguir
    # teniendo la AFP en el formulario y no por eso hay un dato mal puesto.
    eximidos = {"salud": "EPS", "pension": "AFP"}
    siglas_exentas = {eximidos[e] for e in exentos if e in eximidos}
    sobran = [nombre for (sigla, nombre), regla in zip(SUBSISTEMAS, reglas)
              if regla == NO_APLICA and _contrata(servicios, sigla)
              and sigla not in siglas_exentas]
    if sobran:
        problemas.append(
            f"el {etiqueta} no cotiza a {_y(sobran)}, y la planilla lo está "
            f"liquidando. El operador la va a rechazar: revisa los servicios "
            f"contratados o el tipo de cotizante.")

    # La marca del campo 7 solo vale con documento de extranjero; el operador
    # rechaza la combinación con CC. Como el tipo de documento del plano se
    # puede cambiar al descargar, se revisa el que se vaya a usar.
    doc = (tipo_doc or "").strip().upper()
    if extranjero_no_pension and doc and doc not in DOCS_EXTRANJERO:
        problemas.append(
            f"está marcado como extranjero no obligado a cotizar a pensiones, "
            f"pero el documento es {doc}. El anexo solo acepta esa marca con "
            f"{_y(list(DOCS_EXTRANJERO))}.")

    return problemas


def _y(nombres) -> str:
    """"a, b y c" — para que el aviso se lea como una frase."""
    if len(nombres) == 1:
        return nombres[0]
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]
