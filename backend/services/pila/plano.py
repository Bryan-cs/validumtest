"""Serializador del archivo plano PILA (archivo tipo 2).

Estructura del Anexo Técnico 2, versión 30 del 24-07-2026. Las posiciones se
extrajeron del PDF y se validaron encadenadas: la numeración de campos va de 1
a N sin huecos, cada campo empieza donde termina el anterior y su longitud
coincide con la diferencia de posiciones. Si esa cadena cierra, el mapa es
consistente con el anexo.

- Registro tipo 1 (encabezado): 22 campos, 359 caracteres.
- Registro tipo 2 (un cotizante): 98 campos, 693 caracteres.

Reglas de relleno: los campos numéricos van alineados a la derecha rellenos con
ceros; los alfanuméricos, a la izquierda rellenos con espacios. Un campo que no
se reporta va en ceros o en blancos según su tipo, nunca vacío: el archivo es de
ancho fijo y el operador lee por posición.
"""
from decimal import Decimal
from typing import NamedTuple


class Campo(NamedTuple):
    numero: int
    inicio: int      # posición 1-based, como la numera el anexo
    longitud: int
    tipo: str        # N numérico | A alfanumérico
    nombre: str


CAMPOS_TIPO_1 = [
    Campo( 1,   1,   2, "N", "tipo_registro"),
    Campo( 2,   3,   1, "N", "modalidad_planilla"),
    Campo( 3,   4,   4, "N", "secuencia"),
    Campo( 4,   8, 200, "A", "razon_social"),
    Campo( 5, 208,   2, "A", "tipo_doc_aportante"),
    Campo( 6, 210,  16, "A", "num_doc_aportante"),
    Campo( 7, 226,   1, "N", "dv_aportante"),
    Campo( 8, 227,   1, "A", "tipo_planilla"),
    Campo( 9, 228,  10, "N", "planilla_asociada"),
    Campo(10, 238,  10, "A", "fecha_planilla_asociada"),
    Campo(11, 248,   1, "A", "forma_presentacion"),
    Campo(12, 249,  10, "A", "cod_sucursal"),
    Campo(13, 259,  40, "A", "nombre_sucursal"),
    Campo(14, 299,   6, "A", "cod_arl"),
    Campo(15, 305,   7, "A", "periodo_pago_otros"),
    Campo(16, 312,   7, "A", "periodo_pago_salud"),
    Campo(17, 319,  10, "N", "numero_planilla"),
    Campo(18, 329,  10, "A", "fecha_pago"),
    Campo(19, 339,   5, "N", "total_cotizantes"),
    Campo(20, 344,  12, "N", "valor_total_nomina"),
    Campo(21, 356,   2, "N", "tipo_aportante"),
    Campo(22, 358,   2, "N", "cod_operador"),
]

CAMPOS_TIPO_2 = [
    Campo( 1,   1,   2, "N", "tipo_registro"),
    Campo( 2,   3,   5, "N", "secuencia"),
    Campo( 3,   8,   2, "A", "tipo_doc"),
    Campo( 4,  10,  16, "A", "doc"),
    Campo( 5,  26,   2, "N", "tipo_cotizante"),
    Campo( 6,  28,   2, "N", "subtipo_cotizante"),
    Campo( 7,  30,   1, "A", "extranjero_no_pension"),
    Campo( 8,  31,   1, "A", "colombiano_exterior"),
    Campo( 9,  32,   2, "A", "cod_depto_labor"),
    Campo(10,  34,   3, "A", "cod_municipio_labor"),
    Campo(11,  37,  20, "A", "primer_apellido"),
    Campo(12,  57,  30, "A", "segundo_apellido"),
    Campo(13,  87,  20, "A", "primer_nombre"),
    Campo(14, 107,  30, "A", "segundo_nombre"),
    Campo(15, 137,   1, "A", "nov_ING"),
    Campo(16, 138,   1, "A", "nov_RET"),
    Campo(17, 139,   1, "A", "nov_TDE"),
    Campo(18, 140,   1, "A", "nov_TAE"),
    Campo(19, 141,   1, "A", "nov_TDP"),
    Campo(20, 142,   1, "A", "nov_TAP"),
    Campo(21, 143,   1, "A", "nov_VSP"),
    Campo(22, 144,   1, "A", "nov_correcciones"),
    Campo(23, 145,   1, "A", "nov_VST"),
    Campo(24, 146,   1, "A", "nov_SLN"),
    Campo(25, 147,   1, "A", "nov_IGE"),
    Campo(26, 148,   1, "A", "nov_LMA"),
    Campo(27, 149,   1, "A", "nov_VAC_LR"),
    Campo(28, 150,   1, "A", "nov_AVP"),
    Campo(29, 151,   1, "A", "nov_VCT"),
    Campo(30, 152,   2, "N", "nov_IRL_dias"),
    Campo(31, 154,   6, "A", "cod_afp"),
    Campo(32, 160,   6, "A", "cod_afp_traslado"),
    Campo(33, 166,   6, "A", "cod_eps"),
    Campo(34, 172,   6, "A", "cod_eps_traslado"),
    Campo(35, 178,   6, "A", "cod_ccf"),
    Campo(36, 184,   2, "N", "dias_pension"),
    Campo(37, 186,   2, "N", "dias_salud"),
    Campo(38, 188,   2, "N", "dias_arl"),
    Campo(39, 190,   2, "N", "dias_ccf"),
    Campo(40, 192,   9, "N", "salario_basico"),
    Campo(41, 201,   1, "A", "tipo_salario"),
    Campo(42, 202,   9, "N", "ibc_pension"),
    Campo(43, 211,   9, "N", "ibc_salud"),
    Campo(44, 220,   9, "N", "ibc_arl"),
    Campo(45, 229,   9, "N", "ibc_ccf"),
    Campo(46, 238,   7, "N", "tarifa_pension"),
    Campo(47, 245,   9, "N", "cot_pension"),
    Campo(48, 254,   9, "N", "aporte_vol_afiliado"),
    Campo(49, 263,   9, "N", "aporte_vol_aportante"),
    Campo(50, 272,   9, "N", "total_pension"),
    Campo(51, 281,   9, "N", "fsp_solidaridad"),
    Campo(52, 290,   9, "N", "fsp_subsistencia"),
    Campo(53, 299,   9, "N", "valor_no_retenido"),
    Campo(54, 308,   7, "N", "tarifa_salud"),
    Campo(55, 315,   9, "N", "cot_salud"),
    Campo(56, 324,   9, "N", "valor_upc_adicional"),
    Campo(57, 333,  15, "A", "autorizacion_incapacidad"),
    Campo(58, 348,   9, "N", "valor_incapacidad"),
    Campo(59, 357,  15, "A", "autorizacion_licencia_mat"),
    Campo(60, 372,   9, "N", "valor_licencia_mat"),
    Campo(61, 381,   9, "N", "tarifa_arl"),
    Campo(62, 390,   9, "N", "centro_trabajo"),
    Campo(63, 399,   9, "N", "cot_arl"),
    Campo(64, 408,   7, "N", "tarifa_ccf"),
    Campo(65, 415,   9, "N", "valor_ccf"),
    Campo(66, 424,   7, "N", "tarifa_sena"),
    Campo(67, 431,   9, "N", "valor_sena"),
    Campo(68, 440,   7, "N", "tarifa_icbf"),
    Campo(69, 447,   9, "N", "valor_icbf"),
    Campo(70, 456,   7, "N", "tarifa_esap"),
    Campo(71, 463,   9, "N", "valor_esap"),
    Campo(72, 472,   7, "N", "tarifa_men"),
    Campo(73, 479,   9, "N", "valor_men"),
    Campo(74, 488,   2, "A", "cotizante_principal_tipo_doc"),
    Campo(75, 490,  16, "A", "cotizante_principal_doc"),
    Campo(76, 506,   1, "A", "exonerado_salud_sena_icbf"),
    Campo(77, 507,   6, "A", "cod_arl_cotizante"),
    Campo(78, 513,   1, "A", "clase_riesgo"),
    Campo(79, 514,   1, "A", "indicador_alto_riesgo"),
    Campo(80, 515,  10, "A", "fecha_ING"),
    Campo(81, 525,  10, "A", "fecha_RET"),
    Campo(82, 535,  10, "A", "fecha_VSP"),
    Campo(83, 545,  10, "A", "fecha_ini_SLN"),
    Campo(84, 555,  10, "A", "fecha_fin_SLN"),
    Campo(85, 565,  10, "A", "fecha_ini_IGE"),
    Campo(86, 575,  10, "A", "fecha_fin_IGE"),
    Campo(87, 585,  10, "A", "fecha_ini_LMA"),
    Campo(88, 595,  10, "A", "fecha_fin_LMA"),
    Campo(89, 605,  10, "A", "fecha_ini_VAC"),
    Campo(90, 615,  10, "A", "fecha_fin_VAC"),
    Campo(91, 625,  10, "A", "fecha_ini_VCT"),
    Campo(92, 635,  10, "A", "fecha_fin_VCT"),
    Campo(93, 645,  10, "A", "fecha_ini_IRL"),
    Campo(94, 655,  10, "A", "fecha_fin_IRL"),
    Campo(95, 665,   9, "N", "ibc_otros_parafiscales"),
    Campo(96, 674,   3, "N", "horas_laboradas"),
    Campo(97, 677,  10, "A", "fecha_radicacion_exterior"),
    Campo(98, 687,   7, "N", "subactividad_economica"),
]

LARGO_TIPO_1 = CAMPOS_TIPO_1[-1].inicio + CAMPOS_TIPO_1[-1].longitud - 1
LARGO_TIPO_2 = CAMPOS_TIPO_2[-1].inicio + CAMPOS_TIPO_2[-1].longitud - 1


def _formatear(campo: Campo, valor) -> str:
    """Un valor en su representación de ancho fijo.

    Los decimales se truncan a entero porque PILA no lleva separador decimal en
    los campos de valor: el redondeo al peso ya lo hizo el motor de liquidación.
    Las tarifas son la excepción y llegan aquí ya formateadas como texto.
    """
    if valor is None:
        valor = "" if campo.tipo == "A" else 0

    if campo.tipo == "N":
        # Las tarifas llegan ya formateadas con punto decimal. El anexo marca
        # esos campos como numericos, pero el operador los espera asi.
        if isinstance(valor, str) and "." in valor:
            if len(valor) != campo.longitud:
                raise ValueError(f"campo {campo.numero} ({campo.nombre}): {valor!r} "
                                 f"no mide {campo.longitud} posiciones")
            return valor
        if isinstance(valor, str):
            valor = valor.strip() or 0
        if isinstance(valor, Decimal):
            valor = int(valor)
        elif isinstance(valor, float):
            valor = int(round(valor))
        texto = str(int(valor))
        if len(texto) > campo.longitud:
            raise ValueError(
                f"campo {campo.numero} ({campo.nombre}): {texto} no cabe en "
                f"{campo.longitud} digitos")
        return texto.rjust(campo.longitud, "0")

    texto = str(valor)
    # Un nombre mas largo que su campo se recorta: el anexo pide el dato
    # truncado, no rechaza el registro por eso.
    return texto[:campo.longitud].ljust(campo.longitud, " ")


def formatear_tarifa(tarifa, longitud: int) -> str:
    """Tarifa como fraccion decimal CON punto, ocupando el campo completo.

    Verificado contra un plano real aceptado por el operador: el 16% de
    pension se escribe "0.16000" en sus 7 posiciones y el 4,35% de riesgos
    laborales, "0.0435000" en sus 9. O sea "0." mas tantos decimales como
    posiciones queden libres. Una tarifa en cero no va en ceros sino en
    "0.00000".

    El anexo marca estos campos como numericos, pero el punto va: los tres
    intentos sin el —con 4, 5 y 6 decimales— los rechazo el operador con
    "Valor invalido para campo".
    """
    valor = Decimal(str(tarifa or 0))
    decimales = longitud - 2          # descontando el "0" y el punto
    texto = f"{valor:.{decimales}f}"
    if len(texto) != longitud:
        raise ValueError(f"la tarifa {valor} no cabe en {longitud} posiciones "
                         f"(quedo como {texto!r})")
    return texto


def _armar(campos, valores, largo_esperado):
    partes = [_formatear(c, valores.get(c.nombre)) for c in campos]
    linea = "".join(partes)
    if len(linea) != largo_esperado:
        raise ValueError(f"el registro quedo de {len(linea)} caracteres, "
                         f"se esperaban {largo_esperado}")
    return linea


def registro_tipo_1(valores: dict) -> str:
    """Encabezado de la planilla."""
    return _armar(CAMPOS_TIPO_1, {"tipo_registro": 1, **valores}, LARGO_TIPO_1)


def registro_tipo_2(valores: dict) -> str:
    """Un cotizante."""
    return _armar(CAMPOS_TIPO_2, {"tipo_registro": 2, **valores}, LARGO_TIPO_2)


def periodos_del_encabezado(periodo_cotizacion: str):
    """Los dos períodos del encabezado: (otros subsistemas, salud).

    El operador avisó: "El período de salud reportado en la liquidación
    (2026-10) es diferente al período de salud a liquidar actualmente
    (2026-09)". Salud lleva el mes que se está liquidando; pensión y los demás
    subsistemas, el mes anterior. El plano de referencia lo confirma: para la
    planilla de agosto reporta 2026-07 en el campo 15 y 2026-08 en el 16.
    """
    anio, mes = int(periodo_cotizacion[:4]), int(periodo_cotizacion[5:7])
    if mes == 1:
        anterior = f"{anio - 1:04d}-12"
    else:
        anterior = f"{anio:04d}-{mes - 1:02d}"
    return anterior, periodo_cotizacion


def datos_sucursal(aportante):
    """Forma de presentación y sucursal del encabezado.

    El anexo permite presentar en forma "U" (única) con la sucursal en blanco,
    pero el operador rechaza el archivo así: "Para la forma de presentación S el
    código de sucursal es obligatorio". El plano de referencia que sí acepta
    usa "S" con la sucursal "01", y eso es lo que se replica. Si el aportante
    tiene su propia sucursal cargada, manda la suya.
    """
    codigo = (getattr(aportante, "cod_sucursal", "") or "").strip() or "01"
    nombre = (getattr(aportante, "nombre_sucursal", "") or "").strip() or codigo
    return "S", codigo, nombre


def valores_desde_detalle(detalle, secuencia: int) -> dict:
    """Traduce un DetalleLiquidado a los campos del registro tipo 2.

    Los campos que no se listan aqui quedan en su relleno por defecto: ceros los
    numericos y blancos los alfanumericos, que es justo lo que el anexo espera
    de una novedad que no se reporta.
    """
    nov = detalle.novedades or {}
    fechas = detalle.fechas_novedades or {}

    return {
        "secuencia": secuencia,
        "tipo_doc": detalle.tipo_doc,
        "doc": detalle.doc,
        "tipo_cotizante": detalle.tipo_cotizante,
        "subtipo_cotizante": detalle.subtipo_cotizante or 0,
        # Campos 7 y 8: marcas, se escriben con X o se dejan en blanco.
        "extranjero_no_pension": "X" if detalle.extranjero_no_pension else "",
        "colombiano_exterior": "X" if detalle.colombiano_exterior else "",
        "cod_depto_labor": detalle.cod_depto_labor,
        "cod_municipio_labor": detalle.cod_municipio_labor,
        "primer_apellido": detalle.primer_apellido,
        "segundo_apellido": detalle.segundo_apellido,
        "primer_nombre": detalle.primer_nombre,
        "segundo_nombre": detalle.segundo_nombre,
        "nov_ING": nov.get("ING", ""),
        "nov_RET": nov.get("RET", ""),
        "nov_VSP": nov.get("VSP", ""),
        "nov_SLN": nov.get("SLN", ""),
        "nov_IGE": nov.get("IGE", ""),
        "nov_LMA": nov.get("LMA", ""),
        "nov_VAC_LR": nov.get("VAC", ""),
        "nov_IRL_dias": nov.get("IRL_dias", 0),
        "cod_afp": detalle.cod_afp,
        "cod_eps": detalle.cod_eps,
        "cod_ccf": detalle.cod_ccf,
        "dias_pension": detalle.dias_pension,
        "dias_salud": detalle.dias_salud,
        "dias_arl": detalle.dias_arl,
        "dias_ccf": detalle.dias_ccf,
        "salario_basico": detalle.salario_basico,
        "tipo_salario": detalle.tipo_salario,
        "ibc_pension": detalle.ibc_pension,
        "ibc_salud": detalle.ibc_salud,
        "ibc_arl": detalle.ibc_arl,
        "ibc_ccf": detalle.ibc_ccf,
        "tarifa_pension": formatear_tarifa(detalle.tarifa_pension, 7),
        "cot_pension": detalle.cot_pension,
        "total_pension": detalle.cot_pension,
        "fsp_solidaridad": detalle.fsp_solidaridad,
        "fsp_subsistencia": detalle.fsp_subsistencia,
        "tarifa_salud": formatear_tarifa(detalle.tarifa_salud, 7),
        "cot_salud": detalle.cot_salud,
        "tarifa_arl": formatear_tarifa(detalle.tarifa_arl, 9),
        "centro_trabajo": detalle.centro_trabajo,
        "cot_arl": detalle.cot_arl,
        "tarifa_ccf": formatear_tarifa(detalle.tarifa_ccf, 7),
        "valor_ccf": detalle.valor_ccf,
        "tarifa_sena": formatear_tarifa(detalle.tarifa_sena, 7),
        "valor_sena": detalle.valor_sena,
        "tarifa_icbf": formatear_tarifa(detalle.tarifa_icbf, 7),
        "valor_icbf": detalle.valor_icbf,
        # ESAP y MEN casi nunca aplican, pero su tarifa va en "0.00000" y no en
        # ceros: es un campo de tarifa y el operador lo lee como tal.
        "tarifa_esap": formatear_tarifa(0, 7),
        "tarifa_men": formatear_tarifa(0, 7),
        "cod_arl_cotizante": detalle.cod_arl,
        "clase_riesgo": detalle.clase_riesgo,
        # El operador rechaza las horas en cero.
        "horas_laboradas": detalle.horas_laboradas,
        "subactividad_economica": detalle.subactividad_economica,
        # El anexo reporta este campo en "S"; con "X" el operador lo rechaza.
        "exonerado_salud_sena_icbf": "S" if detalle.exonerado else "",
        "fecha_ING": fechas.get("ING", ""),
        "fecha_RET": fechas.get("RET", ""),
    }


def generar(aportante, liquidacion, resumen, modalidad: int = 1) -> str:
    """Arma el archivo completo: encabezado y un registro por cotizante.

    Devuelve el texto con saltos CRLF, que es como lo esperan los operadores.
    """
    forma, cod_sucursal, nombre_sucursal = datos_sucursal(aportante)
    periodo_otros, periodo_salud = periodos_del_encabezado(liquidacion.periodo_cotizacion)
    encabezado = registro_tipo_1({
        "modalidad_planilla": modalidad,
        "secuencia": 1,
        "razon_social": aportante.razon_social,
        "tipo_doc_aportante": aportante.tipo_doc or "NI",
        "num_doc_aportante": aportante.num_doc,
        "dv_aportante": aportante.dv or 0,
        "tipo_planilla": liquidacion.tipo_planilla,
        "planilla_asociada": 0,
        "fecha_planilla_asociada": "",
        "forma_presentacion": forma,
        "cod_sucursal": cod_sucursal,
        "nombre_sucursal": nombre_sucursal,
        "cod_arl": aportante.cod_arl or "",
        "periodo_pago_otros": periodo_otros,
        "periodo_pago_salud": periodo_salud,
        "numero_planilla": liquidacion.numero_planilla or 0,
        "fecha_pago": liquidacion.fecha_limite_pago or "",
        "total_cotizantes": resumen.total_cotizantes,
        "valor_total_nomina": int(sum((d.ibc_salud or d.ibc_pension)
                                      for d in resumen.detalles)),
        "tipo_aportante": aportante.tipo_aportante or 1,
        "cod_operador": 0,
    })

    lineas = [encabezado]
    for i, detalle in enumerate(resumen.detalles, start=1):
        lineas.append(registro_tipo_2(valores_desde_detalle(detalle, i)))
    return "\r\n".join(lineas) + "\r\n"
