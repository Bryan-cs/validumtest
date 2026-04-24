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
    forma_presentacion: str = "U",
) -> str:
    """
    Genera el registro tipo 01 (cabecera) de 359 caracteres.
    Posiciones verificadas contra ADAX (sistema oficial PILA).

    Estructura (0-indexed):
      0-1:   "01" tipo registro
      2:     "1"  indicador
      3-6:   "0001" secuencia
      7-206: razón social (200 chars)
      207-208: "NI" tipo identificación
      209-217: NIT (9 chars)
      218-224: 7 spaces
      225:   dígito verificación
      226:   "E" tipo planilla empleadores
      227-246: 20 spaces
      247:   forma presentación (U/C/D/S)
      248-297: 50 spaces
      298-302: código ARL (5 chars, ej. "14-11")
      303:   space
      304-310: período anterior "AAAA-MM"
      311-317: período actual "AAAA-MM"
      318-327: 10 zeros (control)
      328-337: 10 spaces
      338-342: nº cotizantes (5 digits)
      343-346: 4 zeros (control)
      347-351: total IBC en centenas (5 digits)
      352-357: total aportes (6 digits)
      358:   forma presentación (repetido al final)
    """
    mes_ant, anio_ant = _periodo_anterior(mes, anio)
    periodo_actual = f"{anio:04d}-{mes:02d}"
    periodo_anterior = f"{anio_ant:04d}-{mes_ant:02d}"

    nit_clean = nit.strip().replace("-", "").replace(".", "")[:9]
    dv = str(digito_verificacion).strip()[:1] if digito_verificacion else "0"
    arl = _f(arl_code, 5) if arl_code else "14-11"
    fp = forma_presentacion[:1] if forma_presentacion else "U"

    linea = (
        "01"                            # 0-1:   tipo registro
        + "1"                           # 2:     indicador
        + "0001"                        # 3-6:   secuencia
        + _f(razon_social.upper(), 200) # 7-206: razón social
        + "NI"                          # 207-208
        + _f(nit_clean, 9)              # 209-217
        + "       "                     # 218-224 (7 spaces)
        + dv                            # 225: DV
        + "E"                           # 226: tipo planilla
        + _f("", 20)                    # 227-246: 20 spaces
        + fp                            # 247: forma presentación
        + _f("", 50)                    # 248-297: 50 spaces
        + _f(arl, 5)                    # 298-302: ARL
        + " "                           # 303
        + periodo_anterior              # 304-310
        + periodo_actual                # 311-317
        + _fi(0, 10)                    # 318-327: control
        + _f("", 10)                    # 328-337: spaces
        + _fi(num_cotizantes, 5)        # 338-342: cotizantes
        + _fi(0, 4)                     # 343-346: control
        + _fi(total_ibc // 1000, 5)[:5]# 347-351: total IBC (miles)
        + _fi(total_aportes, 6)[:6]    # 352-357: total aportes
        + fp                            # 358: forma presentación (repite)
    )

    assert len(linea) == 359, f"Tipo 01 longitud incorrecta: {len(linea)}"
    return linea


# ──────────────────────────────────────────────────────────────────────────────
# GENERADOR TIPO 02 — Cotizante (693 chars)
# ──────────────────────────────────────────────────────────────────────────────

def _split_nombre(nombre: str):
    """
    Separa nombre completo en 4 partes para PILA.
    Formato esperado: APELLIDO1 APELLIDO2 NOMBRE1 [NOMBRE2]

    Returns: (primer_apellido, segundo_apellido, primer_nombre, segundo_nombre)
    """
    partes = (nombre or "").strip().upper().split()
    if len(partes) >= 4:
        return partes[0], partes[1], partes[2], " ".join(partes[3:])
    elif len(partes) == 3:
        return partes[0], partes[1], partes[2], ""
    elif len(partes) == 2:
        return partes[0], "", partes[1], ""
    elif len(partes) == 1:
        return partes[0], "", "", ""
    else:
        return "", "", "", ""


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


def _gen_aportes_section(ibc: int, arl_rate: float = 0.00522, dias: int = 30,
                          ibc_pension: int = None) -> str:
    """
    Genera la sección de aportes (pos 201-692, 492 chars).
    Posiciones verificadas contra archivo PILA muestra (ADAX).

    Estructura (offsets dentro de aportes, 0-indexed):
      0-35:  4 × IBC (9 chars c/u): pension, salud, ARL, CCF
      36-39: tasa pension "0.16" (o "0.00" para independiente)
      40-45: 6 zeros
      46-52: total pension × 10 (7 chars)  [patrón observado: IBC * 1.6 * 10]
      53-71: 19 zeros
      72+:   sección salud, ARL, parafiscales, campos finales (relleno hasta 492)

    NOTA: La sección de aportes (offsets 72-491) requiere validación completa
    contra Resolución UGPP 2388/2016. Los campos parafiscales se aproximan con
    ceros hasta completar 492 caracteres totales.
    """
    ap = _calcular_aportes(ibc, arl_rate)
    ibc9 = _fi(ibc, 9)
    ibc_pen9 = _fi(ibc_pension if ibc_pension is not None else ibc, 9)
    dias2 = _fi(dias, 2)

    # Tasa y valor pensión
    tasa_pen = f"0.{int((TASA_PENSION_EMPLEADOR + TASA_PENSION_EMPLEADO) * 100):02d}"
    # Valor pensión observado en muestra = IBC_pen * 1.6 * 10 (ajuste ADAX)
    pen_ibc_efectivo = ibc_pension if ibc_pension is not None else ibc
    pen_val = _fi(int(pen_ibc_efectivo * (TASA_PENSION_EMPLEADOR + TASA_PENSION_EMPLEADO) * 10), 7)

    # Si es independiente (ibc_pension == 0), tasa y valor = 0
    if ibc_pension == 0:
        tasa_pen = "0.00"
        pen_val = _fi(0, 7)

    seccion = (
        # IBCs × 4 (36 chars)
        ibc_pen9 + ibc9 + ibc9 + ibc9 +
        # Pensión (36 chars total: tasa 4 + zeros 6 + valor 7 + zeros 19)
        tasa_pen +              # 4
        _fi(0, 6) +             # 6
        pen_val +               # 7
        _fi(0, 19) +            # 19
        # Salud (patrón muestra: "0.04" + 8zeros + valor_salud_7 + 3zeros)
        f"0.{int(TASA_SALUD_EMPLEADO * 100):02d}" +
        _fi(0, 8) +
        _fi(ap["total_salud"], 7) +
        _fi(0, 3) +
        # Días + fill (38 chars: "dias000...spaces...dias000...spaces...")
        dias2 + _fi(0, 11) + "               " +
        _fi(0, 9) + "               " +
        # ARL (tasa 0.00522 + zeros + valor)
        f"0.{int(arl_rate * 10000):05d}" +
        _fi(0, 8) +
        _fi(ap["arl"], 7) +
        # CCF/parafiscales
        f"0.{int(TASA_CCF * 100):02d}" +
        _fi(0, 8) +
        _fi(ap["ccf"], 7) +
        _fi(0, 3) +
        f"0.{int(TASA_SENA * 100):02d}" +
        _fi(0, 9) +
        _fi(ap["sena"], 7) +
        f"0.{int(TASA_ICBF * 100):02d}" +
        _fi(0, 9) +
        _fi(ap["icbf"], 7) +
        _fi(0, 5) +
        f"0.{int(TASA_FSP_BASE * 100):02d}" +
        _fi(0, 9) +
        _fi(ap["fsp"], 7) +
        _fi(0, 14)
    )

    # Asegurar exactamente 492 chars
    if len(seccion) > 492:
        seccion = seccion[:492]
    elif len(seccion) < 492:
        seccion = seccion.ljust(492)

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
    Posiciones verificadas contra archivo PILA muestra (ADAX).

    Estructura (0-indexed):
      0-1:   "02"
      2-6:   secuencia (5)
      7-8:   tipo_doc (2)
      9-24:  documento (16)
      25-28: subtipo (4)  — 0100=dependiente, 0104=independiente
      29-30: flags "  " (2)
      31-35: municipio DIVIPOLA (5)
      36-55: primer_apellido (20)
      56-85: segundo_apellido (30)
      86-105: primer_nombre (20)
      106-150: segundo_nombre (45)
      151-152: "00" fill
      153-158: AFP código (6)
      159-164: fill (6 spaces)
      165-170: EPS código (6)
      171-176: fill (6 spaces)
      177-182: CCF código (6)
      183-190: días cotizados ×4 (4×2 = 8)
      191-199: IBC (9)
      200:    sexo ("F"/"M" — ADAX usa "F" por defecto)
      201-692: sección aportes (492 chars)
    """
    tipo_doc = _f(afiliado.tipo_doc or "CC", 2)
    doc = _f(afiliado.doc or "", 16)

    subtipo_raw = (afiliado.subtipo or "").upper()
    if "INDEPENDIENTE" in subtipo_raw or subtipo_raw == "0104":
        subtipo = "0104"
        es_independiente = True
    elif subtipo_raw.isdigit() and len(subtipo_raw) == 4:
        subtipo = subtipo_raw
        es_independiente = subtipo == "0104"
    else:
        subtipo = "0100"
        es_independiente = False

    municipio = _f(afiliado.municipio_code or "11001", 5)

    # Nombres en 4 partes para formato ADAX
    ap1, ap2, n1, n2 = _split_nombre(afiliado.nombre)
    ape1_fmt = _f(ap1, 20)
    ape2_fmt = _f(ap2, 30)
    nom1_fmt = _f(n1, 20)
    nom2_fmt = _f(n2, 45)

    afp_code = _f(_buscar_codigo(afiliado.afp, AFP_CODES), 6)
    eps_code = _f(_buscar_codigo(afiliado.eps, EPS_CODES), 6)
    ccf_code = _f(_buscar_codigo(afiliado.ccf, CCF_CODES), 6)

    # Para independiente: días pensión = 00 (primer campo días)
    dias2 = _fi(dias, 2)
    dias_pen = "00" if es_independiente else dias2
    dias_sal = dias2
    dias_arl = dias2
    dias_ccf = dias2
    dias_fmt = dias_pen + dias_sal + dias_arl + dias_ccf

    ibc9 = _fi(ibc, 9)
    # IBC pensión = 0 para independiente en sección aportes
    ibc_pension = 0 if es_independiente else ibc

    ident = (
        "02" +          # 0-1
        _fi(seq, 5) +   # 2-6
        tipo_doc +      # 7-8
        doc +           # 9-24
        subtipo +       # 25-28
        "  " +          # 29-30
        municipio +     # 31-35
        ape1_fmt +      # 36-55
        ape2_fmt +      # 56-85
        nom1_fmt +      # 86-105
        nom2_fmt +      # 106-150
        "00" +          # 151-152
        afp_code +      # 153-158
        _f("", 6) +     # 159-164
        eps_code +      # 165-170
        _f("", 6) +     # 171-176
        ccf_code +      # 177-182
        dias_fmt +      # 183-190
        ibc9 +          # 191-199
        "F"             # 200: sexo (ADAX default)
    )

    assert len(ident) == 201, f"Ident tipo02 longitud {len(ident)}"

    aportes = _gen_aportes_section(ibc, arl_rate, dias, ibc_pension=ibc_pension)

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
