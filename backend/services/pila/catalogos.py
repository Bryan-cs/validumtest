"""Catálogos normativos de PILA.

Fuente: Anexo Técnico 2 de la Resolución 2388 de 2016, versión 30 del 24-07-2026
(modificado por la Resolución 1529 de 2026). Los códigos se extrajeron del anexo,
no se transcribieron a mano.

Van en código y no en una migración porque son normativos: cuando el Ministerio
publique una versión nueva se actualiza este archivo y se vuelve a sembrar. La
siembra es idempotente y marca como no vigente lo que el anexo dejó de listar,
sin borrar filas — un afiliado puede seguir apuntando a un código derogado y su
planilla histórica debe poder leerse.

Los códigos de administradoras (EPS, AFP, CCF, ARL) y los DANE de departamento
y municipio no salen del anexo — el anexo no los contiene. Vienen de
`datos/referencia.json`, con su fuente anotada ahí mismo.
"""

import json
from pathlib import Path

ANEXO_VERSION = "30"
ANEXO_FECHA = "2026-07-24"

# Campo 30 del archivo tipo 1. El 17 lo agregó la Resolución 1529 de 2026.
TIPO_APORTANTE = {
    "01": "Empleador",
    "02": "Independiente",
    "03": "Entidades o universidades públicas de los regímenes especial y de excepción",
    "04": "Agremiaciones, asociaciones o congregaciones religiosas",
    "05": "Cooperativas y Precooperativas de Trabajo Asociado",
    "06": "Misiones diplomáticas, consulares o de organismos multilaterales no sometidos a la legislación colombiana",
    "07": "Organizaciones Administradoras del Programa de Hogares de Bienestar",
    "08": "Pagador de aportes de los concejales municipales o distritales o de los ediles de las juntas administradoras locales",
    "09": "Pagador de aportes contrato sindical",
    "10": "Pagador programa de reincorporación",
    "11": "Pagador aportes parafiscales del Magisterio",
    "12": "Pagador prestación humanitaria",
    "13": "Pagador Subsistema Nacional de Voluntarios en Primera Respuesta",
    "14": "Trabajador pago aporte faltante pensión",
    "15": "Contratante",
    "16": "Pagador Promotor del Servicio Social para la Paz",
    "17": "Pagador Recicladores de Oficio",
}

# Campo 5 del registro tipo 2. La numeración es dispersa: los códigos que el
# anexo v30 ya no lista quedaron derogados y no deben poder elegirse.
# Campo 6 del registro tipo 2. El subtipo no reemplaza al tipo: lo matiza, y
# varios de ellos levantan la obligación de cotizar a pensión sin dejar de ser
# el cotizante que se es. No existen los números 7 ni 8.
SUBTIPO_COTIZANTE = {
    "01": "Dependiente pensionado por vejez, jubilación o invalidez activo",
    "02": "Independiente pensionado por vejez, jubilación o invalidez activo",
    "03": "Cotizante no obligado a cotización a pensiones por edad",
    "04": "Cotizante con requisitos cumplidos para pensión o indemnización sustitutiva",
    "05": "Cotizante con indemnización sustitutiva o devolución de saldos reconocida",
    "06": "Cotizante de régimen exceptuado de pensiones",
    "09": "Cotizante pensionado con mesada igual o superior a 25 SMLMV",
    "10": "Residente en el exterior afiliado voluntario a pensiones",
    "11": "Conductor de taxi de servicio público",
    "12": "Conductor de taxi de servicio público no obligado a cotizar a pensión",
}

TIPO_COTIZANTE = {
    "01": "Dependiente",
    "02": "Servicio doméstico",
    "03": "Independiente",
    "04": "Madre sustituta",
    "12": "Aprendices en etapa lectiva",
    "16": "Independiente agremiado o asociado",
    "18": "Servidores públicos sin tope máximo en el IBC",
    "19": "Aprendices etapa lectiva Ley 2466 de 2025",
    "20": "Estudiantes (Régimen especial Ley 789 de 2002)",
    "21": "Estudiante de posgrado de salud y residente",
    "22": "Profesor de establecimiento particular",
    "23": "Estudiantes aporte solo riesgos laborales",
    "30": "Dependiente entidades o universidades públicas de los Regímenes Especial y de Excepción",
    "31": "Cooperados de Cooperativas o Precooperativas de trabajo asociado",
    "32": "Cotizante miembro de la carrera diplomática o consular de un país extranjero o funcionario de organismo multilateral no sometido a la legislación colombiana",
    "33": "Beneficiario del Fondo de Solidaridad Pensional",
    "34": "Concejal o edil de Junta Administradora Local del Distrito Capital de Bogotá",
    "35": "Concejal municipal o distrital",
    "36": "Edil de Junta Administradora Local beneficiario del Fondo de Solidaridad Pensional",
    "40": "Beneficiario UPC adicional",
    "42": "Cotizante independiente pago solo salud",
    "43": "Cotizante a pensiones con pago por tercero",
    "44": "Cotizante dependiente Empleo de Emergencia con duración mayor o igual a un mes",
    "45": "Cotizante dependiente Empleo de Emergencia con duración menor a un mes",
    "47": "Trabajador dependiente de entidad beneficiaria del Sistema General de Participación-Aportes Patronales",
    "51": "Trabajador de tiempo parcial dependiente",
    "52": "Beneficiario del mecanismo de protección al cesante",
    "53": "Afiliado participe",
    "54": "Prepensionado de entidades en liquidación",
    "55": "Afiliado participe-dependiente",
    "56": "Prepensionado con aporte voluntario a Salud",
    "57": "Independiente voluntario al Sistema de Riesgos Laborales",
    "58": "Estudiantes de prácticas laborales en el sector público",
    "59": "Independiente con contrato de prestación de servicios superior a 1 mes",
    "60": "Edil Junta Administradora Local no beneficiario del Fondo de Solidaridad Pensional",
    "61": "Beneficiario programa de reincorporación",
    "62": "Personal del Magisterio",
    "63": "Beneficiario de Prestación humanitaria",
    "64": "Trabajador penitenciario o servicio de utilidad pública",
    "65": "Dependiente vinculado piso de protección social",
    "66": "Independiente vinculado piso de protección social",
    "67": "Voluntario en primera respuesta aporte solo al Sistema de Riesgos Laborales",
    "68": "Dependiente veterano de la Fuerza Pública",
    "69": "Contribuyente solidario",
    "70": "Promotor del Servicio Social para la Paz",
    "71": "Ley de Segundas Oportunidades",
    "72": "Mujeres con aporte a pensión por pago por tercero",
    "73": "Interno de Medicina",
    "74": "Reciclador de Oficio",
    "75": "Dependiente con Permanencia en el Régimen Subsidiado",
    "76": "Trabajador de tiempo parcial Independiente",
}

# Campo 8 del registro tipo 1.
TIPO_PLANILLA = {
    "A": "Planilla cotizantes con novedad de ingreso",
    "B": "Planilla Piso de Protección Social",
    "E": "Planilla empleados",
    "F": "Planilla pago aporte patronal faltante, de una entidad beneficiaria del sistema general de participaciones",
    "H": "Planilla madres sustitutas",
    "I": "Planilla independientes",
    "J": "Planilla para pago de seguridad social en cumplimiento de sentencia judicial",
    "K": "Planilla estudiantes",
    "M": "Planilla mora",
    "N": "Planilla correcciones",
    "O": "Planilla Obligaciones determinadas por la UGPP",
    "S": "Planilla empleados de servicio doméstico",
    "T": "Planilla empleados entidad beneficiaria del Sistema General de Participación",
    "U": "Planilla de uso UGPP para pago por terceros",
    "W": "Planilla Reliquidaciones por Retroactivo Servidores Públicos",
    "X": "Planilla para el pago de empresas en proceso de liquidación, reestructuración o en procesos concursales",
    "Y": "Planilla independientes empresas",
    "Z": "Planilla para pago de cálculo actuarial por omisión en pensiones",
}

# Campo 3 del registro tipo 2, más NI para el aportante.
TIPO_DOC = {
    "CC": "Cédula de ciudadanía",
    "CD": "Carné diplomático",
    "CE": "Cédula de extranjería",
    "NI": "Número de identificación tributaria",
    "PA": "Pasaporte",
    "PE": "Permiso Especial de Permanencia",
    "PT": "Permiso por Protección Temporal",
    "SC": "Salvoconducto de permanencia",
    "TI": "Tarjeta de identidad",
}

# ── Datos de referencia que no vienen del anexo ──────────────────────────────
# Viven en un JSON aparte y no en este módulo porque son ~1.250 entradas que
# cambian por su cuenta —una EPS se liquida, un municipio se crea— y no tienen
# por qué ensuciar el diff de los catálogos normativos.
_REFERENCIA = json.loads((Path(__file__).parent / "datos" / "referencia.json")
                         .read_text(encoding="utf-8"))

FUENTE_ADMINISTRADORAS = _REFERENCIA["fuente_administradoras"]
FUENTE_DANE = _REFERENCIA["fuente_dane"]

# Un catálogo por subsistema: EPS, AFP, CCF, ARL, SENA, ICBF, ADRES.
ADMINISTRADORAS = _REFERENCIA["administradoras"]

# El Fondo de Solidaridad Pensional no es una AFP, pero ocupa el campo 31
# cuando el cotizante es de régimen exceptuado (subtipo 6) y su IBC llega a 4
# SMLMV: no aporta a pensión pero sí al Fondo. No viene en el archivo de la
# UGPP porque no es una administradora de pensiones.
ADMINISTRADORAS.setdefault("AFP", {})["FSP001"] = "Fondo de Solidaridad Pensional"

DEPTO = _REFERENCIA["departamentos"]

# El código DANE de municipio solo es único dentro de su departamento: "001" es
# Medellín en Antioquia y Barranquilla en Atlántico. Por eso se guarda completo
# (5 dígitos) con el departamento en `padre`, y el serializador lo parte en 2+3
# al escribir los campos 9 y 10 del registro tipo 2.
MUNICIPIO = {cod: nombre for cod, (nombre, _dep) in _REFERENCIA["municipios"].items()}
MUNICIPIO_DEPTO = {cod: dep for cod, (_nom, dep) in _REFERENCIA["municipios"].items()}

CATALOGOS = {
    "TIPO_APORTANTE": TIPO_APORTANTE,
    "TIPO_COTIZANTE": TIPO_COTIZANTE,
    "SUBTIPO_COTIZANTE": SUBTIPO_COTIZANTE,
    "TIPO_PLANILLA":  TIPO_PLANILLA,
    "TIPO_DOC":       TIPO_DOC,
    "DEPTO":          DEPTO,
    "MUNICIPIO":      MUNICIPIO,
    **ADMINISTRADORAS,
}

# Qué código de otro catálogo es el "padre" de cada entrada.
PADRES = {"MUNICIPIO": MUNICIPIO_DEPTO}

# Administradoras que ya no operan (EPS liquidadas o absorbidas, ARL que salió
# del mercado). Se siembran como NO vigentes: no deben poder elegirse al crear
# nada, pero una planilla de 2019 las referencia y su nombre debe poder leerse.
HISTORICOS = _REFERENCIA["administradoras_historicas"]


# Palabras que solo dicen de qué subsistema es la administradora y estorban al
# comparar: "EPS COMPENSAR" y "Compensar" son la misma, y "NUEVA EPS SA." y
# "Nueva EPS" también.
_RUIDO = ("EPS", "CCF", "AFP", "ARL", "SA", "S.A", "S.A.", "SAS", "EOC", "CCF.")


def _normalizar(nombre: str) -> str:
    """Deja el nombre en lo que de verdad lo identifica.

    Sin tildes, sin puntuación, sin las siglas del subsistema y sin espacios
    de más. El formulario guarda "Nueva EPS" y el catálogo dice "NUEVA EPS
    SA.": las dos tienen que llegar a "NUEVA".
    """
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(nombre or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper()
    texto = "".join(c if c.isalnum() else " " for c in texto)
    palabras = [p for p in texto.split() if p and p not in _RUIDO]
    return " ".join(palabras)


def buscar_codigo(tipo: str, nombre: str) -> str:
    """El código PILA de una administradora a partir de su nombre.

    Existe porque el formulario guarda el nombre —"Compensar"— y el archivo
    plano necesita el código —"EPS008"—. Antes había que escribir los dos, y
    quien llenaba el formulario correctamente se encontraba con que el campo
    del archivo salía vacío.

    Devuelve "" cuando no hay una única coincidencia clara. Es a propósito:
    un código equivocado manda los aportes a otra administradora, así que es
    mejor dejarlo en blanco y que la liquidación avise.
    """
    catalogo = CATALOGOS.get((tipo or "").strip().upper())
    if not catalogo or not str(nombre or "").strip():
        return ""

    crudo = str(nombre).strip()

    # Un codigo escrito tal cual manda sobre todo lo demas. Tambien cubre las
    # entradas de lista que lo llevan entre parentesis para desempatar dos
    # administradoras que se llaman igual.
    if crudo in catalogo:
        return crudo
    import re
    for entre_parentesis in re.findall(r"\(([^)]+)\)", crudo):
        if entre_parentesis.strip() in catalogo:
            return entre_parentesis.strip()

    buscado = _normalizar(nombre)
    if not buscado:
        return ""

    exactos = [cod for cod, nom in catalogo.items() if _normalizar(nom) == buscado]
    if len(exactos) == 1:
        return exactos[0]

    # Sin coincidencia exacta se acepta que uno contenga al otro, pero solo si
    # hay una sola candidata: con varias no se puede saber cuál es.
    parciales = [cod for cod, nom in catalogo.items()
                 if buscado in _normalizar(nom) or _normalizar(nom) in buscado]
    return parciales[0] if len(parciales) == 1 else ""


def nombres_para_listas(tipo: str) -> list:
    """Los nombres de un subsistema, listos para un desplegable.

    Cada entrada tiene que resolver a un unico codigo, asi que cuando dos
    administradoras se llaman igual se les agrega el suyo entre parentesis.
    Sin eso, elegir una de las dos dejaria el campo del archivo vacio, que es
    justo lo que esto viene a evitar.
    """
    catalogo = CATALOGOS.get((tipo or "").strip().upper()) or {}
    veces = {}
    for nombre in catalogo.values():
        veces[nombre] = veces.get(nombre, 0) + 1
    entradas = [f"{nombre} ({codigo})" if veces[nombre] > 1 else nombre
                for codigo, nombre in catalogo.items()]
    return sorted(set(entradas))


def sembrar(db) -> dict:
    """Siembra o actualiza `pila_codigos`. Idempotente: se puede correr siempre.

    Devuelve el conteo de lo que hizo, para que el llamador lo registre.
    """
    import models

    creados = actualizados = derogados = 0
    historicos_creados = 0

    for tipo, datos in CATALOGOS.items():
        existentes = {c.codigo: c for c in db.query(models.PilaCodigo).filter_by(tipo=tipo).all()}
        padres = PADRES.get(tipo, {})
        historicos = HISTORICOS.get(tipo, {})

        for codigo, nombre in datos.items():
            padre = padres.get(codigo)
            fila = existentes.get(codigo)
            if fila is None:
                db.add(models.PilaCodigo(tipo=tipo, codigo=codigo, nombre=nombre,
                                         padre=padre, vigente=True))
                creados += 1
            elif fila.nombre != nombre or fila.padre != padre or not fila.vigente:
                fila.nombre = nombre
                fila.padre = padre
                fila.vigente = True
                actualizados += 1

        # Los derogados conocidos entran de una vez marcados como no vigentes,
        # para poder resolver el nombre de un código viejo sin ofrecerlo.
        for codigo, nombre in historicos.items():
            if codigo not in existentes and codigo not in datos:
                db.add(models.PilaCodigo(tipo=tipo, codigo=codigo, nombre=nombre, vigente=False))
                historicos_creados += 1

        # Lo que dejó de estar listado se marca no vigente, nunca se borra: las
        # planillas ya liquidadas siguen apuntando a esos códigos.
        for codigo, fila in existentes.items():
            if codigo not in datos and fila.vigente:
                fila.vigente = False
                derogados += 1

    db.commit()
    return {"creados": creados, "actualizados": actualizados,
            "derogados": derogados, "historicos": historicos_creados}
