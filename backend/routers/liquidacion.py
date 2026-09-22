"""Liquidación de planillas PILA.

Una planilla es de **una persona y un período**. Cada afiliado paga la suya,
con su propio número y su propio enlace de pago; no se liquida a toda la
empresa de una vez.

El aportante sigue apareciendo en el encabezado porque la planilla tipo E lo
exige, y se deduce de la empresa de la ficha (`Afiliado.empresa` contra
`AportantePila.cliente_ref`). `cliente_txt` es a quien se le cobra, no quien
cotiza. Si esa empresa no tiene aportante cargado, la liquidación se detiene
y lo dice: sin NIT y dígito de verificación no hay encabezado válido.

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
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import get_db
from routers.deps import require_admin, require_admin_or_empleado
from routers.credenciales import credenciales_de_aportante
import const
import models, schemas
from crud_helpers import _log, _servicios_afiliado
from services.pila import (liquidacion as motor, obligaciones, operador,
                           perfiles, plano)
from services.pila.archivo import (
    TIPOS_DOC_COTIZANTE,
    armar_plano as _armar_plano,
    documentos_pedidos as _documentos_pedidos,
)

router = APIRouter(prefix="/liquidacion", tags=["liquidacion"])

ESTADOS_BORRABLES = {"borrador", "generada", "anulada"}


def _creds(db: Session, ap) -> tuple | None:
    """Las de esa empresa en Credenciales, o None para caer al entorno."""
    if ap is None:
        return None
    return credenciales_de_aportante(db, getattr(ap, "num_doc", "") or "")


def _periodo(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


def _mes_siguiente(anio: int, mes: int) -> str:
    return f"{anio + 1:04d}-01" if mes == 12 else f"{anio:04d}-{mes + 1:02d}"


def _mes_anterior(anio: int, mes: int) -> str:
    return f"{anio - 1:04d}-12" if mes == 1 else f"{anio:04d}-{mes - 1:02d}"


def _dias_facturados(db: Session, af, anio: int, mes: int):
    """Los dias que dice la factura del periodo, si la hay.

    Facturacion los guarda en `periodo`, y son los que el cliente contrato y
    pago. Sin mirarlos se facturaba medio mes y se liquidaba el mes entero.
    """
    nombres_mes = {const.MESES[mes - 1]} if 1 <= mes <= 12 else set()
    factura = (db.query(models.Factura)
                 .filter(models.Factura.doc == af.doc,
                         models.Factura.anio == str(anio),
                         models.Factura.mes.in_(nombres_mes | {str(mes), f"{mes:02d}"}))
                 .first())
    return getattr(factura, "periodo", None) if factura else None


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

    # La empresa de la ficha es quien va en el encabezado. cliente_txt es el
    # cliente al que se le cobra. Si no hay aportante con el nombre de la
    # empresa, se intenta el cliente.
    ref = (af.empresa or "").strip() or (af.cliente_txt or "").strip()
    ap = (db.query(models.AportantePila).filter_by(cliente_ref=ref).first()
          if ref else None)
    if not ap and (af.cliente_txt or "").strip() and (af.cliente_txt or "").strip() != ref:
        ap = (db.query(models.AportantePila)
                .filter_by(cliente_ref=af.cliente_txt.strip()).first())
    if not ap:
        raise HTTPException(400, f"La empresa '{ref or '(sin empresa)'}' no tiene "
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
    periodo = _periodo(anio, mes)
    periodo_pension, periodo_salud = plano.periodos_del_encabezado(periodo)
    return {
        "afiliado": {"id": af.id, "doc": af.doc, "tipo_doc": af.tipo_doc,
                     "nombre": _nombre(af), "cliente": af.cliente_txt},
        "aportante": {"id": ap.id, "razon_social": ap.razon_social,
                      "nit": f"{ap.num_doc}-{ap.dv}" if ap.dv else ap.num_doc,
                      "exonerado_parafiscales": bool(ap.exonerado_parafiscales)},
        "periodo_cotizacion": periodo,
        "periodo_pago": _mes_siguiente(anio, mes),
        "periodo_pension": periodo_pension,
        "periodo_salud": periodo_salud,
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


# Lo que Facturacion guarda en Factura.estado. "pagado" es cuando el cliente
# ya entrego el dinero; "planilla_pagada" es un paso posterior.
_ESTADOS_FACTURA = {"pendiente", "pagado", "planilla_pagada"}


@router.get("/pendientes")
def pendientes(anio: int, mes: int, cliente: str = "", q: str = "",
               subtipo: str = "", tipo_cotizante: str = "", tipo_doc: str = "",
               aportante: str = "", estado_factura: str = "pagado",
               db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    """A quien hay que liquidarle el periodo, segun las facturas de ese mes.

    El orden del trabajo es: primero se factura, el cliente paga, y recien
    ahi se liquida la planilla. Por defecto solo entran las facturas en
    estado pagado. `estado_factura=todos` (o pendiente, o planilla_pagada)
    deja ver el resto sin meterlas al trabajo de liquidar.

    Cada fila es una factura. Cuando su afiliado ya no esta —se elimino, o la
    factura quedo de alguien que se fue— la fila igual aparece, sin `id`, para
    que se vea que hay una factura sin con que liquidarla.
    """
    estado_factura = (estado_factura or "pagado").strip().lower()
    if estado_factura != "todos" and estado_factura not in _ESTADOS_FACTURA:
        raise HTTPException(400, "estado_factura debe ser pagado, pendiente, "
                                  "planilla_pagada o todos")
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
    if estado_factura != "todos":
        q_fact = q_fact.filter(models.Factura.estado == estado_factura)
    facturas = q_fact.order_by(models.Factura.nombre_afiliado).limit(5000).all()
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
                campos += [_nombre(a), a.doc, a.cliente_txt, a.empresa]
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
            "empresa": getattr(a, "empresa", None) or "",
            "tipo_cotizante": getattr(a, "tipo_cotizante", None),
            "subtipo": getattr(a, "subtipo", None),
            "servicios": _servicios_afiliado(a) if a is not None else [],
            "sin_afiliado": a is None,
            "factura_codigo": f.codigo,
            "factura_estado": f.estado,
            "desactualizada": desfasada,
            # Los subtipos 20 y 22 se identifican ante el operador con cedula
            # de extranjeria. Se sugiere aqui para que el selector venga
            # puesto y no dependa de que alguien se acuerde.
            "tipo_doc_sugerido": (perfiles.documento_sugerido(a.subtipo, a.tipo_doc)
                                  if a is not None else ""),
            # Los grupos que se tramitan por fuera se ven, se liquidan y se
            # descargan, pero no se envian desde aqui.
            "se_envia": (perfiles.se_envia_al_operador(a.subtipo)
                         if a is not None else False),
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
                            tipo_planilla=data.tipo_planilla,
                            dias_facturados=_dias_facturados(db, af, data.anio, data.mes))
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
                            tipo_planilla=data.tipo_planilla,
                            dias_facturados=_dias_facturados(db, af, data.anio, data.mes))
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


def _corta_si_no_se_envia(db: Session, liquidaciones):
    """Detiene el envio de los grupos que se tramitan por fuera.

    Se comprueba aqui y no solo en la pantalla: el boton se puede esconder,
    pero el endpoint sigue existiendo y un envio equivocado deja un registro
    en el operador que despues toca anular.
    """
    fuera = []
    for l in liquidaciones:
        af = (db.query(models.Afiliado).filter_by(id=l.afiliado_id).first()
              if l.afiliado_id else None)
        if af and not perfiles.se_envia_al_operador(af.subtipo):
            fuera.append(f"{l.afiliado_nombre} (subtipo {af.subtipo})")
    if fuera:
        raise HTTPException(
            409, f"Estas planillas no se envían desde aquí, se tramitan por "
                 f"fuera: {', '.join(fuera)}. El archivo se puede descargar.")


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
async def enviar_conjunto(ids: str, tipo_archivo: str = "I", tipo_doc: str = "",
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

    _corta_si_no_se_envia(db, filas)
    cuerpo, nombre, ap = _armar_plano(db, filas, tipo_doc, _documentos_pedidos(docs))
    try:
        resultado = await run_in_threadpool(
            operador.enviar_planilla,
            cuerpo, nombre, ap.tipo_doc or "NI", ap.num_doc,
            tipo_archivo, _creds(db, ap))
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))

    crudo = json.dumps(resultado, ensure_ascii=False, default=str)[:20000]
    for l in filas:
        l.respuesta_operador = crudo
        if resultado.get("simulado"):
            continue
        l.operador = l.operador or operador.operador_nombre()
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
            "planilla_id": filas[0].id,
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


@router.get("/{liquidacion_id}/comprobante")
async def descargar_comprobante(liquidacion_id: int,
                          db: Session = Depends(get_db),
                          token=Depends(require_admin_or_empleado)):
    """El recibo que emite el operador después de pagar, no el plano tipo 1/2."""
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if not l.numero_planilla:
        raise HTTPException(409, "Esta planilla todavía no tiene número del "
                                 "operador: hay que enviarla y pagarla antes")
    ap = db.query(models.AportantePila).filter_by(id=l.aportante_id).first()
    if not ap:
        raise HTTPException(409, "No hay aportante para pedir el comprobante")
    try:
        cuerpo, tipo, nombre = await run_in_threadpool(
            operador.traer_comprobante,
            l.numero_planilla, ap.tipo_doc or "NI", ap.num_doc, _creds(db, ap))
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))
    return Response(
        content=cuerpo, media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/{liquidacion_id}/enviar")
async def enviar_al_operador(liquidacion_id: int, tipo_archivo: str = "I",
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

    _corta_si_no_se_envia(db, [l])
    cuerpo, nombre, ap = _armar_plano(db, l, tipo_doc)

    try:
        resultado = await run_in_threadpool(
            operador.enviar_planilla,
            cuerpo, nombre, ap.tipo_doc or "NI", ap.num_doc,
            tipo_archivo, _creds(db, ap))
    except operador.ErrorOperador as e:
        # El mensaje del operador es más útil que uno nuestro: se pasa tal cual.
        raise HTTPException(502, str(e))

    l.respuesta_operador = json.dumps(resultado, ensure_ascii=False, default=str)[:20000]
    if not resultado.get("simulado"):
        l.operador = l.operador or operador.operador_nombre()
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
async def corregir_en_el_operador(liquidacion_id: int, tipo_archivo: str = "I",
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
        resultado = await run_in_threadpool(
            operador.pedir_correccion,
            l.planilla_corregida, ap.tipo_doc or "NI", ap.num_doc,
            tipo_archivo, _creds(db, ap))
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))

    l.respuesta_operador = json.dumps(resultado, ensure_ascii=False, default=str)[:20000]
    leido = {}
    if isinstance(resultado.get("respuesta"), dict):
        leido = operador.interpretar_validacion(resultado["respuesta"])
    numero = (leido.get("numero_planilla") or "")[:20]
    url = resultado.get("url_pago") or ""
    if isinstance(url, dict):
        url = url.get("url") or url.get("urlPago") or ""
    # Un envío de varias comparte el mismo código: la corrección es de esa
    # planilla, así que el número y el enlace quedan en todas.
    grupo = (db.query(models.PlanillaLiquidacion)
               .filter_by(planilla_corregida=l.planilla_corregida).all())
    for fila in grupo or [l]:
        fila.respuesta_operador = l.respuesta_operador
        if numero:
            fila.numero_planilla = numero
            fila.estado = "numerada"
        if isinstance(url, str) and url:
            fila.link_pago = url
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
def estado_operador(num_doc: str = "", db: Session = Depends(get_db),
                    token=Depends(require_admin_or_empleado)):
    """Si el envío al operador está configurado y en qué modo.

    Lo consulta la pantalla para no ofrecer un botón que no va a funcionar.
    Con `num_doc` dice si esa empresa tiene clave propia o cae a la global.
    """
    propias = credenciales_de_aportante(db, num_doc) if num_doc else None
    return {"modo": "real" if operador.modo_real() else "simulacion",
            "credenciales": operador.hay_credenciales(propias),
            "operador": operador.operador_nombre(),
            "origen": "empresa" if propias else "entorno"}


@router.post("/{liquidacion_id}/pago")
async def refrescar_pago(liquidacion_id: int, db: Session = Depends(get_db),
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
    enlace = ""
    resumen = None
    try:
        with operador._cliente_nuevo() as cliente:
            sesion = operador.autenticar(cliente, creds=_creds(db, ap))
            datos = operador.consultar_aportante(sesion, ap.tipo_doc or "NI",
                                                 ap.num_doc, cliente)
            operador.autorizar(sesion, ap.tipo_doc or "NI", ap.num_doc, cliente,
                               aportante_id=datos.get("id"))
            enlace = operador.enlace_de_pago(
                sesion, l.planilla_corregida or "", l.numero_planilla or "", cliente)
            try:
                resumen = operador.totales(
                    sesion, l.planilla_corregida or l.numero_planilla, cliente)
            except operador.ErrorOperador:
                resumen = None
    except operador.ErrorOperador as e:
        raise HTTPException(502, str(e))

    if not enlace:
        raise HTTPException(502, "El operador no entregó el enlace de pago. "
                                 "Si la planilla sigue con errores, corrígela primero.")
    l.link_pago = enlace
    db.commit()
    return {"link_pago": l.link_pago, "totales": resumen,
            "referencia": l.planilla_corregida or l.numero_planilla}


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
