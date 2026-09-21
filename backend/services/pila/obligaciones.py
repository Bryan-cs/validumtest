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

    Sirve para las dos formas del detalle: el `DetalleLiquidado` que produce el
    motor y el `PlanillaDetalle` que queda guardado, que no tiene todas sus
    columnas. Por eso los campos se leen con `getattr`.
    """
    def campo(nombre):
        return getattr(detalle, nombre, None) or 0

    presentes = []
    if campo("dias_salud") or campo("cot_salud"):
        presentes.append("EPS")
    if campo("dias_pension") or campo("cot_pension"):
        presentes.append("AFP")
    if campo("dias_arl") or campo("cot_arl"):
        clase = getattr(detalle, "clase_riesgo", "") or ""
        presentes.append(f"ARL {clase}".strip())
    if campo("dias_ccf") or campo("valor_ccf"):
        presentes.append("CCF")
    return presentes


def codigos_faltantes(detalle) -> list:
    """Subsistemas que la planilla declara sin decir a que administradora.

    El operador no lo perdona: "El codigo de la administradora de Salud no
    puede estar vacio para el tipo de cotizante 01". Es un error duro, no una
    advertencia, asi que conviene tratarlo como tal y no dejar que el archivo
    salga.

    Se mira contra lo que la planilla liquida, no contra lo contratado: a un
    cotizante exento de pension se le vacia el codigo de AFP a proposito.
    """
    declara = liquidados(detalle)
    faltan = []
    for sigla, campo, nombre in (("EPS", "cod_eps", "salud"),
                                 ("AFP", "cod_afp", "pensiones"),
                                 ("CCF", "cod_ccf", "caja de compensacion familiar")):
        if _contrata(declara, sigla) and not (getattr(detalle, campo, "") or "").strip():
            faltan.append(nombre)
    return faltan


def revisar_subsistemas_parejos(detalle, tipo_planilla: str = "E") -> list:
    """Salud, riesgos y caja van juntos o no van.

    Lo dijo el validador del operador en cinco mensajes distintos, probando
    combinaciones una a una:

        819  Dias cotizados a riesgos no pueden ser 0
        283  Dias cotizados a salud (30) y riesgos laborales (0) deben ser iguales
        691  Los IBC de salud y riesgos deben ser iguales para el cotizante
        285  Dias cotizados a riesgos y parafiscales deben ser iguales
        820  Dias cotizados a parafiscales no pueden ser 0

    Solo aplica a los tipos de cotizante que deben los tres. La pension es la
    excepcion y por eso se puede apagar sola con el subtipo de cotizante.

    Se avisa aqui porque el operador lo rechaza despues, cuando ya se subio el
    archivo y hay un registro que anular.
    """
    reglas = reglas_de(getattr(detalle, "tipo_cotizante", ""), tipo_planilla)
    if not reglas:
        return []
    salud, _pension, riesgos, caja = reglas
    if not (salud == riesgos == caja == OBLIGATORIO):
        return []

    dias = {"salud": getattr(detalle, "dias_salud", 0) or 0,
            "riesgos laborales": getattr(detalle, "dias_arl", 0) or 0,
            "caja de compensación": getattr(detalle, "dias_ccf", 0) or 0}
    if len(set(dias.values())) == 1 and 0 not in dias.values():
        return []

    faltan = [nombre for nombre, d in dias.items() if not d]
    if faltan:
        return [f"le falta {_y(faltan)}. Para este tipo de cotizante el operador "
                f"exige salud, riesgos y caja con los mismos días: van los tres "
                f"o no va ninguno."]
    detalle_dias = ", ".join(f"{n} {d}" for n, d in dias.items())
    return [f"los días no coinciden entre subsistemas ({detalle_dias}). El "
            f"operador exige que salud, riesgos y caja lleven los mismos."]


def revisar_actividad(detalle) -> list:
    """Si el codigo de actividad economica cuadra con la clase de riesgo.

    El codigo del Decreto 1607 de 2002 lleva la clase de riesgo en su primer
    digito: 1661401 es clase 1 y 5960901 es clase 5. Cuando el cotizante tiene
    una clase distinta a la de la actividad principal del aportante, el campo
    98 queda diciendo otra cosa que el campo 78.

    No se corrige solo. Cambiarle el primer digito produciria un codigo que no
    corresponde a ninguna actividad: hay que elegir la actividad real de esa
    persona, y eso no lo puede adivinar el sistema.
    """
    codigo = str(getattr(detalle, "subactividad_economica", "") or "").strip()
    clase = str(getattr(detalle, "clase_riesgo", "") or "").strip()
    if not codigo or not clase or not codigo[0].isdigit():
        return []
    if codigo[0] == clase:
        return []
    return [f"la actividad economica {codigo} es de clase de riesgo {codigo[0]}, "
            f"y el cotizante esta en clase {clase}. El operador lo avisa y "
            f"sugiere la actividad que corresponda a su clase."]


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


# ── Campos que solo valen para ciertos tipos de cotizante ────────────────────
#
# El anexo no los junta en una tabla: cada regla vive en la fila de su campo o
# en el parrafo de su tipo. Estas cuatro salieron de un rechazo real, donde el
# operador devolvio la lista completa en el texto del error.

# Campo 96. "Es un campo obligatorio para los tipos de cotizante 1, 2, 18, 22,
# 30, 51 y 55" — y para los demas sobra: el operador avisa que hay horas
# reportadas sin aportes a caja.
TIPOS_CON_HORAS = {"01", "02", "18", "22", "30", "51", "55"}

# Campo 76. La lista es del propio operador: "El tipo cotizante 23 no permite
# exoneracion de pago parafiscales, los permitidos son 1, 2, 18, 20, 22, 30,
# 32, 55, 31, 68, 71".
TIPOS_CON_EXONERACION = {"01", "02", "18", "20", "22", "30", "31", "32",
                         "55", "68", "71"}

# Campo 41. El anexo no da la lista, pero si dice, tipo por tipo, cual tiene
# como base "el salario mensual". Son esos: los demas cotizan sobre un IBC
# fijado por norma y el campo no aplica.
TIPOS_CON_TIPO_SALARIO = {"01", "02", "18", "20", "22", "30", "31", "32",
                          "47", "51", "55"}

# Que tipos de cotizante acepta cada tipo de planilla. Tambien del operador:
# "El tipo de cotizante 23 no es valido en el tipo de planilla E. Los tipos de
# cotizante validos son 01, 12, 15, 18, 19, 20, 21, 22, 30, 31, 32, 40, 51, 54,
# 55, 62, 68, 71". Solo esta la E porque es la unica que genera el sistema; sin
# entrada no se valida.
TIPOS_POR_PLANILLA = {
    "E": {"01", "12", "15", "18", "19", "20", "21", "22", "30", "31", "32",
          "40", "51", "54", "55", "62", "68", "71"},
    # La planilla I la trae el anexo con su tabla completa, en la seccion de
    # tipos de planilla. Es la de los aportantes registrados como
    # "I - Independiente", y es donde viven los cotizantes que no tienen las
    # obligaciones de un dependiente:
    #
    #    3  Independiente                              salud y pension
    #   33  Beneficiario del Fondo de Solidaridad      salud y pension
    #   40  Beneficiario de UPC adicional              salud
    #   42  Cotizante pago solo salud (Ley 1250/2008)  salud
    #   43  Pensiones con pago por tercero             pension
    #   56  Prepensionado con aporte voluntario        salud
    #   57  Independiente voluntario a riesgos         riesgos
    #   59  Independiente por prestacion de servicios  salud, pension y riesgos
    "I": {"03", "33", "40", "42", "43", "56", "57", "59"},
    # La planilla Y tambien trae su lista, en los nueve casos que enumera su
    # seccion. El cuarto es el que describe a una cooperativa o asociacion que
    # paga por sus asociados independientes:
    #
    #   "Aportante que sea agremiaciones, asociaciones o congregaciones
    #    religiosas autorizadas por este Ministerio que pagan los aportes de
    #    los trabajadores independientes agremiados o asociados a ellas para
    #    los tipos de cotizantes 16 y 57"
    #
    # Los demas casos traen sus propios tipos: contratistas (59), cesantes
    # (52), concejales y ediles (34, 35, 36, 60), contrato sindical (53),
    # reincorporacion (61) y prestacion humanitaria (63).
    "Y": {"16", "34", "35", "36", "52", "53", "57", "59", "60", "61", "63"},
}


# Lo que cambia dentro de una planilla concreta. La planilla Y la define el
# anexo asi: "es obligatorio el aporte al Sistema General de Riesgos Laborales
# y opcional efectuar en nombre de su contratista, los aportes a los Sistemas
# Generales de Seguridad Social en Salud y Pension, asi como tambien los
# aportes a cajas de compensacion familiar... caso en el cual el aportante
# debera reportar el tipo de cotizante 59".
#
# O sea que el 59, que fuera de aqui tiene salud y pension obligatorias, en la
# planilla Y solo debe riesgos. Sin esto el sistema le reclamaria aportes que
# el aportante no tiene por que hacer.
OBLIGACIONES_POR_PLANILLA = {
    "Y": {"59": ("V", "V", "O", "V")},
}


def reglas_de(tipo_cotizante, tipo_planilla: str = "") -> tuple:
    """Las obligaciones de un tipo de cotizante dentro de una planilla.

    Devuelve None cuando el tipo no esta en la tabla, que es la forma de decir
    "no se valida": inventar una regla bloquearia planillas correctas.
    """
    tipo = _tipo(tipo_cotizante)
    planilla = (tipo_planilla or "").strip().upper()
    propias = OBLIGACIONES_POR_PLANILLA.get(planilla, {})
    return propias.get(tipo) or OBLIGACIONES.get(tipo)


def admite_horas(tipo_cotizante) -> bool:
    return _tipo(tipo_cotizante) in TIPOS_CON_HORAS


def admite_exoneracion(tipo_cotizante) -> bool:
    return _tipo(tipo_cotizante) in TIPOS_CON_EXONERACION


def admite_tipo_salario(tipo_cotizante) -> bool:
    return _tipo(tipo_cotizante) in TIPOS_CON_TIPO_SALARIO


def _tipo(tipo_cotizante) -> str:
    return str(tipo_cotizante or "").strip().zfill(2)


def revisar_planilla(tipo_cotizante, tipo_planilla: str) -> list:
    """Si ese tipo de cotizante cabe en ese tipo de planilla."""
    validos = TIPOS_POR_PLANILLA.get((tipo_planilla or "").strip().upper())
    tipo = _tipo(tipo_cotizante)
    if not validos or tipo in validos:
        return []
    return [f"el tipo de cotizante {tipo} ({nombre_tipo(tipo)}) no se puede "
            f"reportar en una planilla tipo {tipo_planilla}. El operador la va "
            f"a rechazar: corrige el tipo de cotizante."]


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


# Documentos que se aceptan con la marca del campo 7. El anexo lista cinco en
# la sección 2.1.2.3.3; el operador acepta dos más y lo dice en el texto del
# rechazo: "solo son permitidos los tipos de documentos PA, CE, CD, SC, PE, PT
# y PC". Con cédula de ciudadanía la marca no tiene sentido y la rechaza.
DOCS_EXTRANJERO = ("CE", "PA", "CD", "SC", "PE", "PT", "PC")


def revisar(tipo_cotizante: str, servicios, extranjero_no_pension: bool = False,
            colombiano_exterior: bool = False, tipo_doc: str = "",
            subtipo_cotizante: str = "", tipo_planilla: str = "") -> list:
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
    reglas = reglas_de(tipo, tipo_planilla)
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
