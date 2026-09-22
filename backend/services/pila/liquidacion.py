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


def _servicios_crudos(afiliado) -> list:
    """Los servicios tal como se guardaron, sin lo que deduce el normalizador."""
    crudo = getattr(afiliado, "servicios", None)
    if isinstance(crudo, (list, tuple)):
        return list(crudo)
    try:
        import json as _json
        datos = _json.loads(crudo or "[]")
        return list(datos) if isinstance(datos, list) else []
    except (ValueError, TypeError):
        return []


def dias_cotizados(afiliado, anio: int, mes: int, dias_facturados=None) -> tuple:
    """Días del período y las novedades de ingreso o retiro que los explican.

    PILA cuenta sobre meses de 30 días. Un ingreso el día 10 deja 21 días
    cotizados (del 10 al 30), no los días naturales que queden de mes.

    `dias_facturados` son los de la factura del período, que es lo que el
    cliente contrató y pagó. Mandan sobre el cálculo por fecha de ingreso:
    si se facturaron 15 días, la planilla declara 15. Sin esto se facturaba
    medio mes y se liquidaba el mes entero.
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

    if dias_facturados is not None:
        try:
            facturados = int(dias_facturados)
        except (TypeError, ValueError):
            facturados = None
        if facturados is not None and 0 < facturados <= P.DIAS_MES_PILA:
            dias = facturados

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


def _codigo_administradora(afiliado, tipo: str, nombre: str, codigo: str) -> str:
    """El código que va al plano sale del nombre de la ficha.

    ADRES y el formulario escriben "Famisanar". El archivo necesita EPS017.
    `cod_eps` puede seguir en EPS037 de un guardado anterior: si el nombre
    resuelve, ese código viejo no se manda.
    """
    from services.pila.catalogos import buscar_codigo
    hallado = buscar_codigo(tipo, getattr(afiliado, nombre, "") or "")
    if hallado:
        return hallado
    return getattr(afiliado, codigo, "") or ""


def liquidar_afiliado(afiliado, aportante, anio: int, mes: int,
                     dias_facturados=None) -> DetalleLiquidado:
    """Calcula el registro de un cotizante. No toca la base de datos."""
    par = P.parametros(anio)
    smlmv = par.smlmv

    dias, novedades, fechas = dias_cotizados(afiliado, anio, mes, dias_facturados)

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
        cod_afp=_codigo_administradora(afiliado, "AFP", "afp", "cod_afp"),
        cod_eps=_codigo_administradora(afiliado, "EPS", "eps", "cod_eps"),
        cod_ccf=_codigo_administradora(afiliado, "CCF", "ccf", "cod_ccf"),
        salario_basico=P.redondear_peso(salario),
        tipo_salario=(afiliado.tipo_salario or "F")[:1],
        centro_trabajo=afiliado.centro_trabajo or "",
        novedades=novedades, fechas_novedades=fechas,
        horas_laboradas=dias * 8,
        # La actividad del afiliado manda: su primer dígito es la clase de
        # riesgo, y la del aportante solo sirve para quien comparta la suya.
        subactividad_economica=(getattr(afiliado, "actividad_economica", "") or ""
                                or getattr(aportante, "actividad_economica", "") or ""),
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
    # Riesgos se decide sobre los servicios tal como se guardaron, no sobre la
    # lista normalizada. `_servicios_afiliado` agrega ARL cuando el campo `arl`
    # de la ficha trae una clase, aunque el servicio no este contratado: eso le
    # sirve a Cobro, donde la clase vive en su propio campo, pero aqui haria
    # que alguien con solo EPS contratada liquidara riesgos igual.
    #
    # La clase si sale de la lista normalizada, que es la que sabe leerla de
    # los dos sitios. Lo que no puede venir de ahi es la decision de cotizar.
    contrata_riesgos = any("ARL" in str(x).upper()
                           for x in _servicios_crudos(afiliado))
    clase_contratada = (next((s.split()[-1] for s in servicios
                              if s.startswith("ARL")), None)
                        if contrata_riesgos else None)

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
        # La exoneración del 114-1 no aplica a cualquier tipo de cotizante: el
        # operador rechaza la marca en los que no están en su lista.
        exonera = (bool(getattr(aportante, "exonerado_parafiscales", False))
                   and ibc < smlmv * P.TOPE_EXONERACION_SMLMV
                   and obligaciones.admite_exoneracion(d.tipo_cotizante))
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
    else:
        # Sin riesgos contratados, pero afiliado a una ARL: se reporta la
        # afiliacion con sus dias e IBC y la tarifa en cero. El archivo dice
        # "esta afiliado, este mes no hay aporte", que es cierto, y satisface
        # tres reglas que el operador exige juntas:
        #
        #   819  los dias de riesgos no pueden ser 0
        #   283  los dias de salud y riesgos deben ser iguales
        #   691  los IBC de salud y riesgos deben ser iguales
        #
        # Sin esto, alguien con salud y caja pero sin riesgos no podia generar
        # una planilla que el operador aceptara. Es lo mismo que hace el
        # sistema con el que se contrasto.
        #
        # Solo cuando hay afiliacion de verdad en la ficha: inventar una ARL
        # para que cuadren los dias seria otra cosa.
        cod_arl = afiliado.cod_arl or getattr(aportante, "cod_arl", "") or ""
        clase_afiliacion = str(afiliado.clase_riesgo or
                               getattr(aportante, "clase_riesgo", "") or "")
        # La ARL es de la empresa. Si el código está y la clase no, se usa la
        # 1: sin eso los días de riesgos quedan en 0, la caja no se declara y
        # el departamento sale en blanco. Pasa en cualquier empresa a la que
        # no se le haya cargado la clase, con la misma ficha.
        if cod_arl and clase_afiliacion not in P.TARIFA_ARL_POR_CLASE:
            clase_afiliacion = "1"
        if cod_arl and clase_afiliacion in P.TARIFA_ARL_POR_CLASE and dias:
            # Tarifa 0 en tipo 01 solo la acepta el operador si el campo 27
            # trae L (licencia remunerada), igual que el plano de ARUS que
            # cobra ARL en $0. Sin esa marca rechaza los campos 381-389.
            d.dias_arl = dias
            d.ibc_arl = ibc
            d.tarifa_arl = Decimal("0")
            d.cot_arl = Decimal("0")
            d.clase_riesgo = "1"
            d.cod_arl = cod_arl
            if not d.novedades.get("VAC"):
                d.novedades["VAC"] = "L"

    # Parafiscales. Si CCF está contratada se cotiza sobre el IBC real
    # (mínimo 1 SMLMV). Si no, se declara caja con IBC 100 como los planos
    # de ARUS que el operador acepta: días y tarifa llenos, aporte mínimo.
    if contrata_caja:
        _llenar_ccf(d, dias, ibc, token=False, afiliado=afiliado)
    elif _debe_declarar_caja_sin_contrato(d):
        _llenar_ccf(d, dias, ibc, token=True, afiliado=afiliado)

    if contrata_caja and not d.exonerado:
        d.tarifa_sena = P.TARIFA_SENA
        d.valor_sena = P.aproximar_aporte(ibc * P.TARIFA_SENA)
        d.tarifa_icbf = P.TARIFA_ICBF
        d.valor_icbf = P.aproximar_aporte(ibc * P.TARIFA_ICBF)

    _alinear_actividad_con_la_clase(d)
    _depurar_campos_del_tipo(d)
    _garantizar_novedad_de_ingreso(d, anio, mes)
    return d


def _llenar_ccf(d: DetalleLiquidado, dias: int, ibc: Decimal, token: bool,
                afiliado=None) -> None:
    base = P.IBC_CCF_SIN_CONTRATO if token else ibc
    d.dias_ccf = dias
    d.ibc_ccf = base
    d.tarifa_ccf = P.TARIFA_CCF
    d.valor_ccf = P.aproximar_aporte(base * P.TARIFA_CCF)
    from services.pila.catalogos import buscar_codigo, caja_cubre_depto, sede_de_caja
    if not (d.cod_ccf or "").strip():
        hallado = buscar_codigo("CCF", getattr(afiliado, "ccf", "") or "")
        if hallado:
            d.cod_ccf = hallado
    # Sin caja contratada: COMCAJA (CCF68) en 99/773, como el plano de ARUS.
    # Con caja en la ficha se reporta esa (Colsubsidio, Compensar). Si el
    # departamento de labor no la cubre, se mueve el DANE a uno que sí, en
    # vez de cambiar la caja por COMCAJA.
    if token or not (d.cod_ccf or "").strip():
        d.cod_ccf = P.COD_CCF_SIN_CONTRATO
        d.cod_depto_labor = P.DEPTO_CCF_SIN_CONTRATO
        d.cod_municipio_labor = P.MUN_CCF_SIN_CONTRATO
    elif not caja_cubre_depto(d.cod_ccf, d.cod_depto_labor):
        depto, mun = sede_de_caja(d.cod_ccf)
        if depto:
            d.cod_depto_labor = depto
            d.cod_municipio_labor = mun
        else:
            d.cod_ccf = P.COD_CCF_SIN_CONTRATO
            d.cod_depto_labor = P.DEPTO_CCF_SIN_CONTRATO
            d.cod_municipio_labor = P.MUN_CCF_SIN_CONTRATO


def _alinear_actividad_con_la_clase(d: DetalleLiquidado) -> None:
    """El primer dígito del código del Decreto 768 es la clase de riesgo.

    La empresa tiene un solo CIIU (1661401, 1620101). Si la ficha cotiza ARL 4,
    el archivo no puede salir con clase 4 y un código que empieza por 1: el
    operador lo rechaza en cualquier empresa. Se deja el CIIU y el adicional,
    y el primer dígito pasa a ser la clase que esta línea reporta.
    """
    codigo = (d.subactividad_economica or "").strip()
    clase = (d.clase_riesgo or "").strip()
    if (len(codigo) == 7 and codigo.isdigit() and clase in "12345"
            and codigo[0] != clase):
        d.subactividad_economica = clase + codigo[1:]


def _debe_declarar_caja_sin_contrato(d: DetalleLiquidado) -> bool:
    """Si hay que poner caja en el plano aunque no esté contratada.

    Solo en los tipos que el operador obliga a los tres subsistemas juntos.
    Un estudiante o un independiente no se inventan caja: en ellos faltaría
    a propósito y mandarla sería otro rechazo.
    """
    if not d.dias_salud or not d.dias_arl:
        return False
    reglas = obligaciones.reglas_de(d.tipo_cotizante)
    return bool(reglas) and reglas[3] == obligaciones.OBLIGATORIO


def _garantizar_novedad_de_ingreso(d: DetalleLiquidado, anio: int, mes: int) -> None:
    """Un período parcial tiene que decir por qué lo es.

    Si la planilla declara menos de 30 días y no trae ninguna novedad que lo
    explique, el operador pregunta por la de ingreso. Hoy los días solo se
    reducen por la fecha de ingreso, que ya marca la novedad; esto es la red
    para cualquier otro camino que termine con un período parcial.

    La fecha sale de los días declarados, no se inventa: si se cotizan 20 de
    30 días, el primero cotizado es el 11. Se recorta al último día real del
    mes porque PILA cuenta sobre meses de 30 pero la fecha tiene que existir.
    """
    dias = max(d.dias_salud, d.dias_pension, d.dias_arl, d.dias_ccf)
    if not dias or dias >= P.DIAS_MES_PILA:
        return
    if d.novedades.get("ING") or d.novedades.get("RET"):
        return

    d.novedades["ING"] = "X"
    if not d.fechas_novedades.get("ING"):
        import calendar
        dia = min(P.DIAS_MES_PILA - dias + 1, calendar.monthrange(anio, mes)[1])
        d.fechas_novedades["ING"] = date(anio, mes, dia).isoformat()


def _depurar_campos_del_tipo(d: DetalleLiquidado) -> None:
    """Vacía los campos que el tipo de cotizante no admite.

    Son campos que se llenan sin pensar —el tipo de salario, las horas— y que
    para ciertos tipos de cotizante el operador devuelve como error. Se limpian
    al final, cuando ya está decidido todo lo demás, en vez de repartir la
    condición por cada bloque.
    """
    if not obligaciones.admite_tipo_salario(d.tipo_cotizante):
        d.tipo_salario = ""

    # Las horas laboradas van con el aporte a caja: el operador avisa cuando
    # hay horas reportadas y no hay aportes a CCF.
    if not obligaciones.admite_horas(d.tipo_cotizante) or not d.dias_ccf:
        d.horas_laboradas = 0

    # El codigo de una administradora solo va cuando se le cotiza. Dejarlo
    # puesto con cero dias dice que hay aporte a ese subsistema y no lo hay,
    # y el operador reclama que los dias no cuadran. La AFP ya se vaciaba en
    # los casos exentos; esto lo vuelve general para los tres.
    for dias, codigo in (("dias_salud", "cod_eps"),
                         ("dias_pension", "cod_afp"),
                         ("dias_ccf", "cod_ccf")):
        if not getattr(d, dias, 0):
            setattr(d, codigo, "")


def liquidar(afiliados, aportante, anio: int, mes: int,
             tipo_planilla: str = "E", dias_facturados=None) -> ResumenLiquidacion:
    """Liquida una lista de afiliados y suma los totales por subsistema."""
    resumen = ResumenLiquidacion(detalles=[])

    for af in afiliados:
        d = liquidar_afiliado(af, aportante, anio, mes, dias_facturados)

        quien = f"{d.doc} {d.primer_nombre} {d.primer_apellido}".strip()

        # Los grupos que se tramitan por fuera se liquidan igual, para poder
        # ver los numeros y bajar el archivo, pero conviene decirlo aqui.
        if not perfiles.se_envia_al_operador(getattr(af, "subtipo", None)):
            resumen.avisos.append(
                f"{quien}: este grupo se tramita por fuera. La planilla se puede "
                f"descargar, pero el envío al operador está cortado.")

        # Aqui toda persona lleva salud. Sin EPS la ficha esta a medio llenar.
        for choque in perfiles.revisar_salud_contratada(d.servicios):
            resumen.avisos.append(f"{quien}: {choque}")

        # Sin servicios contratados no hay nada que liquidar.
        if not d.servicios:
            resumen.avisos.append(
                f"{quien}: no tiene servicios contratados, no se liquidó nada")

        # Un servicio contratado sin su código se liquida igual, pero el archivo
        # sale con ese campo en blanco y el operador lo va a rechazar.
        faltantes = obligaciones.codigos_faltantes(d)
        if faltantes:
            resumen.avisos.append(
                f"{quien}: la planilla liquida {', '.join(faltantes)} pero no tiene "
                f"el código de la administradora. El operador lo rechaza como error, "
                f"no como advertencia: complétalo antes de enviar.")

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
                subtipo_cotizante=d.subtipo_cotizante,
                tipo_planilla=tipo_planilla):
            resumen.avisos.append(f"{quien}: {choque}")

        # Y si ese tipo de cotizante cabe en este tipo de planilla, que es un
        # rechazo que el operador no autocorrige.
        for choque in obligaciones.revisar_planilla(d.tipo_cotizante, tipo_planilla):
            resumen.avisos.append(f"{quien}: {choque}")

        for choque in obligaciones.revisar_actividad(d):
            resumen.avisos.append(f"{quien}: {choque}")

        for choque in obligaciones.revisar_subsistemas_parejos(d, tipo_planilla):
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
