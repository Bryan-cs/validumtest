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


def revisar(tipo_cotizante: str, servicios) -> list:
    """Choques entre el tipo de cotizante y lo contratado.

    Devuelve una lista de frases, vacía si todo cuadra. Cada frase dice qué
    falta o qué sobra y las dos salidas posibles, porque cualquiera de los dos
    datos puede ser el equivocado: puede faltar el servicio en el formulario, o
    puede estar mal el tipo de cotizante.
    """
    tipo = (tipo_cotizante or "").strip().zfill(2)
    reglas = OBLIGACIONES.get(tipo)
    if not reglas:
        return []

    servicios = list(servicios or [])
    etiqueta = f"tipo de cotizante {tipo} ({nombre_tipo(tipo)})"
    problemas = []

    faltan = [nombre for (sigla, nombre), regla in zip(SUBSISTEMAS, reglas)
              if regla == OBLIGATORIO and not _contrata(servicios, sigla)]
    if faltan:
        problemas.append(
            f"el {etiqueta} está obligado a cotizar a {_y(faltan)}, "
            f"pero eso no está contratado. El operador va a rechazar la planilla: "
            f"agrega el servicio o corrige el tipo de cotizante.")

    sobran = [nombre for (sigla, nombre), regla in zip(SUBSISTEMAS, reglas)
              if regla == NO_APLICA and _contrata(servicios, sigla)]
    if sobran:
        problemas.append(
            f"el {etiqueta} no cotiza a {_y(sobran)}, y está contratado. "
            f"El operador lo va a rechazar: quita el servicio o corrige el tipo "
            f"de cotizante.")

    return problemas


def _y(nombres) -> str:
    """"a, b y c" — para que el aviso se lea como una frase."""
    if len(nombres) == 1:
        return nombres[0]
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]
