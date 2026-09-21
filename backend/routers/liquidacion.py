"""Liquidación de planillas PILA.

Una planilla es de **una persona y un período**. Cada afiliado paga la suya,
con su propio número y su propio enlace de pago; no se liquida a toda la
empresa de una vez.

El aportante sigue apareciendo en el encabezado porque la planilla tipo E lo
exige, y se deduce del cliente del afiliado (`Afiliado.cliente_txt` contra
`AportantePila.cliente_ref`). Si ese cliente no tiene aportante cargado, la
liquidación se detiene y lo dice: sin NIT y dígito de verificación no hay
encabezado válido.

El flujo es previsualizar → liquidar → descargar. La previsualización no toca
la base. Liquidar congela el cálculo, incluida la línea exacta del registro
tipo 2, para que lo que se descargue sea lo que se reportó aunque el afiliado
cambie después.

No hay endpoint para editar una planilla liquidada: se anula y se vuelve a
liquidar, o se corrige con una planilla tipo N, que es como lo resuelve la
norma.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from database import get_db
from routers.deps import require_admin, require_admin_or_empleado
import const
import models, schemas
from crud_helpers import _log
from services.pila import (liquidacion as motor, obligaciones, operador,
                           perfiles, plano)

router = APIRouter(prefix="/liquidacion", tags=["liquidacion"])

ESTADOS_BORRABLES = {"borrador", "generada", "anulada"}

# Valores válidos del campo 3 del registro tipo 2 (tipo de documento del
# cotizante), tal como los lista el Anexo Técnico 2.
TIPOS_DOC_COTIZANTE = {"CC", "CE", "TI", "PA", "CD", "SC", "PE", "PT", "PC"}


def _periodo(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


def _mes_siguiente(anio: int, mes: int) -> str:
    return f"{anio + 1:04d}-01" if mes == 12 else f"{anio:04d}-{mes + 1:02d}"


def _mes_anterior(anio: int, mes: int) -> str:
    return f"{anio - 1:04d}-12" if mes == 1 else f"{anio:04d}-{mes - 1:02d}"


def _aviso_primera_planilla(db: Session, af, anio: int, mes: int) -> list:
    """Si esta persona no aparece en la planilla del mes anterior.

    El operador lo devuelve como advertencia: "no fue reportado en planillas
    pagadas del periodo anterior y no tiene marcada una novedad ingreso en
    esta planilla, por lo tanto, le sugerimos marcar esta novedad".

    No se marca sola. La novedad de ingreso lleva fecha y esa fecha entra a un
    documento con efectos legales; ponerle una inventada es peor que la
    advertencia. Se avisa para que alguien decida.
    """
    anterior = _mes_anterior(anio, mes)
    ya_estaba = (db.query(models.PlanillaLiquidacion)
                   .filter_by(afiliado_doc=af.doc, periodo_cotizacion=anterior)
                   .filter(models.PlanillaLiquidacion.estado != "anulada")
                   .first())
    if ya_estaba:
        return []
    ingreso = (getattr(af, "fecha_ingreso", "") or "")[:7]
    if ingreso == _periodo(anio, mes):
        return []      # ya entra con la novedad puesta por su fecha de ingreso
    return [f"{_nombre(af)}: no tiene planilla en {anterior}. El operador va a "
            f"sugerir que se marque la novedad de ingreso; si de verdad entró "
            f"antes, la advertencia se puede ignorar."]


def _afiliado_y_aportante(db: Session, afiliado_id: int):
    """El afiliado a liquidar y la empresa que va en su encabezado."""
    af = db.query(models.Afiliado).filter_by(id=afiliado_id).first()
    if not af:
        raise HTTPException(404, "Afiliado no encontrado")
    if not af.activo:
        raise HTTPException(400, f"{af.nombre} está retirado: no se le puede liquidar")

    ap = (db.query(models.AportantePila)
            .filter_by(cliente_ref=af.cliente_txt or "").first())
    if not ap:
        raise HTTPException(400, f"El cliente '{af.cliente_txt or '(sin cliente)'}' no tiene "
                                 f"aportante cargado. Créalo en Aportantes para poder "
                                 f"liquidar: la planilla necesita su NIT y dígito de "
                                 f"verificación en el encabezado.")
    return af, ap


def _nombre(af) -> str:
    partes = (af.primer_nombre, af.segundo_nombre, af.primer_apellido, af.segundo_apellido)
    completo = " ".join(x for x in partes if x)
    return completo or (af.nombre or "")


def _detalle_a_dict(d) -> dict:
    def _n(v):
        return int(v or 0)
    return {
        "doc": d.doc, "tipo_doc": d.tipo_doc,
        "nombre": " ".join(x for x in (d.primer_nombre, d.segundo_nombre,
                                       d.primer_apellido, d.segundo_apellido) if x),
        "tipo_cotizante": d.tipo_cotizante,
        "dias": d.dias_salud or d.dias_pension or d.dias_arl,
        "ibc": _n(d.ibc_salud or d.ibc_pension or d.ibc_arl),
        "cot_pension": _n(d.cot_pension), "cot_salud": _n(d.cot_salud),
        "cot_arl": _n(d.cot_arl), "valor_ccf": _n(d.valor_ccf),
        "valor_sena": _n(d.valor_sena), "valor_icbf": _n(d.valor_icbf),
        "fsp": _n(d.fsp_solidaridad + d.fsp_subsistencia),
        "exonerado": d.exonerado,
        "servicios": d.servicios,
        "novedades": list((d.novedades or {}).keys()),
        "total": _n(d.total),
    }


def _resumen_a_dict(resumen, af, ap, anio, mes) -> dict:
    return {
        "afiliado": {"id": af.id, "doc": af.doc, "tipo_doc": af.tipo_doc,
                     "nombre": _nombre(af), "cliente": af.cliente_txt},
        "aportante": {"id": ap.id, "razon_social": ap.razon_social,
                      "nit": f"{ap.num_doc}-{ap.dv}" if ap.dv else ap.num_doc,
                      "exonerado_parafiscales": bool(ap.exonerado_parafiscales)},
        "periodo_cotizacion": _periodo(anio, mes),
        "periodo_pago": _mes_siguiente(anio, mes),
        "totales": {
            "pension": int(resumen.total_pension), "salud": int(resumen.total_salud),
            "arl": int(resumen.total_arl), "ccf": int(resumen.total_ccf),
            "sena": int(resumen.total_sena), "icbf": int(resumen.total_icbf),
            "fsp": int(resumen.total_fsp), "general": int(resumen.total_general),
        },
        "avisos": resumen.avisos,
        "detalle": _detalle_a_dict(resumen.detalles[0]) if resumen.detalles else None,
    }


def _en_lotes(valores, tamano=400):
    """Parte una lista para no pasarse del limite de parametros de SQLite."""
    valores = list(valores)
    for i in range(0, len(valores), tamano):
        yield valores[i:i + tamano]


@router.get("/pendientes")
def pendientes(anio: int, mes: int, cliente: str = "", q: str = "",
               subtipo: str = "", tipo_cotizante: str = "", tipo_doc: str = "",
               aportante: str = "",
               db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    """A quien hay que liquidarle el periodo, segun las facturas de ese mes.

    El orden del trabajo es: primero se factura, despues se liquida. Por eso
    la lista sale de las facturas del periodo y no de los afiliados activos:
    si el mes no se ha facturado, aqui no hay nada que hacer todavia y la
    pantalla debe decirlo en vez de ofrecer a todo el mundo.

    Cada fila es una factura. Cuando su afiliado ya no esta —se elimino, o la
    factura quedo de alguien que se fue— la fila igual aparece, sin `id`, para
    que se vea que hay una factura sin con que liquidarla.
    """
    periodo = _periodo(anio, mes)

    # Facturacion guarda el mes por su nombre —"Septiembre"— y el año como
    # texto, no como numeros. Comparar contra enteros falla en Postgres con
    # "operator does not exist: character varying = integer", y en SQLite pasa
    # en silencio sin encontrar nada. Se aceptan tambien las formas numericas
    # por si quedan facturas viejas guardadas asi.
    nombres_mes = {const.MESES[mes - 1]} if 1 <= mes <= 12 else set()
    formas_mes = nombres_mes | {str(mes), f"{mes:02d}"}
    q_fact = db.query(models.Factura).filter(
        models.Factura.anio == str(anio),
        models.Factura.mes.in_(formas_mes))
    if cliente:
        q_fact = q_fact.filter(models.Factura.cliente == cliente)
    if aportante:
        # Por empresa, que es como se agrupa un archivo plano: el encabezado
        # lleva un solo aportante, asi que para juntar gente hay que poder
        # verla junta primero.
        valores = [v.strip() for v in aportante.split(",") if v.strip()]
        if valores:
            q_fact = q_fact.filter(models.Factura.cliente.in_(valores))
    facturas = q_fact.order_by(models.Factura.nombre_afiliado).limit(500).all()
    if not facturas:
        return []

    docs = {f.doc for f in facturas if f.doc}
    afiliados = {}
    for lote in _en_lotes(docs):
        for a in (db.query(models.Afiliado)
                    .filter(models.Afiliado.activo == True,            # noqa: E712
                            models.Afiliado.doc.in_(lote)).all()):
            afiliados[a.doc] = a

    liquidadas = {
        l.afiliado_doc: l
        for l in db.query(models.PlanillaLiquidacion)
                   .filter(models.PlanillaLiquidacion.periodo_cotizacion == periodo,
                           models.PlanillaLiquidacion.estado != "anulada").all()
    }

    def _pasa_filtros(f, a):
        """Los filtros miran al afiliado; sin afiliado solo queda el texto."""
        if q:
            patron = q.strip().lower()
            campos = [f.nombre_afiliado, f.doc, f.cliente]
            if a is not None:
                campos += [_nombre(a), a.doc, a.cliente_txt]
            if not any(patron in (v or "").lower() for v in campos):
                return False
        for valor, atributo, normalizar in (
            (subtipo, "subtipo", lambda v: v),
            (tipo_cotizante, "tipo_cotizante", lambda v: v.zfill(2)),
            (tipo_doc, "tipo_doc", lambda v: v.upper()),
        ):
            if not valor:
                continue
            if a is None:
                return False
            buscados = {normalizar(v.strip()) for v in valor.split(",") if v.strip()}
            if str(getattr(a, atributo, "") or "") not in buscados:
                return False
        return True

    filas = []
    for f in facturas:
        a = afiliados.get(f.doc)
        if not _pasa_filtros(f, a):
            continue
        l = liquidadas.get(f.doc)
        # El plano se congela al liquidar: si el afiliado cambio despues, el
        # archivo que se descargue lleva los datos viejos.
        desfasada = bool(l and l.creado and a is not None and a.actualizado
                         and a.actualizado > l.creado)
        filas.append({
            "id": getattr(a, "id", None),
            "doc": f.doc,
            "tipo_doc": getattr(a, "tipo_doc", None),
            "nombre": _nombre(a) if a is not None else f.nombre_afiliado,
            "cliente": getattr(a, "cliente_txt", None) or f.cliente,
            "tipo_cotizante": getattr(a, "tipo_cotizante", None),
            "subtipo": getattr(a, "subtipo", None),
            "sin_afiliado": a is None,
            "factura_codigo": f.codigo,
            "factura_estado": f.estado,
            "desactualizada": desfasada,
            # Los subtipos 20 y 22 se identifican ante el operador con cedula
            # de extranjeria. Se sugiere aqui para que el selector venga
            # puesto y no dependa de que alguien se acuerde.
            "tipo_doc_sugerido": (perfiles.documento_sugerido(a.subtipo, a.tipo_doc)
                                  if a is not None else ""),
            "planilla_id": getattr(l, "id", None),
            "estado": getattr(l, "estado", None),
            "total": int(l.total_general or 0) if l else None,
            "codigo_planilla": getattr(l, "planilla_corregida", None),
            "numero_planilla": getattr(l, "numero_planilla", None),
            "link_pago": getattr(l, "link_pago", None),
        })
    return filas


@router.post("/previsualizar")
def previsualizar(data: schemas.LiquidacionRequest, db: Session = Depends(get_db),
                  token=Depends(require_admin_or_empleado)):
    """Calcula sin guardar nada."""
    af, ap = _afiliado_y_aportante(db, data.afiliado_id)
    resumen = motor.liquidar([af], ap, data.anio, data.mes,
                            tipo_planilla=data.tipo_planilla)
    resumen.avisos.extend(_aviso_primera_planilla(db, af, data.anio, data.mes))
    return _resumen_a_dict(resumen, af, ap, data.anio, data.mes)


@router.post("", status_code=201)
def liquidar(data: schemas.LiquidacionRequest, db: Session = Depends(get_db),
             token=Depends(require_admin_or_empleado)):
    """Congela la liquidación de una persona para el período."""
    af, ap = _afiliado_y_aportante(db, data.afiliado_id)
    periodo = _periodo(data.anio, data.mes)

    ya = (db.query(models.PlanillaLiquidacion)
            .filter_by(afiliado_doc=af.doc, periodo_cotizacion=periodo)
            .filter(models.PlanillaLiquidacion.estado != "anulada").first())
    if ya:
        raise HTTPException(409, f"{_nombre(af)} ya tiene una planilla {ya.estado} "
                                 f"en {periodo}. Anúlala antes de volver a liquidar.")

    resumen = motor.liquidar([af], ap, data.anio, data.mes,
                            tipo_planilla=data.tipo_planilla)
    resumen.avisos.extend(_aviso_primera_planilla(db, af, data.anio, data.mes))
    d = resumen.detalles[0]

    liq = models.PlanillaLiquidacion(
        aportante_id=ap.id, cliente_ref=ap.cliente_ref,
        afiliado_id=af.id, afiliado_doc=af.doc, afiliado_nombre=_nombre(af),
        tipo_planilla=data.tipo_planilla, periodo_cotizacion=periodo,
        periodo_pago=_mes_siguiente(data.anio, data.mes),
        estado="generada", operador=data.operador,
        total_cotizantes=1,
        total_pension=resumen.total_pension, total_salud=resumen.total_salud,
        total_arl=resumen.total_arl, total_ccf=resumen.total_ccf,
        total_sena=resumen.total_sena, total_icbf=resumen.total_icbf,
        total_fsp=resumen.total_fsp, total_general=resumen.total_general,
        generado_por=token.get("sub", ""),
    )
    db.add(liq)
    db.flush()

    db.add(models.PlanillaDetalle(
        organizacion_id=liq.organizacion_id, liquidacion_id=liq.id,
        afiliado_id=d.afiliado_id, secuencia=1,
        tipo_doc=d.tipo_doc, doc=d.doc,
        primer_apellido=d.primer_apellido, segundo_apellido=d.segundo_apellido,
        primer_nombre=d.primer_nombre, segundo_nombre=d.segundo_nombre,
        tipo_cotizante=d.tipo_cotizante, subtipo_cotizante=d.subtipo_cotizante,
        cod_depto_labor=d.cod_depto_labor, cod_municipio_labor=d.cod_municipio_labor,
        cod_afp=d.cod_afp, cod_eps=d.cod_eps, cod_ccf=d.cod_ccf,
        dias_pension=d.dias_pension, dias_salud=d.dias_salud,
        dias_arl=d.dias_arl, dias_ccf=d.dias_ccf,
        salario_basico=d.salario_basico, tipo_salario=d.tipo_salario,
        ibc_pension=d.ibc_pension, ibc_salud=d.ibc_salud,
        ibc_arl=d.ibc_arl, ibc_ccf=d.ibc_ccf,
        tarifa_pension=d.tarifa_pension, cot_pension=d.cot_pension,
        total_pension=d.cot_pension,
        fsp_solidaridad=d.fsp_solidaridad, fsp_subsistencia=d.fsp_subsistencia,
        tarifa_salud=d.tarifa_salud, cot_salud=d.cot_salud,
        tarifa_arl=d.tarifa_arl, centro_trabajo=d.centro_trabajo, cot_arl=d.cot_arl,
        tarifa_ccf=d.tarifa_ccf, valor_ccf=d.valor_ccf,
        tarifa_sena=d.tarifa_sena, valor_sena=d.valor_sena,
        tarifa_icbf=d.tarifa_icbf, valor_icbf=d.valor_icbf,
        novedades=json.dumps(d.novedades or {}),
        fechas_novedades=json.dumps(d.fechas_novedades or {}),
        linea_plana=plano.registro_tipo_2(plano.valores_desde_detalle(d, 1)),
    ))

    db.commit()
    db.refresh(liq)
    _log(db, token.get("sub", ""), "liquidó planilla PILA", "Liquidación",
         f"{_nombre(af)} ({af.doc}) {periodo} — ${int(resumen.total_general):,}")
    db.commit()

    return {"id": liq.id, "estado": liq.estado,
            **_resumen_a_dict(resumen, af, ap, data.anio, data.mes)}


def _desactualizadas(db: Session, liquidaciones) -> set:
    """Las liquidaciones cuyo afiliado cambió después de liquidar.

    La línea del plano se congela al liquidar, que es lo correcto: el archivo
    que se manda tiene que ser el que se revisó. El problema es el silencio.
    Si alguien corrige el IBC o agrega un servicio y vuelve a descargar, baja
    el archivo viejo sin enterarse, lo sube al operador y recibe los mismos
    errores que creía haber corregido. Esto no cambia la congelación: solo la
    hace visible para que la pantalla pueda decir "vuelve a liquidar".
    """
    ids = {l.afiliado_id for l in liquidaciones if l.afiliado_id}
    if not ids:
        return set()
    cambios = dict(db.query(models.Afiliado.id, models.Afiliado.actualizado)
                     .filter(models.Afiliado.id.in_(ids)).all())
    return {l.id for l in liquidaciones
            if l.afiliado_id and l.creado and cambios.get(l.afiliado_id)
            and cambios[l.afiliado_id] > l.creado}


@router.get("")
def listar(cliente: str = "", periodo: str = "", doc: str = "", estado: str = "",
           db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    q = db.query(models.PlanillaLiquidacion)
    if cliente:
        q = q.filter(models.PlanillaLiquidacion.cliente_ref == cliente)
    if periodo:
        q = q.filter(models.PlanillaLiquidacion.periodo_cotizacion == periodo)
    if doc:
        q = q.filter(models.PlanillaLiquidacion.afiliado_doc == doc)
    if estado:
        q = q.filter(models.PlanillaLiquidacion.estado == estado)
    filas = q.order_by(models.PlanillaLiquidacion.id.desc()).limit(300).all()
    desfasadas = _desactualizadas(db, filas)
    return [{
        "desactualizada": l.id in desfasadas,
        "id": l.id, "afiliado_doc": l.afiliado_doc, "afiliado_nombre": l.afiliado_nombre,
        "cliente_ref": l.cliente_ref, "tipo_planilla": l.tipo_planilla,
        "periodo_cotizacion": l.periodo_cotizacion, "periodo_pago": l.periodo_pago,
        "estado": l.estado, "operador": l.operador,
        "numero_planilla": l.numero_planilla, "link_pago": l.link_pago,
        "total_general": int(l.total_general or 0),
        "generado_por": l.generado_por,
    } for l in filas]


def _liquidaciones_del_grupo(db: Session, ids: str):
    """Las liquidaciones de una lista de ids, validadas como conjunto.

    Se exige que estén vivas y que el orden de salida sea estable: el archivo
    numera los cotizantes de corrido, y si el orden cambiara entre la descarga
    y el envío, serían dos archivos distintos para la misma gente.
    """
    try:
        pedidos = [int(x) for x in str(ids).split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "Los ids tienen que ser números separados por coma")
    if not pedidos:
        raise HTTPException(400, "No se indicó ninguna liquidación")

    filas = (db.query(models.PlanillaLiquidacion)
               .filter(models.PlanillaLiquidacion.id.in_(pedidos))
               .order_by(models.PlanillaLiquidacion.afiliado_nombre).all())
    encontrados = {l.id for l in filas}
    faltan = [i for i in pedidos if i not in encontrados]
    if faltan:
        raise HTTPException(404, f"No se encontraron las liquidaciones: "
                                 f"{', '.join(map(str, faltan))}")
    anuladas = [l.afiliado_nombre for l in filas if l.estado == "anulada"]
    if anuladas:
        raise HTTPException(409, f"Hay planillas anuladas en la selección: "
                                 f"{', '.join(anuladas)}")
    return filas


@router.get("/plano-conjunto", response_class=PlainTextResponse)
def descargar_plano_conjunto(ids: str, tipo_doc: str = "", docs: str = "",
                             db: Session = Depends(get_db),
                             token=Depends(require_admin_or_empleado)):
    """Un solo archivo con varias personas de la misma empresa y período.

    Liquidar sigue siendo de a uno —cada quien con su detalle y su total—,
    pero el archivo que se sube al operador puede llevarlas juntas, que es
    como se presenta una nómina.
    """
    filas = _liquidaciones_del_grupo(db, ids)
    cuerpo, nombre, _ = _armar_plano(db, filas, tipo_doc, _documentos_pedidos(docs))
    return PlainTextResponse(
        cuerpo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/enviar-conjunto")
def enviar_conjunto(ids: str, tipo_archivo: str = "I", tipo_doc: str = "",
                    docs: str = "",
                    db: Session = Depends(get_db),
                    token=Depends(require_admin_or_empleado)):
    """Manda un archivo con varias personas y reparte la respuesta entre todas.

    El operador devuelve un solo código y un solo número para el archivo, así
    que ese resultado se escribe en cada una de las liquidaciones del grupo:
    todas quedan apuntando a la misma planilla, que es lo que de verdad pasó.
    """
    filas = _liquidaciones_del_grupo(db, ids)

    ya = [l.afiliado_nombre for l in filas if l.numero_planilla]
    if ya:
        raise HTTPException(409, f"Estas planillas ya fueron numeradas: "
                                 f"{', '.join(ya)}")

    # El mismo corte que en el envío individual: un código de administradora
    # vacío es error duro y deja un registro allá que después toca anular.
    for l in filas:
        for d in db.query(models.PlanillaDetalle).filter_by(liquidacion_id=l.id).all():
            faltan = obligaciones.codigos_faltantes(d)
            if faltan:
                raise HTTPException(
                    409, f"{l.afiliado_nombre} liquida {', '.join(faltan)} sin el "
                         f"código de la administradora. Complétalo en su ficha, "
                         f"vuelve a liquidar y envía.")

    cuerpo, nombre, ap = _armar_plano(db, filas, tipo_doc, _documentos_pedidos(docs))
    try:
        resultado = operador.enviar_planilla(
            cuerpo, nombre, ap.tipo_doc or "NI", ap.num_doc, tipo_archivo=tipo_archivo)
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))

    crudo = json.dumps(resultado, ensure_ascii=False, default=str)[:20000]
    for l in filas:
        l.respuesta_operador = crudo
        if resultado.get("simulado"):
            continue
        l.operador = l.operador or "suaporte"
        if resultado.get("numero_planilla"):
            l.numero_planilla = resultado["numero_planilla"][:20]
            l.estado = "numerada"
        elif resultado.get("errores"):
            l.estado = "inconsistente"
        else:
            l.estado = "enviada"
        if resultado.get("codigo_planilla"):
            l.planilla_corregida = resultado["codigo_planilla"][:20]
        if resultado.get("url_pago"):
            l.link_pago = resultado["url_pago"]
    db.commit()

    _log(db, token.get("sub", ""), "envió planilla conjunta al operador", "Liquidación",
         f"{ap.razon_social} {filas[0].periodo_cotizacion} — {len(filas)} cotizantes"
         + (" (simulación)" if resultado.get("simulado") else
            f" — N.º {filas[0].numero_planilla or 'sin número'}"))
    db.commit()

    return {"simulado": resultado.get("simulado", False),
            "cotizantes": len(filas),
            "estado": filas[0].estado,
            "codigo_planilla": resultado.get("codigo_planilla"),
            "numero_planilla": filas[0].numero_planilla,
            "link_pago": filas[0].link_pago,
            "errores": resultado.get("errores", []),
            "advertencias": resultado.get("advertencias", []),
            "totales": resultado.get("totales")}


@router.get("/{liquidacion_id}")
def obtener(liquidacion_id: int, db: Session = Depends(get_db),
            token=Depends(require_admin_or_empleado)):
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    detalles = (db.query(models.PlanillaDetalle)
                  .filter_by(liquidacion_id=l.id)
                  .order_by(models.PlanillaDetalle.secuencia).all())
    return {
        "id": l.id, "afiliado_doc": l.afiliado_doc, "afiliado_nombre": l.afiliado_nombre,
        "cliente_ref": l.cliente_ref, "tipo_planilla": l.tipo_planilla,
        "periodo_cotizacion": l.periodo_cotizacion, "periodo_pago": l.periodo_pago,
        "estado": l.estado, "operador": l.operador,
        "numero_planilla": l.numero_planilla, "link_pago": l.link_pago,
        "totales": {
            "pension": int(l.total_pension or 0), "salud": int(l.total_salud or 0),
            "arl": int(l.total_arl or 0), "ccf": int(l.total_ccf or 0),
            "sena": int(l.total_sena or 0), "icbf": int(l.total_icbf or 0),
            "fsp": int(l.total_fsp or 0), "general": int(l.total_general or 0),
        },
        "detalles": [{
            "secuencia": d.secuencia, "doc": d.doc, "tipo_doc": d.tipo_doc,
            "nombre": " ".join(x for x in (d.primer_nombre, d.segundo_nombre,
                                           d.primer_apellido, d.segundo_apellido) if x),
            "dias": d.dias_salud or d.dias_pension or d.dias_arl,
            "ibc": int(d.ibc_salud or d.ibc_pension or d.ibc_arl or 0),
            "cot_pension": int(d.cot_pension or 0), "cot_salud": int(d.cot_salud or 0),
            "cot_arl": int(d.cot_arl or 0), "valor_ccf": int(d.valor_ccf or 0),
            "valor_sena": int(d.valor_sena or 0), "valor_icbf": int(d.valor_icbf or 0),
            "fsp": int((d.fsp_solidaridad or 0) + (d.fsp_subsistencia or 0)),
        } for d in detalles],
    }


def _doc_del_afiliado(db: Session, liquidacion) -> str:
    """Con qué documento sale esta persona, si su subtipo pide uno distinto."""
    if not liquidacion.afiliado_id:
        return ""
    af = db.query(models.Afiliado).filter_by(id=liquidacion.afiliado_id).first()
    return perfiles.documento_sugerido(af.subtipo, af.tipo_doc) if af else ""


def _cambiar_documento(linea: str, tipo_doc: str) -> str:
    """El campo 3 son las posiciones 8 y 9. Se cambian esas dos y nada más."""
    return linea[:7] + tipo_doc.ljust(2)[:2] + linea[9:]


def _renumerar(linea: str, secuencia: int) -> str:
    """El campo 2 es la secuencia del cotizante dentro del archivo.

    Cada liquidación se guarda sola, así que todas traen la suya en 1. Al
    juntarlas en un archivo hay que numerarlas de corrido, o el operador ve
    varios cotizantes con la misma secuencia.
    """
    return linea[:2] + f"{secuencia:05d}" + linea[7:]


def _documentos_pedidos(docs: str) -> dict:
    """Interpreta "12:CE,13:CC" como {12: "CE", 13: "CC"}.

    Es el documento que se eligio para cada persona en la pantalla. En un
    archivo con varias no tiene por que ser el mismo para todas: una puede ir
    con cedula de extranjeria por su subtipo y el resto con la suya.
    """
    elegidos = {}
    for parte in str(docs or "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        if ":" not in parte:
            raise HTTPException(400, f"'{parte}' no tiene la forma id:DOCUMENTO")
        crudo_id, crudo_doc = parte.split(":", 1)
        try:
            elegidos[int(crudo_id)] = crudo_doc.strip().upper()
        except ValueError:
            raise HTTPException(400, f"'{crudo_id}' no es un id de liquidación")
    return elegidos


def _armar_plano(db: Session, liquidaciones, tipo_doc: str = "",
                 docs: dict = None) -> tuple:
    """El archivo plano de una o varias liquidaciones, y su nombre sugerido.

    Acepta una sola o una lista. Varias personas caben en un mismo archivo
    porque el registro tipo 2 se repite, pero el encabezado lleva un único
    aportante y un único período: solo se pueden juntar las de la misma
    empresa y el mismo mes. Eso no es decisión nuestra, es la forma del
    archivo.

    Las liquidaciones siguen siendo una por persona. Lo que se agrupa es el
    archivo, no la liquidación: cada quien conserva su detalle, su total y su
    rastro.

    El detalle no se recalcula: sale de la línea congelada al liquidar. Solo
    el encabezado se arma al vuelo, porque lleva los totales del conjunto.
    """
    if not isinstance(liquidaciones, (list, tuple)):
        liquidaciones = [liquidaciones]
    if not liquidaciones:
        raise HTTPException(400, "No hay liquidaciones para armar el archivo")

    if len({l.aportante_id for l in liquidaciones}) > 1:
        raise HTTPException(409, "Un archivo plano lleva un solo aportante en el "
                                 "encabezado: no se pueden juntar personas de "
                                 "empresas distintas")
    periodos = {l.periodo_cotizacion for l in liquidaciones}
    if len(periodos) > 1:
        raise HTTPException(409, "Un archivo plano lleva un solo período: "
                                 f"llegaron {', '.join(sorted(periodos))}")
    if len({l.tipo_planilla for l in liquidaciones}) > 1:
        raise HTTPException(409, "Todas las planillas del archivo tienen que ser "
                                 "del mismo tipo")

    primera = liquidaciones[0]
    ap = db.query(models.AportantePila).filter_by(id=primera.aportante_id).first()

    lineas, detalles_todos = [], []
    for l in liquidaciones:
        detalles = (db.query(models.PlanillaDetalle)
                      .filter_by(liquidacion_id=l.id)
                      .order_by(models.PlanillaDetalle.secuencia).all())
        detalles_todos.extend(detalles)

        # Manda lo que se eligio para esa persona; despues un documento
        # pedido para todo el archivo; y si no hay ninguno, lo decide su
        # subtipo. En un archivo con varias personas no tiene por que ser el
        # mismo para todas.
        doc = ((docs or {}).get(l.id) or tipo_doc
               or _doc_del_afiliado(db, l)).strip().upper()
        if doc and doc not in TIPOS_DOC_COTIZANTE:
            raise HTTPException(400, f"tipo_doc debe ser uno de: "
                                     f"{', '.join(sorted(TIPOS_DOC_COTIZANTE))}")
        for d in detalles:
            if not d.linea_plana:
                continue
            linea = _renumerar(d.linea_plana, len(lineas) + 1)
            lineas.append(_cambiar_documento(linea, doc) if doc else linea)

    forma, cod_sucursal, nombre_sucursal = plano.datos_sucursal(ap)
    periodo_otros, periodo_salud = plano.periodos_del_encabezado(primera.periodo_cotizacion)

    encabezado = plano.registro_tipo_1({
        "modalidad_planilla": 1, "secuencia": 1,
        "razon_social": ap.razon_social,
        "tipo_doc_aportante": ap.tipo_doc or "NI", "num_doc_aportante": ap.num_doc,
        "dv_aportante": ap.dv or 0, "tipo_planilla": primera.tipo_planilla,
        "planilla_asociada": 0, "fecha_planilla_asociada": "",
        "forma_presentacion": forma,
        "cod_sucursal": cod_sucursal, "nombre_sucursal": nombre_sucursal,
        "cod_arl": ap.cod_arl or "",
        "periodo_pago_otros": periodo_otros, "periodo_pago_salud": periodo_salud,
        # El número solo se escribe cuando el archivo es de una sola planilla:
        # un conjunto todavía no tiene número propio.
        "numero_planilla": (primera.numero_planilla or 0) if len(liquidaciones) == 1 else 0,
        "fecha_pago": primera.fecha_limite_pago or "",
        "total_cotizantes": len(lineas),
        "valor_total_nomina": int(sum((d.ibc_salud or d.ibc_pension or 0)
                                      for d in detalles_todos)),
        "tipo_aportante": ap.tipo_aportante or 1, "cod_operador": 0,
    })

    if len(liquidaciones) == 1:
        pedido = (docs or {}).get(primera.id) or tipo_doc
        sufijo = f"_{pedido.strip().upper()}" if pedido else ""
        nombre = (f"PILA_{primera.afiliado_doc or ap.num_doc}_"
                  f"{primera.periodo_cotizacion}_{primera.tipo_planilla}{sufijo}.txt")
    else:
        nombre = (f"PILA_{ap.num_doc}_{primera.periodo_cotizacion}_"
                  f"{primera.tipo_planilla}_{len(lineas)}cotizantes.txt")

    salto = chr(13) + chr(10)
    return salto.join([encabezado] + lineas) + salto, nombre, ap


@router.get("/{liquidacion_id}/plano", response_class=PlainTextResponse)
def descargar_plano(liquidacion_id: int, tipo_doc: str = "",
                    db: Session = Depends(get_db),
                    token=Depends(require_admin_or_empleado)):
    """El archivo plano de esa persona: encabezado más su registro tipo 2.

    `tipo_doc` baja el mismo plano identificando a la persona con otro
    documento —CE, PA, PT— sin volver a liquidar. Pasa cuando alguien quedó
    registrado con un documento en una administradora y con otro en el
    operador, y solo acepta el que tiene en sus bases.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    cuerpo, nombre, _ = _armar_plano(db, l, tipo_doc)
    return PlainTextResponse(
        cuerpo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/{liquidacion_id}/enviar")
def enviar_al_operador(liquidacion_id: int, tipo_archivo: str = "I",
                       tipo_doc: str = "",
                       db: Session = Depends(get_db),
                       token=Depends(require_admin_or_empleado)):
    """Manda la planilla al operador y guarda lo que responda.

    Sustituye el recorrido manual: descargar, entrar al portal, subir, revisar
    inconsistencias y volver por el enlace de pago.

    `tipo_doc` es el mismo del plano y por la misma razón: si la persona está
    en las bases del operador con otro documento, el envío tiene que salir con
    ese. Sin esto se podía descargar el archivo con CE y mandar CC, que es lo
    contrario de lo que se eligió.

    El cliente arranca en modo simulación y no sale a la red mientras
    `SUAPORTE_MODO` no sea "real": enviar crea un registro en el operador y el
    enlace de pago mueve dinero.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if l.estado == "anulada":
        raise HTTPException(409, "La planilla está anulada")
    if l.numero_planilla:
        raise HTTPException(409, f"Esta planilla ya fue enviada y quedó numerada "
                                 f"como {l.numero_planilla}")

    # Un codigo de administradora vacio es error duro para el operador, y
    # mandarlo igual deja un registro alla que despues toca anular. Se corta
    # aqui, que es donde todavia se puede arreglar.
    detalles = (db.query(models.PlanillaDetalle)
                  .filter_by(liquidacion_id=l.id).all())
    for d in detalles:
        faltan = obligaciones.codigos_faltantes(d)
        if faltan:
            raise HTTPException(
                409, f"{l.afiliado_nombre} liquida {', '.join(faltan)} sin el "
                     f"código de la administradora. Complétalo en su ficha, "
                     f"vuelve a liquidar y envía.")

    cuerpo, nombre, ap = _armar_plano(db, l, tipo_doc)

    try:
        resultado = operador.enviar_planilla(
            cuerpo, nombre, ap.tipo_doc or "NI", ap.num_doc, tipo_archivo=tipo_archivo)
    except operador.ErrorOperador as e:
        # El mensaje del operador es más útil que uno nuestro: se pasa tal cual.
        raise HTTPException(502, str(e))

    l.respuesta_operador = json.dumps(resultado, ensure_ascii=False, default=str)[:20000]
    if not resultado.get("simulado"):
        l.operador = l.operador or "suaporte"
        if resultado.get("numero_planilla"):
            l.numero_planilla = resultado["numero_planilla"][:20]
            l.estado = "numerada"
        elif resultado.get("errores"):
            # El operador recibió la planilla y le asignó código, pero no la
            # numera mientras tenga errores sin corregir.
            l.estado = "inconsistente"
        else:
            l.estado = "enviada"
        if resultado.get("codigo_planilla"):
            l.planilla_corregida = resultado["codigo_planilla"][:20]
        if resultado.get("url_pago"):
            l.link_pago = resultado["url_pago"]
    db.commit()

    _log(db, token.get("sub", ""), "envió planilla al operador", "Liquidación",
         f"{l.afiliado_nombre} {l.periodo_cotizacion}"
         + (" (simulación)" if resultado.get("simulado") else
            f" — N.º {l.numero_planilla or 'sin número'}"))
    db.commit()

    return {"simulado": resultado.get("simulado", False),
            "estado": l.estado,
            "codigo_planilla": resultado.get("codigo_planilla"),
            "numero_planilla": l.numero_planilla,
            "link_pago": l.link_pago,
            "errores": resultado.get("errores", []),
            "advertencias": resultado.get("advertencias", []),
            "totales": resultado.get("totales")}


@router.post("/{liquidacion_id}/corregir")
def corregir_en_el_operador(liquidacion_id: int, tipo_archivo: str = "I",
                            db: Session = Depends(get_db),
                            token=Depends(require_admin_or_empleado)):
    """Le pide al operador que corrija lo que él mismo marcó como corregible.

    Hay errores que el operador sabe arreglar y nosotros no: el código de
    actividad económica sale del anexo del Decreto 768, que no está en ninguna
    documentación pública que se pueda leer. Su validador sí lo tiene, así que
    conviene preguntárselo en vez de adivinar un código que cambiaría la tarifa
    de riesgos que se paga.

    Solo corrige errores, no advertencias: eso lo decide el operador, no
    nosotros.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if not l.planilla_corregida:
        raise HTTPException(409, "Esta planilla todavía no tiene código del "
                                 "operador: hay que enviarla antes de corregirla")

    ap = db.query(models.AportantePila).filter_by(id=l.aportante_id).first()
    try:
        resultado = operador.pedir_correccion(
            l.planilla_corregida, ap.tipo_doc or "NI", ap.num_doc,
            tipo_archivo=tipo_archivo)
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))

    l.respuesta_operador = json.dumps(resultado, ensure_ascii=False, default=str)[:20000]
    db.commit()

    _log(db, token.get("sub", ""), "pidió corrección al operador", "Liquidación",
         f"{l.afiliado_nombre} {l.periodo_cotizacion} — planilla {l.planilla_corregida}")
    db.commit()

    return {"simulado": resultado.get("simulado", False),
            "codigo_planilla": l.planilla_corregida,
            "inconsistencias": resultado.get("inconsistencias"),
            "totales": resultado.get("totales"),
            "url_pago": resultado.get("url_pago")}


@router.get("/operador/estado")
def estado_operador(token=Depends(require_admin_or_empleado)):
    """Si el envío al operador está configurado y en qué modo.

    Lo consulta la pantalla para no ofrecer un botón que no va a funcionar.
    """
    return {"modo": "real" if operador.modo_real() else "simulacion",
            "credenciales": operador.hay_credenciales()}


@router.post("/{liquidacion_id}/pago")
def refrescar_pago(liquidacion_id: int, db: Session = Depends(get_db),
                   token=Depends(require_admin_or_empleado)):
    """Vuelve a pedirle al operador el enlace de pago y los totales.

    Sirve después de corregir inconsistencias: el enlace sigue siendo el mismo
    trámite, pero los totales cambian cuando el operador ajusta la liquidación.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    referencia = l.numero_planilla or l.planilla_corregida
    if not referencia:
        raise HTTPException(409, "Esta planilla todavía no se ha enviado al operador")

    ap = db.query(models.AportantePila).filter_by(id=l.aportante_id).first()
    try:
        with operador._cliente_nuevo() as cliente:
            sesion = operador.autenticar(cliente)
            datos = operador.consultar_aportante(sesion, ap.tipo_doc or "NI",
                                                 ap.num_doc, cliente)
            operador.autorizar(sesion, ap.tipo_doc or "NI", ap.num_doc, cliente,
                               aportante_id=datos.get("id"))
            enlace = operador.url_pago(sesion, referencia, cliente)
            resumen = operador.totales(sesion, referencia, cliente)
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))

    if enlace:
        l.link_pago = enlace
        db.commit()
    return {"link_pago": l.link_pago, "totales": resumen, "referencia": referencia}


@router.post("/{liquidacion_id}/anular")
def anular(liquidacion_id: int, db: Session = Depends(get_db),
           token=Depends(require_admin_or_empleado)):
    """Anula para poder volver a liquidar. No se borra: queda el rastro."""
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if l.estado == "pagada":
        raise HTTPException(409, "Una planilla pagada no se anula: corrígela con una "
                                 "planilla tipo N")
    l.estado = "anulada"
    db.commit()
    _log(db, token.get("sub", ""), "anuló planilla PILA", "Liquidación",
         f"{l.afiliado_nombre} {l.periodo_cotizacion}")
    db.commit()
    return {"ok": True, "estado": l.estado}


@router.delete("/{liquidacion_id}")
def eliminar(liquidacion_id: int, db: Session = Depends(get_db),
             token=Depends(require_admin)):
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if l.estado not in ESTADOS_BORRABLES:
        raise HTTPException(409, f"No se puede borrar una planilla en estado '{l.estado}'")
    desc = f"{l.afiliado_nombre} {l.periodo_cotizacion}"
    # El detalle se borra explícitamente: la FK es ON DELETE CASCADE, pero
    # SQLite solo la aplica con PRAGMA foreign_keys=ON y en dev quedaría
    # huérfano. Borrarlo aquí funciona igual en las dos bases.
    db.query(models.PlanillaDetalle).filter_by(liquidacion_id=l.id).delete()
    db.delete(l)
    db.commit()
    _log(db, token.get("sub", ""), "eliminó planilla PILA", "Liquidación", desc)
    db.commit()
    return {"ok": True}
