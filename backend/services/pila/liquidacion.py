"""Motor de liquidación PILA.

Toma los afiliados de un aportante para un período y calcula, por cada uno,
días, IBC y aportes de cada subsistema. No escribe archivos ni toca la base:
devuelve el cálculo para que el router lo persista en `planillas_detalle`.

Dos decisiones de diseño que conviene tener presentes:

1. **A qué subsistemas cotiza cada quien sale de los servicios contratados**,
   los que se marcan en el formulario del afiliado. Es el mismo criterio que
   usa Cobro para facturar, vía `_servicios_afiliado`, así que lo que se cobra
   y lo que se liquida salen de la misma fuente. Los códigos de administradora
   sirven para llenar el archivo, no para decidir qué se liquida: un servicio
   contratado sin su código se liquida igual y se avisa.

2. **Los días salen de las novedades.** Sin novedad son 30. Con ingreso o retiro
   en el mes, los días transcurridos. PILA siempre trabaja sobre meses de 30
   días, no sobre los días naturales del calendario.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from crud_helpers import _servicios_afiliado
from . import obligaciones, perfiles

from . import parametros as P


@dataclass
class DetalleLiquidado:
    """Lo que se reporta de un cotizante en un registro tipo 2."""
    afiliado_id: Optional[int]
    tipo_doc: str
    doc: str
    primer_apellido: str = ""
    segundo_apellido: str = ""
    primer_nombre: str = ""
    segundo_nombre: str = ""
    tipo_cotizante: str = "01"
    subtipo_cotizante: str = ""
    # Campos 7 y 8 del registro tipo 2. Son marcas, no valores: cuando estan
    # puestas el subsistema correspondiente no se liquida.
    extranjero_no_pension: bool = False
    colombiano_exterior: bool = False
    cod_depto_labor: str = ""
    cod_municipio_labor: str = ""

    cod_afp: str = ""
    cod_eps: str = ""
    cod_ccf: str = ""

    dias_pension: int = 0
    dias_salud: int = 0
    dias_arl: int = 0
    dias_ccf: int = 0

    salario_basico: Decimal = Decimal("0")
    tipo_salario: str = "F"
    ibc_pension: Decimal = Decimal("0")
    ibc_salud: Decimal = Decimal("0")
    ibc_arl: Decimal = Decimal("0")
    ibc_ccf: Decimal = Decimal("0")

    tarifa_pension: Decimal = Decimal("0")
    cot_pension: Decimal = Decimal("0")
    fsp_solidaridad: Decimal = Decimal("0")
    fsp_subsistencia: Decimal = Decimal("0")

    tarifa_salud: Decimal = Decimal("0")
    cot_salud: Decimal = Decimal("0")

    tarifa_arl: Decimal = Decimal("0")
    cot_arl: Decimal = Decimal("0")
    centro_trabajo: str = ""
    # Campos 77 y 78: la ARL y la clase de riesgo del cotizante. El plano de
    # referencia del operador los trae llenos.
    cod_arl: str = ""
    clase_riesgo: str = ""
    # Campo 98: subactividad economica del aportante, no una tarifa.
    subactividad_economica: str = ""

    tarifa_ccf: Decimal = Decimal("0")
    valor_ccf: Decimal = Decimal("0")
    tarifa_sena: Decimal = Decimal("0")
    valor_sena: Decimal = Decimal("0")
    tarifa_icbf: Decimal = Decimal("0")
    valor_icbf: Decimal = Decimal("0")

    # El operador rechaza horas en cero. El plano de referencia reporta 8 por
    # cada día cotizado: 1 día -> 008.
    horas_laboradas: int = 0

    # Los servicios contratados que se liquidaron, para poder explicarlo.
    servicios: list = field(default_factory=list)

    exonerado: bool = False
    novedades: dict = field(default_factory=dict)
    fechas_novedades: dict = field(default_factory=dict)

    @property
    def total(self) -> Decimal:
        return (self.cot_pension + self.fsp_solidaridad + self.fsp_subsistencia +
                self.cot_salud + self.cot_arl + self.valor_ccf +
                self.valor_sena + self.valor_icbf)


@dataclass
class ResumenLiquidacion:
    detalles: list
    total_pension: Decimal = Decimal("0")
    total_salud: Decimal = Decimal("0")
    total_arl: Decimal = Decimal("0")
    total_ccf: Decimal = Decimal("0")
    total_sena: Decimal = Decimal("0")
    total_icbf: Decimal = Decimal("0")
    total_fsp: Decimal = Decimal("0")
    avisos: list = field(default_factory=list)

    @property
    def total_general(self) -> Decimal:
        return (self.total_pension + self.total_salud + self.total_arl +
                self.total_ccf + self.total_sena + self.total_icbf + self.total_fsp)

    @property
    def total_cotizantes(self) -> int:
        return len(self.detalles)


def _dec(valor, por_defecto="0") -> Decimal:
    if valor is None or valor == "":
        return Decimal(por_defecto)
    return Decimal(str(valor))


def _partir_nombre(nombre: str):
    """Reparte un nombre completo en los cuatro campos del registro tipo 2.

    Es un respaldo para los afiliados que todavía no tienen el nombre separado:
    con dos palabras asume nombre y apellido; con cuatro o más, dos y dos. Nunca
    va a ser perfecto —"MARÍA DEL CARMEN" no se parte bien— y por eso los campos
    separados existen en el modelo y mandan cuando están llenos.
    """
    partes = [p for p in (nombre or "").strip().upper().split() if p]
    if len(partes) >= 4:
        return partes[2], " ".join(partes[3:]), partes[0], partes[1]
    if len(partes) == 3:
        return partes[1], partes[2], partes[0], ""
    if len(partes) == 2:
        return partes[1], "", partes[0], ""
    return (partes[0] if partes else ""), "", "", ""


def dias_cotizados(afiliado, anio: int, mes: int) -> tuple:
    """Días del período y las novedades de ingreso o retiro que los explican.

    PILA cuenta sobre meses de 30 días. Un ingreso el día 10 deja 21 días
    cotizados (del 10 al 30), no los días naturales que queden de mes.
    """
    novedades, fechas = {}, {}
    dias = P.DIAS_MES_PILA

    def _parsear(valor):
        try:
            return date.fromisoformat(str(valor)[:10])
        except (ValueError, TypeError):
            return None

    ingreso = _parsear(getattr(afiliado, "fecha_ingreso", None))
    if ingreso and ingreso.year == anio and ingreso.month == mes:
        dia = min(ingreso.day, P.DIAS_MES_PILA)
        dias = P.DIAS_MES_PILA - dia + 1
        novedades["ING"] = "X"
        fechas["ING"] = ingreso.isoformat()

    return max(dias, 0), novedades, fechas


def _ibc(base: Decimal, dias: int, smlmv: Decimal) -> Decimal:
    """IBC proporcional a los días, con piso de 1 SMLMV y techo de 25.

    El piso también es proporcional: quien cotiza 15 días no puede quedar por
    debajo de medio salario mínimo, pero tampoco se le exige uno completo.
    """
    proporcional = base * Decimal(dias) / Decimal(P.DIAS_MES_PILA)
    piso = smlmv * Decimal(dias) / Decimal(P.DIAS_MES_PILA)
    techo = smlmv * P.TOPE_IBC_SMLMV
    return P.redondear_peso(min(max(proporcional, piso), techo))


def liquidar_afiliado(afiliado, aportante, anio: int, mes: int) -> DetalleLiquidado:
    """Calcula el registro de un cotizante. No toca la base de datos."""
    par = P.parametros(anio)
    smlmv = par.smlmv

    dias, novedades, fechas = dias_cotizados(afiliado, anio, mes)

    # El IBC individual manda sobre el salario básico; si no hay ninguno de los
    # dos se cae al mínimo, que es lo que aplica a la mayoría de independientes.
    base = _dec(getattr(afiliado, "ibc", None)) or _dec(getattr(afiliado, "salario_basico", None))
    if base <= 0:
        base = smlmv

    # El salario básico no es el IBC y va en su propio campo del registro tipo
    # 2. Se ven iguales en la mayoría de los casos, pero no lo son: en el plano
    # de referencia que el operador aceptó, el salario es 1.750.905 y el IBC de
    # pensión 58.364, porque el cotizante trabajó un día. Escribir el IBC aquí
    # hace que el archivo declare un salario que no es el del contrato.
    salario = _dec(getattr(afiliado, "salario_basico", None))
    if salario <= 0:
        salario = base

    ap_ap = afiliado.primer_apellido or ""
    if not ap_ap:
        ap_ap, ap_seg, nom_pri, nom_seg = _partir_nombre(getattr(afiliado, "nombre", ""))
    else:
        ap_seg = afiliado.segundo_apellido or ""
        nom_pri = afiliado.primer_nombre or ""
        nom_seg = afiliado.segundo_nombre or ""

    d = DetalleLiquidado(
        afiliado_id=getattr(afiliado, "id", None),
        tipo_doc=(afiliado.tipo_doc or "CC")[:2],
        doc=str(afiliado.doc or ""),
        primer_apellido=ap_ap, segundo_apellido=ap_seg,
        primer_nombre=nom_pri, segundo_nombre=nom_seg,
        tipo_cotizante=afiliado.tipo_cotizante or "01",
        subtipo_cotizante=afiliado.subtipo_cotizante or "",
        extranjero_no_pension=bool(getattr(afiliado, "extranjero_no_pension", False)),
        colombiano_exterior=bool(getattr(afiliado, "colombiano_exterior", False)),
        cod_depto_labor=afiliado.cod_depto_labor or aportante.cod_depto or "",
        cod_municipio_labor=afiliado.cod_municipio_labor or aportante.cod_municipio or "",
        cod_afp=afiliado.cod_afp or "", cod_eps=afiliado.cod_eps or "",
        cod_ccf=afiliado.cod_ccf or "",
        salario_basico=P.redondear_peso(salario),
        tipo_salario=(afiliado.tipo_salario or "F")[:1],
        centro_trabajo=afiliado.centro_trabajo or "",
        novedades=novedades, fechas_novedades=fechas,
        horas_laboradas=dias * 8,
        subactividad_economica=(getattr(aportante, "actividad_economica", "") or ""),
    )

    ibc = _ibc(base, dias, smlmv)

    # Lo contratado manda. `_servicios_afiliado` normaliza a EPS, AFP, CCF y
    # "ARL <clase>", y deduce la clase de riesgo del campo `arl` cuando no
    # viene marcada como servicio.
    servicios = _servicios_afiliado(afiliado)
    d.servicios = servicios
    contrata_salud = "EPS" in servicios
    contrata_pension = "AFP" in servicios
    contrata_caja = "CCF" in servicios

    # Las marcas de los campos 7 y 8 pesan mas que el servicio contratado. Un
    # extranjero no obligado a cotizar a pensiones cotiza a todo lo demas segun
    # su tipo de cotizante, pero de pension no se liquida nada: el anexo exige
    # dejar vacios los campos 19, 20, 28, 31, 32, 36, 42 y 46 al 53, que son
    # justo los que llena este bloque. Lo mismo con salud para el colombiano en
    # el exterior.
    # El subtipo del formulario dice lo que el tipo de cotizante no puede
    # decir: si esta persona cotiza a pension o no, mas alla de lo contratado.
    perfil = perfiles.perfil(getattr(afiliado, "subtipo", None))
    # "00" en la base significa "ninguno", no "el subtipo cero": sin normalizar,
    # el perfil nunca llegaba a aplicarse.
    if perfil.subtipo_cotizante and not obligaciones.normalizar_subtipo(d.subtipo_cotizante):
        d.subtipo_cotizante = perfil.subtipo_cotizante
    if perfil.extranjero_no_pension:
        d.extranjero_no_pension = True
    if perfil.obliga_pension:
        # Obligada a cotizar aunque no lo tenga contratado: es el unico caso
        # en que la liquidacion no sigue al formulario, y es a proposito.
        contrata_pension = True

    # El subtipo de cotizante (campo 6) exime igual que las marcas: un
    # dependiente ya pensionado, o con los requisitos cumplidos, sigue siendo
    # tipo 01 y no cotiza a pension. Sin esto no habia forma de liquidarlo.
    exentos = obligaciones.exenciones(
        d.subtipo_cotizante, d.extranjero_no_pension, d.colombiano_exterior)
    if "pension" in exentos:
        contrata_pension = False
        d.cod_afp = ""      # campo 31, tambien va vacio
    if "salud" in exentos:
        contrata_salud = False

    # El regimen exceptuado no se apaga: se reporta distinto. Dias e IBC de
    # pension van llenos con tarifa 0, y el Fondo de Solidaridad se paga desde
    # los 4 SMLMV, con FSP001 en el campo 31.
    exceptuado = obligaciones.es_regimen_exceptuado(d.subtipo_cotizante)
    if exceptuado:
        contrata_pension = False
    clase_contratada = next((s.split()[-1] for s in servicios if s.startswith("ARL")), None)

    # Pensión
    if contrata_pension:
        d.dias_pension = dias
        d.ibc_pension = ibc
        d.tarifa_pension = P.TARIFA_PENSION
        d.cot_pension = P.aproximar_aporte(ibc * P.TARIFA_PENSION)
        d.fsp_solidaridad, d.fsp_subsistencia = P.partir_fsp(ibc, smlmv)
    elif exceptuado:
        d.dias_pension = dias
        d.ibc_pension = ibc
        d.tarifa_pension = Decimal("0")
        d.fsp_solidaridad, d.fsp_subsistencia = P.partir_fsp(ibc, smlmv)
        d.cod_afp = (obligaciones.COD_FONDO_SOLIDARIDAD
                     if ibc >= smlmv * 4 else "")

    # Salud. La exoneración del artículo 114-1 quita la parte patronal a los
    # cotizantes por debajo de 10 SMLMV; el 4% del trabajador no se toca.
    if contrata_salud:
        d.dias_salud = dias
        d.ibc_salud = ibc
        exonera = bool(getattr(aportante, "exonerado_parafiscales", False)) and \
            ibc < smlmv * P.TOPE_EXONERACION_SMLMV
        d.exonerado = exonera
        d.tarifa_salud = P.TARIFA_SALUD_TRABAJADOR if exonera else P.TARIFA_SALUD
        d.cot_salud = P.aproximar_aporte(ibc * d.tarifa_salud)

    # Riesgos laborales: la tarifa sale de la clase de riesgo del afiliado y,
    # si no la tiene, de la del aportante.
    # Riesgos solo si está contratado. La clase sale del servicio ("ARL 3"); el
    # dato del afiliado o del aportante sirve de respaldo para saber cuál es,
    # nunca para decidir que se cotiza.
    clase = clase_contratada or (afiliado.clase_riesgo or
                                 getattr(aportante, "clase_riesgo", None)
                                 if clase_contratada else None)
    if clase_contratada and str(clase) in P.TARIFA_ARL_POR_CLASE:
        d.dias_arl = dias
        d.ibc_arl = ibc
        d.tarifa_arl = _dec(afiliado.tarifa_arl) or P.TARIFA_ARL_POR_CLASE[str(clase)]
        d.cot_arl = P.aproximar_aporte(ibc * d.tarifa_arl)
        d.clase_riesgo = str(clase)
        d.cod_arl = afiliado.cod_arl or getattr(aportante, "cod_arl", "") or ""

    # Parafiscales
    if contrata_caja:
        d.dias_ccf = dias
        d.ibc_ccf = ibc
        d.tarifa_ccf = P.TARIFA_CCF
        d.valor_ccf = P.aproximar_aporte(ibc * P.TARIFA_CCF)

    if contrata_caja and not d.exonerado:
        d.tarifa_sena = P.TARIFA_SENA
        d.valor_sena = P.aproximar_aporte(ibc * P.TARIFA_SENA)
        d.tarifa_icbf = P.TARIFA_ICBF
        d.valor_icbf = P.aproximar_aporte(ibc * P.TARIFA_ICBF)

    return d


def liquidar(afiliados, aportante, anio: int, mes: int) -> ResumenLiquidacion:
    """Liquida una lista de afiliados y suma los totales por subsistema."""
    resumen = ResumenLiquidacion(detalles=[])

    for af in afiliados:
        d = liquidar_afiliado(af, aportante, anio, mes)

        quien = f"{d.doc} {d.primer_nombre} {d.primer_apellido}".strip()

        # Sin servicios contratados no hay nada que liquidar.
        if not d.servicios:
            resumen.avisos.append(
                f"{quien}: no tiene servicios contratados, no se liquidó nada")

        # Un servicio contratado sin su código se liquida igual, pero el archivo
        # sale con ese campo en blanco y el operador lo va a rechazar.
        faltantes = [nombre for contrata, codigo, nombre in (
            ("EPS" in d.servicios, d.cod_eps, "EPS"),
            ("AFP" in d.servicios, d.cod_afp, "AFP"),
            ("CCF" in d.servicios, d.cod_ccf, "caja de compensación"),
        ) if contrata and not codigo]
        if faltantes:
            resumen.avisos.append(
                f"{quien}: tiene contratado {', '.join(faltantes)} pero le falta el "
                f"código. El archivo saldrá con ese campo vacío.")

        # Lo contratado manda para liquidar, pero el operador valida contra el
        # tipo de cotizante. Cuando los dos no coinciden el rechazo es seguro,
        # así que conviene decirlo aquí y no después de subir el archivo.
        # Se revisa lo que la planilla declara, no lo que el formulario dice:
        # es lo que el operador va a mirar.
        for choque in obligaciones.revisar(
                d.tipo_cotizante, obligaciones.liquidados(d),
                extranjero_no_pension=d.extranjero_no_pension,
                colombiano_exterior=d.colombiano_exterior,
                tipo_doc=d.tipo_doc,
                subtipo_cotizante=d.subtipo_cotizante):
            resumen.avisos.append(f"{quien}: {choque}")

        resumen.detalles.append(d)
        resumen.total_pension += d.cot_pension
        resumen.total_salud += d.cot_salud
        resumen.total_arl += d.cot_arl
        resumen.total_ccf += d.valor_ccf
        resumen.total_sena += d.valor_sena
        resumen.total_icbf += d.valor_icbf
        resumen.total_fsp += d.fsp_solidaridad + d.fsp_subsistencia

    return resumen
