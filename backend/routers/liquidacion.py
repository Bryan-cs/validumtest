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
import models, schemas
from crud_helpers import _log
from services.pila import liquidacion as motor, plano

router = APIRouter(prefix="/liquidacion", tags=["liquidacion"])

ESTADOS_BORRABLES = {"borrador", "generada", "anulada"}

# Valores válidos del campo 3 del registro tipo 2 (tipo de documento del
# cotizante), tal como los lista el Anexo Técnico 2.
TIPOS_DOC_COTIZANTE = {"CC", "CE", "TI", "PA", "CD", "SC", "PE", "PT"}


def _periodo(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


def _mes_siguiente(anio: int, mes: int) -> str:
    return f"{anio + 1:04d}-01" if mes == 12 else f"{anio:04d}-{mes + 1:02d}"


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


@router.get("/pendientes")
def pendientes(anio: int, mes: int, cliente: str = "", q: str = "",
               db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    """Afiliados activos y si ya tienen planilla en el período.

    Es lo que alimenta el buscador de la pantalla: liquidar es de a uno, pero
    hay que poder ver de un vistazo a quién le falta el mes.
    """
    periodo = _periodo(anio, mes)

    consulta = db.query(models.Afiliado).filter(models.Afiliado.activo == True)  # noqa: E712
    if cliente:
        consulta = consulta.filter(models.Afiliado.cliente_txt == cliente)
    if q:
        patron = f"%{q}%"
        consulta = consulta.filter(models.Afiliado.nombre.ilike(patron) |
                                   models.Afiliado.doc.ilike(patron))
    afiliados = consulta.order_by(models.Afiliado.nombre).limit(500).all()

    liquidadas = {
        l.afiliado_doc: l
        for l in db.query(models.PlanillaLiquidacion)
                   .filter(models.PlanillaLiquidacion.periodo_cotizacion == periodo,
                           models.PlanillaLiquidacion.estado != "anulada").all()
    }

    return [{
        "id": a.id, "doc": a.doc, "tipo_doc": a.tipo_doc,
        "nombre": _nombre(a), "cliente": a.cliente_txt,
        "tipo_cotizante": a.tipo_cotizante,
        "planilla_id": liquidadas[a.doc].id if a.doc in liquidadas else None,
        "estado": liquidadas[a.doc].estado if a.doc in liquidadas else None,
        "total": int(liquidadas[a.doc].total_general or 0) if a.doc in liquidadas else None,
    } for a in afiliados]


@router.post("/previsualizar")
def previsualizar(data: schemas.LiquidacionRequest, db: Session = Depends(get_db),
                  token=Depends(require_admin_or_empleado)):
    """Calcula sin guardar nada."""
    af, ap = _afiliado_y_aportante(db, data.afiliado_id)
    resumen = motor.liquidar([af], ap, data.anio, data.mes)
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

    resumen = motor.liquidar([af], ap, data.anio, data.mes)
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
    return [{
        "id": l.id, "afiliado_doc": l.afiliado_doc, "afiliado_nombre": l.afiliado_nombre,
        "cliente_ref": l.cliente_ref, "tipo_planilla": l.tipo_planilla,
        "periodo_cotizacion": l.periodo_cotizacion, "periodo_pago": l.periodo_pago,
        "estado": l.estado, "operador": l.operador,
        "numero_planilla": l.numero_planilla, "link_pago": l.link_pago,
        "total_general": int(l.total_general or 0),
        "generado_por": l.generado_por,
    } for l in filas]


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

    El detalle no se recalcula, sale de la línea congelada al liquidar.

    `tipo_doc` baja el mismo plano identificando a la persona con otro
    documento —CE, PA, PT— sin volver a liquidar. Pasa cuando alguien quedó
    registrado con un documento en una administradora y con otro en el
    operador, y solo acepta el que tiene en sus bases.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    ap = db.query(models.AportantePila).filter_by(id=l.aportante_id).first()
    detalles = (db.query(models.PlanillaDetalle)
                  .filter_by(liquidacion_id=l.id)
                  .order_by(models.PlanillaDetalle.secuencia).all())

    forma, cod_sucursal, nombre_sucursal = plano.datos_sucursal(ap)
    periodo_otros, periodo_salud = plano.periodos_del_encabezado(l.periodo_cotizacion)
    encabezado = plano.registro_tipo_1({
        "modalidad_planilla": 1, "secuencia": 1,
        "razon_social": ap.razon_social,
        "tipo_doc_aportante": ap.tipo_doc or "NI", "num_doc_aportante": ap.num_doc,
        "dv_aportante": ap.dv or 0, "tipo_planilla": l.tipo_planilla,
        "planilla_asociada": 0, "fecha_planilla_asociada": "",
        "forma_presentacion": forma,
        "cod_sucursal": cod_sucursal, "nombre_sucursal": nombre_sucursal,
        "cod_arl": ap.cod_arl or "",
        "periodo_pago_otros": periodo_otros, "periodo_pago_salud": periodo_salud,
        "numero_planilla": l.numero_planilla or 0,
        "fecha_pago": l.fecha_limite_pago or "",
        "total_cotizantes": l.total_cotizantes or len(detalles),
        "valor_total_nomina": int(sum((d.ibc_salud or d.ibc_pension or 0) for d in detalles)),
        "tipo_aportante": ap.tipo_aportante or 1, "cod_operador": 0,
    })

    lineas_detalle = [d.linea_plana for d in detalles if d.linea_plana]

    if tipo_doc:
        tipo_doc = tipo_doc.strip().upper()
        if tipo_doc not in TIPOS_DOC_COTIZANTE:
            raise HTTPException(400, f"tipo_doc debe ser uno de: "
                                     f"{', '.join(sorted(TIPOS_DOC_COTIZANTE))}")
        # El campo 3 son las posiciones 8 y 9 del registro tipo 2. Se cambian
        # esas dos y nada mas: los valores liquidados quedan intactos.
        lineas_detalle = [x[:7] + tipo_doc.ljust(2) + x[9:] for x in lineas_detalle]

    cuerpo = "\r\n".join([encabezado] + lineas_detalle)
    sufijo = f"_{tipo_doc}" if tipo_doc else ""
    nombre = (f"PILA_{l.afiliado_doc or ap.num_doc}_{l.periodo_cotizacion}"
              f"_{l.tipo_planilla}{sufijo}.txt")
    return PlainTextResponse(
        cuerpo + "\r\n",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


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
