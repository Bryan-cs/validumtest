"""
Generador de archivo PILA (Planilla Integrada de Liquidación de Aportes).
Formato tipo E (Empleadores) — Resolución UGPP 2388/2016 + mod 728/2023.

IMPORTANTE: Este generador es un borrador funcional. Validar contra el sistema
PILA oficial o ADAX antes de enviar a los fondos.
"""

# ──────────────────────────────────────────────────────────────────────────────
# TABLAS DE CÓDIGOS PILA (fuente: UGPP)
# ──────────────────────────────────────────────────────────────────────────────

# EPS: normalizar a mayúsculas sin tildes para comparar
EPS_CODES = {
    "SALUD TOTAL": "EPS002",
    "SANITAS": "EPS005",
    "COMPENSAR": "EPS008",
    "CRUZ BLANCA": "EPS009",
    "SURA": "EPS010",
    "FAMISANAR": "EPS016",
    "NUEVA EPS": "EPS017",
    "CAFESALUD": "EPS012",
    "MEDIMAS": "EPS012",
    "ALIANSALUD": "EPS001",
    "COOSALUD": "EPS037",
    "SAVIA SALUD": "EPS037",
    "MUTUAL SER": "EPS040",
    "COMFENALCO VALLE": "CCFC55",
    "COMFENALCO ANTIOQUIA": "CCFC04",
    "COMFAMILIAR HUILA": "CCFC06",
    "COMFAMILIAR RISARALDA": "CCFC02",
    "COLSANITAS": "EPS018",
    "CAPITAL SALUD": "EPS033",
    "EMSSANAR": "EPS041",
    "MAGISTERIO": "EPS023",
    "ECOOPSOS": "EPS047",
    "SURAMERICANA": "EPS010",
    "EPS SURA": "EPS010",
    "SANITAS EPS": "EPS005",
    "NOVA EPS": "EPS017",
}

AFP_CODES = {
    "PROTECCION": "230201",
    "PORVENIR": "230301",
    "COLFONDOS": "231001",
    "SKANDIA": "231201",
    "OLD MUTUAL": "231201",
    "COLPENSIONES": "240101",
    "FONDO NACIONAL DEL AHORRO": "240201",
    "FNA": "240201",
}

CCF_CODES = {
    "COMPENSAR": "CCF24",
    "COLSUBSIDIO": "CCF22",
    "CAFAM": "CCF21",
    "COMFAMILIAR HUILA": "CCF06",
    "COMFENALCO ANTIOQUIA": "CCF14",
    "COMFAMA": "CCF23",
    "COMFAMILIAR RISARALDA": "CCF02",
    "COMFENALCO VALLE": "CCF55",
    "COMFAMILIAR ATLANTICO": "CCF04",
    "COMBARRANQUILLA": "CCF04",
    "CAJACOPI": "CCF05",
    "COMFAMILIAR CARTAGENA": "CCF07",
    "COMFAMILIAR BOLIVAR": "CCF07",
    "COMFAMILIAR CAMACOL": "CCF08",
    "COMFANDI": "CCF09",
    "COMFENALCO QUINDIO": "CCF10",
    "COMFAMILIAR NARIÑO": "CCF11",
    "COMFACAUCA": "CCF12",
    "COMFAMILIAR CUNDINAMARCA": "CCF13",
    "COMFAMILIAR TOLIMA": "CCF15",
    "COMFAMILIAR SANTANDER": "CCF16",
    "COMFANORTE": "CCF17",
    "COMFACOR": "CCF18",
    "COMFASUCRE": "CCF19",
    "CAJASAN": "CCF20",
    "COMFAJER": "CCF25",
    "COMFACUNDI": "CCF13",
}

# ARL: código PILA + tasa mínima por clase de riesgo
# El código ARL va en el TIPO 01 (cabecera, por empresa), no en tipo 02
ARL_CODES = {
    "SURA": ("14-28", 0.00522),
    "ARL SURA": ("14-28", 0.00522),
    "AXA COLPATRIA": ("14-25", 0.00522),
    "COLPATRIA": ("14-25", 0.00522),
    "LIBERTY": ("14-18", 0.00522),
    "LIBERTY SEGUROS": ("14-18", 0.00522),
    "POSITIVA": ("14-11", 0.00522),
    "POSITIVA COMPAÑIA DE SEGUROS": ("14-11", 0.00522),
    "BOLIVAR": ("14-04", 0.00522),
    "SEGUROS BOLIVAR": ("14-04", 0.00522),
    "EQUIDAD": ("14-44", 0.00522),
    "LA EQUIDAD": ("14-44", 0.00522),
    "MAPFRE": ("14-36", 0.00522),
    "QBE": ("14-47", 0.00522),
}

# Tasas de aporte (Colombia 2024/2025) — todas sobre IBC
TASA_SALUD_EMPLEADOR = 0.085
TASA_SALUD_EMPLEADO = 0.040
TASA_PENSION_EMPLEADOR = 0.120
TASA_PENSION_EMPLEADO = 0.040
TASA_CCF = 0.040
TASA_SENA = 0.020
TASA_ICBF = 0.030

# Fondo de Solidaridad Pensional (aplica IBC > 4 SMMLV)
TASA_FSP_BASE = 0.010  # > 4 SMMLV
TASA_FSP_ADICIONAL = 0.002  # > 16 SMMLV (acumulativo)


# ──────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Normaliza texto: mayúsculas, sin tildes para comparar con tablas."""
    if not texto:
        return ""
    texto = texto.upper().strip()
    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N"}
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return texto


def _buscar_codigo(nombre: str, tabla: dict) -> str:
    """Busca código PILA por nombre normalizado (búsqueda flexible)."""
    if not nombre:
        return ""
    norm = _normalizar(nombre)
    # Exacto
    if norm in tabla:
        return tabla[norm]
    # Parcial: si el nombre de la tabla está contenido en el valor recibido
    for clave, codigo in tabla.items():
        if clave in norm or norm in clave:
            return codigo
    return ""


def _periodo_anterior(mes: int, anio: int) -> tuple:
    """Retorna (mes_ant, anio_ant) del período anterior."""
    if mes == 1:
        return 12, anio - 1
    return mes - 1, anio


def _f(valor, ancho: int, alinear="izq", relleno=" ") -> str:
    """Formatea un campo al ancho indicado."""
    s = str(valor) if valor is not None else ""
    if alinear == "izq":
        return s.ljust(ancho, relleno)[:ancho]
    else:
        return s.rjust(ancho, relleno)[:ancho]


def _fi(valor, ancho: int) -> str:
    """Entero con ceros a la izquierda."""
    return str(int(valor)).zfill(ancho)[:ancho]


# ──────────────────────────────────────────────────────────────────────────────
# GENERADOR TIPO 01 — Cabecera (359 chars)
# ──────────────────────────────────────────────────────────────────────────────

def _gen_tipo01(
    razon_social: str,
    nit: str,
    digito_verificacion: str,
    arl_code: str,
    mes: int,
    anio: int,
    num_cotizantes: int,
    total_ibc: int,
    total_aportes: int,
) -> str:
    """
    Genera el registro tipo 01 (cabecera) de 359 caracteres.
    Basado en análisis del archivo muestra planilla_E_2026-04.txt.
    """
    mes_ant, anio_ant = _periodo_anterior(mes, anio)
    periodo_actual = f"{anio:04d}-{mes:02d}"
    periodo_anterior = f"{anio_ant:04d}-{mes_ant:02d}"

    nit_clean = nit.strip().replace("-", "").replace(".", "")[:9]
    dv = str(digito_verificacion).strip()[:1] if digito_verificacion else "0"
    arl = _f(arl_code, 5) if arl_code else "14-11"

    # Construcción campo a campo (basado en muestra)
    tipo = "01"                              # 1-2:   tipo registro
    indicador = "1"                          # 3:     indicador
    secuencia = "0001"                       # 4-7:   secuencia
    razon = _f(razon_social.upper(), 200)    # 8-207: razón social
    tipo_id = "NI"                           # 208-209
    nit_fmt = _f(nit_clean, 9)              # 210-218
    spaces1 = "       "                      # 219-225 (7 spaces)
    dv_fmt = dv                              # 226
    tipo_emp = "E"                           # 227 (tipo planilla: E=empleadores)
    spaces2 = _f("", 20)                    # 228-247
    clase = "S"                              # 248 (clase aportante: S=sociedad)
    num_orden = "01"                         # 249-250
    spaces3 = _f("", 8)                     # 251-258
    tipo_doc_emp = "01"                      # 259-260 (01=NIT)
    spaces4 = _f("", 38)                    # 261-298
    arl_fmt = _f(arl, 5)                    # 299-303
    sep1 = " "                              # 304
    per_ant = periodo_anterior              # 305-311
    per_act = periodo_actual                # 312-318
    control1 = _fi(0, 10)                   # 319-328 (campo control - ceros)
    spaces5 = _f("", 10)                    # 329-338
    cotizantes = _fi(num_cotizantes, 5)     # 339-343
    control2 = _fi(0, 4)                    # 344-347 (campo control)
    # Resumen IBC y aportes totales (simplificado)
    total_ibc_fmt = _fi(total_ibc // 100, 5)[:5]   # 348-352 (en centenas)
    total_ap_fmt = _fi(total_aportes, 6)[:6]         # 353-358
    fin = " "                               # 359

    linea = (
        tipo + indicador + secuencia + razon +
        tipo_id + nit_fmt + spaces1 + dv_fmt + tipo_emp +
        spaces2 + clase + num_orden + spaces3 + tipo_doc_emp +
        spaces4 + arl_fmt + sep1 + per_ant + per_act +
        control1 + spaces5 + cotizantes + control2 +
        total_ibc_fmt + total_ap_fmt + fin
    )

    # Verificar longitud exacta
    assert len(linea) == 359, f"Tipo 01 longitud incorrecta: {len(linea)}"
    return linea


# ──────────────────────────────────────────────────────────────────────────────
# GENERADOR TIPO 02 — Cotizante (693 chars)
# ──────────────────────────────────────────────────────────────────────────────

def _split_nombre(nombre: str):
    """
    Separa el nombre completo en (apellidos, nombres).
    Asume formato: PRIMER_APELLIDO SEGUNDO_APELLIDO PRIMER_NOMBRE [SEGUNDO_NOMBRE]
    """
    partes = (nombre or "").strip().upper().split()
    if len(partes) >= 4:
        apellidos = " ".join(partes[:2])
        nombres = " ".join(partes[2:])
    elif len(partes) == 3:
        apellidos = " ".join(partes[:2])
        nombres = partes[2]
    elif len(partes) == 2:
        apellidos = partes[0]
        nombres = partes[1]
    else:
        apellidos = nombre.upper() if nombre else ""
        nombres = ""
    return apellidos, nombres


def _calcular_aportes(ibc: int, arl_rate: float = 0.00522, smmlv: int = 1_423_500):
    """Calcula todos los aportes en pesos enteros."""
    salud_emp = round(ibc * TASA_SALUD_EMPLEADOR)
    salud_tra = round(ibc * TASA_SALUD_EMPLEADO)
    pen_emp = round(ibc * TASA_PENSION_EMPLEADOR)
    pen_tra = round(ibc * TASA_PENSION_EMPLEADO)
    pen_total = pen_emp + pen_tra
    arl = round(ibc * arl_rate)
    ccf = round(ibc * TASA_CCF)
    sena = round(ibc * TASA_SENA)
    icbf = round(ibc * TASA_ICBF)

    # Fondo de Solidaridad Pensional
    fsp = 0
    if ibc > 4 * smmlv:
        fsp = round(ibc * TASA_FSP_BASE)
    if ibc > 16 * smmlv:
        fsp += round(ibc * TASA_FSP_ADICIONAL)

    return {
        "salud_emp": salud_emp, "salud_tra": salud_tra,
        "pen_emp": pen_emp, "pen_tra": pen_tra, "pen_total": pen_total,
        "arl": arl, "ccf": ccf, "sena": sena, "icbf": icbf, "fsp": fsp,
        "total_salud": salud_emp + salud_tra,
        "total": salud_emp + salud_tra + pen_total + arl + ccf + sena + icbf + fsp,
    }


def _gen_aportes_section(ibc: int, arl_rate: float = 0.00522, dias: int = 30) -> str:
    """
    Genera la sección de aportes (posiciones 207-693, 487 chars).
    Basada en el patrón observado en archivos PILA muestra.
    Formato: IBC×4 + tasa + valores calculados + campos adicionales.

    NOTA: Esta sección requiere validación contra la resolución UGPP 2388/2016
    antes de uso oficial. Los campos de relleno entre valores se aproximan
    con ceros hasta completar 487 caracteres.
    """
    ap = _calcular_aportes(ibc, arl_rate)
    ibc9 = _fi(ibc, 9)
    dias2 = _fi(dias, 2)

    # Sección aportes según patrón muestra:
    # IBC base ×4 | tasa pension | total pension | parafiscales | ARL | etc.
    seccion = (
        # IBCs base por fondo (9 chars c/u × 4 = 36)
        ibc9 + ibc9 + ibc9 + ibc9 +
        # Tasa total pension "0.16" (4)
        f"0.{int(TASA_PENSION_EMPLEADOR * 100 + TASA_PENSION_EMPLEADO * 100):02d}" +
        # Fill (6)
        _fi(0, 6) +
        # Total pensión (7)
        _fi(ap["pen_total"], 7) +
        # Fill/zeros (19) — campos adicionales pension (subfondos, etc.)
        _fi(0, 19) +
        # Salud: tasa + valores (32)
        f"0.{int((TASA_SALUD_EMPLEADOR + TASA_SALUD_EMPLEADO) * 100):02d}" +
        _fi(0, 8) +
        _fi(ap["total_salud"], 7) +
        _fi(0, 3) +
        # Días cotizados (formato "dias000dias000" por fondo) (26)
        dias2 + _fi(0, 11) + "               " +
        # Fill ARL section (9)
        _fi(0, 9) +
        "               " +
        # ARL: tasa + valor (25)
        f"0.{int(arl_rate * 10000):05d}" +
        _fi(0, 8) +
        _fi(ap["arl"], 7) +
        # CCF: tasa + valor + fill (23)
        f"0.{int(TASA_CCF * 100):02d}" +
        _fi(0, 8) +
        _fi(ap["ccf"], 7) +
        _fi(0, 3) +
        # SENA: tasa + valor (14)
        f"0.{int(TASA_SENA * 100):02d}" +
        _fi(0, 9) +
        _fi(ap["sena"], 7) +
        # ICBF: tasa + valor + fill (26)
        f"0.{int(TASA_ICBF * 100):02d}" +
        _fi(0, 9) +
        _fi(ap["icbf"], 7) +
        _fi(0, 5) +
        # FSP y campos finales (fill hasta 487)
        f"0.{int(TASA_FSP_BASE * 100):02d}" +
        _fi(0, 9) +
        _fi(ap["fsp"], 7) +
        _fi(0, 14)
    )

    # Asegurar exactamente 487 chars
    if len(seccion) > 487:
        seccion = seccion[:487]
    elif len(seccion) < 487:
        seccion = seccion.ljust(487)

    return seccion


def _gen_tipo02(
    seq: int,
    afiliado,
    ibc: int,
    arl_rate: float = 0.00522,
    dias: int = 30,
) -> str:
    """
    Genera el registro tipo 02 (cotizante) de 693 caracteres.

    Posiciones clave (1-indexadas):
    1-2:   tipo registro ("02")
    3-7:   secuencia
    8-9:   tipo documento
    10-25: número documento (16 chars)
    26-29: subtipo cotizante (0100=dependiente, 0104=independiente...)
    30-31: flags extranjero/colombiano exterior ("00")
    32-36: municipio DIVIPOLA (5 dígitos)
    37-86: apellidos (50 chars)
    87-156: nombres (70 chars)
    157-158: fill "00"
    159-164: AFP código (6 chars)
    165-170: fill (6 spaces)
    171-176: EPS código (6 chars)
    177-182: fill (6 spaces)
    183-188: CCF código (6 chars)
    189-196: días cotizados ×4 (4×2 = 8 chars: dias_ccf, dias_arl, dias_sal, dias_pen)
    197-205: IBC (9 dígitos)
    206:    sexo ("M"/"F"/"0" si no aplica)
    207-693: sección aportes (487 chars)
    """
    # Identificación
    tipo_doc = _f(afiliado.tipo_doc or "CC", 2)
    doc = _f(afiliado.doc or "", 16)

    # Subtipo: si Afiliado.subtipo es "INDEPENDIENTE" → "0104", etc.
    subtipo_raw = (afiliado.subtipo or "").upper()
    if "INDEPENDIENTE" in subtipo_raw or subtipo_raw == "0104":
        subtipo = "0104"
    elif subtipo_raw.isdigit() and len(subtipo_raw) == 4:
        subtipo = subtipo_raw
    else:
        subtipo = "0100"  # dependiente por defecto

    # Municipio DIVIPOLA (default 11001 = Bogotá)
    municipio = _f(afiliado.municipio_code or "11001", 5)

    # Nombre → apellidos + nombres
    apellidos, nombres = _split_nombre(afiliado.nombre)
    apellidos_fmt = _f(apellidos, 50)
    nombres_fmt = _f(nombres, 70)

    # Códigos fondos
    afp_code = _f(_buscar_codigo(afiliado.afp, AFP_CODES), 6)
    eps_code = _f(_buscar_codigo(afiliado.eps, EPS_CODES), 6)
    ccf_code = _f(_buscar_codigo(afiliado.ccf, CCF_CODES), 6)

    dias2 = _fi(dias, 2)
    ibc9 = _fi(ibc, 9)

    # Parte identificación (posiciones 1-206)
    ident = (
        "02" +                  # 1-2: tipo
        _fi(seq, 5) +           # 3-7: secuencia
        tipo_doc +              # 8-9: tipo doc
        doc +                   # 10-25: documento
        subtipo +               # 26-29: subtipo
        "  " +                  # 30-31: flags (extranjero/col.exterior - default espacios)
        municipio +             # 32-36: municipio
        apellidos_fmt +         # 37-86: apellidos
        nombres_fmt +           # 87-156: nombres
        "00" +                  # 157-158: fill
        afp_code +              # 159-164: AFP
        _f("", 6) +             # 165-170: fill
        eps_code +              # 171-176: EPS
        _f("", 6) +             # 177-182: fill
        ccf_code +              # 183-188: CCF
        dias2 + dias2 + dias2 + dias2 +  # 189-196: días ×4
        ibc9 +                  # 197-205: IBC
        "0"                     # 206: sexo (0=no especificado)
    )

    assert len(ident) == 206, f"Ident tipo02 longitud {len(ident)}"

    # Sección aportes (posiciones 207-693)
    aportes = _gen_aportes_section(ibc, arl_rate, dias)

    linea = ident + aportes

    assert len(linea) == 693, f"Tipo 02 longitud {len(linea)}"
    return linea


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

def generar_pila(
    afiliados: list,
    ibc_global: int,
    nit: str,
    razon_social: str,
    digito_verificacion: str = "0",
    mes: int = 4,
    anio: int = 2026,
    arl_nombre: str = "POSITIVA",
) -> str:
    """
    Genera el archivo PILA completo como string.

    Args:
        afiliados: lista de objetos models.Afiliado (activos, estado ACTIVO)
        ibc_global: IBC global de Config (usado cuando afiliado.ibc es None)
        nit: NIT del aportante (sin dígito verificación, sin puntos/guiones)
        razon_social: Razón social del aportante
        digito_verificacion: Dígito verificación del NIT
        mes: Mes del período (1-12)
        anio: Año del período
        arl_nombre: Nombre del ARL del aportante (para código en tipo 01)

    Returns:
        Contenido del archivo PILA como string (separador de línea: \r\n)
    """
    # Determinar código y tasa ARL
    arl_info = ARL_CODES.get(_normalizar(arl_nombre), ("14-11", 0.00522))
    arl_code, arl_rate = arl_info

    # Calcular totales para tipo 01
    lineas = []
    total_ibc = 0
    total_aportes = 0
    registros_tipo02 = []

    for i, afil in enumerate(afiliados, 1):
        ibc = int(afil.ibc) if (afil.ibc and afil.ibc > 0) else ibc_global
        ap = _calcular_aportes(ibc, arl_rate)
        total_ibc += ibc
        total_aportes += ap["total"]
        registros_tipo02.append(_gen_tipo02(i, afil, ibc, arl_rate))

    # Tipo 01
    tipo01 = _gen_tipo01(
        razon_social=razon_social,
        nit=nit,
        digito_verificacion=digito_verificacion,
        arl_code=arl_code,
        mes=mes,
        anio=anio,
        num_cotizantes=len(afiliados),
        total_ibc=total_ibc,
        total_aportes=total_aportes,
    )
    lineas.append(tipo01)
    lineas.extend(registros_tipo02)

    return "\r\n".join(lineas)
