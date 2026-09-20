"""Liquidación de planillas PILA.

El flujo es: previsualizar → liquidar → descargar el archivo plano.

La previsualización no toca la base. Liquidar congela el cálculo en
`planillas_liquidacion` + `planillas_detalle`, incluida la línea exacta del
registro tipo 2 de cada cotizante: si mañana el afiliado cambia de EPS, la
planilla ya liquidada debe seguir mostrando y exportando lo que se reportó.

No existe endpoint para editar una planilla liquidada. Para corregir se anula y
se vuelve a liquidar, o se genera una planilla tipo N de correcciones — que es
como lo resuelve la norma, no editando lo ya reportado.
"""
from datetime import date
from decimal import Decimal
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

ESTADOS_EDITABLES = {"borrador", "generada"}


def _afiliados_del_aportante(db: Session, aportante: models.AportantePila):
    return (db.query(models.Afiliado)
              .filter(models.Afiliado.cliente_txt == aportante.cliente_ref,
                      models.Afiliado.activo == True)      # noqa: E712
              .order_by(models.Afiliado.primer_apellido, models.Afiliado.nombre)
              .all())


def _periodo(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


def _mes_siguiente(anio: int, mes: int) -> str:
    return f"{anio + 1:04d}-01" if mes == 12 else f"{anio:04d}-{mes + 1:02d}"


def _detalle_a_dict(d) -> dict:
    """Un DetalleLiquidado en JSON, con los valores como número entero de pesos."""
    def _n(v):
        return int(v or 0)
    return {
        "doc": d.doc, "tipo_doc": d.tipo_doc,
        "nombre": " ".join(x for x in (d.primer_nombre, d.segundo_nombre,
                                       d.primer_apellido, d.segundo_apellido) if x),
        "tipo_cotizante": d.tipo_cotizante,
        "dias": d.dias_salud or d.dias_pension or d.dias_arl,
        "ibc": _n(d.ibc_salud or d.ibc_pension or d.ibc_arl),
        "cot_pension": _n(d.cot_pension),
        "cot_salud": _n(d.cot_salud),
        "cot_arl": _n(d.cot_arl),
        "valor_ccf": _n(d.valor_ccf),
        "valor_sena": _n(d.valor_sena),
        "valor_icbf": _n(d.valor_icbf),
        "fsp": _n(d.fsp_solidaridad + d.fsp_subsistencia),
        "exonerado": d.exonerado,
        "novedades": list((d.novedades or {}).keys()),
        "total": _n(d.total),
    }


def _resumen_a_dict(resumen, aportante, anio, mes) -> dict:
    return {
        "aportante": {"id": aportante.id, "razon_social": aportante.razon_social,
                      "nit": f"{aportante.num_doc}-{aportante.dv}" if aportante.dv
                             else aportante.num_doc,
                      "exonerado_parafiscales": bool(aportante.exonerado_parafiscales)},
        "periodo_cotizacion": _periodo(anio, mes),
        "periodo_pago": _mes_siguiente(anio, mes),
        "total_cotizantes": resumen.total_cotizantes,
        "totales": {
            "pension": int(resumen.total_pension), "salud": int(resumen.total_salud),
            "arl": int(resumen.total_arl), "ccf": int(resumen.total_ccf),
            "sena": int(resumen.total_sena), "icbf": int(resumen.total_icbf),
            "fsp": int(resumen.total_fsp), "general": int(resumen.total_general),
        },
        "avisos": resumen.avisos,
        "detalles": [_detalle_a_dict(d) for d in resumen.detalles],
    }


@router.post("/previsualizar")
def previsualizar(data: schemas.LiquidacionRequest, db: Session = Depends(get_db),
                  token=Depends(require_admin_or_empleado)):
    """Calcula sin guardar nada. Sirve para revisar antes de liquidar."""
    ap = db.query(models.AportantePila).filter_by(id=data.aportante_id).first()
    if not ap:
        raise HTTPException(404, "Aportante no encontrado")

    afiliados = _afiliados_del_aportante(db, ap)
    if not afiliados:
        raise HTTPException(400, f"El aportante '{ap.cliente_ref}' no tiene afiliados "
                                 f"activos que liquidar")

    resumen = motor.liquidar(afiliados, ap, data.anio, data.mes)
    return _resumen_a_dict(resumen, ap, data.anio, data.mes)


@router.post("", status_code=201)
def liquidar(data: schemas.LiquidacionRequest, db: Session = Depends(get_db),
             token=Depends(require_admin_or_empleado)):
    """Congela la liquidación del período."""
    ap = db.query(models.AportantePila).filter_by(id=data.aportante_id).first()
    if not ap:
        raise HTTPException(404, "Aportante no encontrado")

    periodo = _periodo(data.anio, data.mes)
    ya = (db.query(models.PlanillaLiquidacion)
            .filter_by(aportante_id=ap.id, periodo_cotizacion=periodo)
            .filter(models.PlanillaLiquidacion.estado != "anulada").first())
    if ya:
        raise HTTPException(409, f"Ya hay una planilla {ya.estado} para {ap.cliente_ref} "
                                 f"en {periodo}. Anúlala antes de volver a liquidar.")

    afiliados = _afiliados_del_aportante(db, ap)
    if not afiliados:
        raise HTTPException(400, f"El aportante '{ap.cliente_ref}' no tiene afiliados activos")

    resumen = motor.liquidar(afiliados, ap, data.anio, data.mes)

    liq = models.PlanillaLiquidacion(
        aportante_id=ap.id, cliente_ref=ap.cliente_ref,
        tipo_planilla=data.tipo_planilla, periodo_cotizacion=periodo,
        periodo_pago=_mes_siguiente(data.anio, data.mes),
        estado="generada", operador=data.operador,
        total_cotizantes=resumen.total_cotizantes,
        total_pension=resumen.total_pension, total_salud=resumen.total_salud,
        total_arl=resumen.total_arl, total_ccf=resumen.total_ccf,
        total_sena=resumen.total_sena, total_icbf=resumen.total_icbf,
        total_fsp=resumen.total_fsp, total_general=resumen.total_general,
        generado_por=token.get("sub", ""),
    )
    db.add(liq)
    db.flush()          # necesita id para los detalles

    for i, d in enumerate(resumen.detalles, start=1):
        linea = plano.registro_tipo_2(plano.valores_desde_detalle(d, i))
        db.add(models.PlanillaDetalle(
            organizacion_id=liq.organizacion_id, liquidacion_id=liq.id,
            afiliado_id=d.afiliado_id, secuencia=i,
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
            linea_plana=linea,
        ))

    db.commit()
    db.refresh(liq)
    _log(db, token.get("sub", ""), "liquidó planilla PILA", "Liquidación",
         f"{ap.cliente_ref} {periodo} — {resumen.total_cotizantes} cotizantes, "
         f"${int(resumen.total_general):,}")
    db.commit()

    return {"id": liq.id, "periodo_cotizacion": periodo, "estado": liq.estado,
            **_resumen_a_dict(resumen, ap, data.anio, data.mes)}


@router.get("")
def listar(cliente: str = "", anio: str = "", estado: str = "",
           db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    q = db.query(models.PlanillaLiquidacion)
    if cliente:
        q = q.filter(models.PlanillaLiquidacion.cliente_ref == cliente)
    if anio:
        q = q.filter(models.PlanillaLiquidacion.periodo_cotizacion.like(f"{anio}-%"))
    if estado:
        q = q.filter(models.PlanillaLiquidacion.estado == estado)
    filas = q.order_by(models.PlanillaLiquidacion.id.desc()).limit(300).all()
    return [{
        "id": l.id, "cliente_ref": l.cliente_ref, "tipo_planilla": l.tipo_planilla,
        "periodo_cotizacion": l.periodo_cotizacion, "periodo_pago": l.periodo_pago,
        "estado": l.estado, "operador": l.operador,
        "numero_planilla": l.numero_planilla, "link_pago": l.link_pago,
        "total_cotizantes": l.total_cotizantes,
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
        "id": l.id, "cliente_ref": l.cliente_ref, "tipo_planilla": l.tipo_planilla,
        "periodo_cotizacion": l.periodo_cotizacion, "periodo_pago": l.periodo_pago,
        "estado": l.estado, "operador": l.operador,
        "numero_planilla": l.numero_planilla, "link_pago": l.link_pago,
        "totales": {
            "pension": int(l.total_pension or 0), "salud": int(l.total_salud or 0),
            "arl": int(l.total_arl or 0), "ccf": int(l.total_ccf or 0),
            "sena": int(l.total_sena or 0), "icbf": int(l.total_icbf or 0),
            "fsp": int(l.total_fsp or 0), "general": int(l.total_general or 0),
        },
        "total_cotizantes": l.total_cotizantes,
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
def descargar_plano(liquidacion_id: int, db: Session = Depends(get_db),
                    token=Depends(require_admin_or_empleado)):
    """El archivo plano, armado desde las líneas congeladas al liquidar.

    No se recalcula: se devuelve exactamente lo que se reportó. Solo el
    encabezado se arma al vuelo, porque lleva los totales de la cabecera.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    ap = db.query(models.AportantePila).filter_by(id=l.aportante_id).first()
    detalles = (db.query(models.PlanillaDetalle)
                  .filter_by(liquidacion_id=l.id)
                  .order_by(models.PlanillaDetalle.secuencia).all())

    encabezado = plano.registro_tipo_1({
        "modalidad_planilla": 1, "secuencia": 1,
        "razon_social": ap.razon_social,
        "tipo_doc_aportante": ap.tipo_doc or "NI", "num_doc_aportante": ap.num_doc,
        "dv_aportante": ap.dv or 0, "tipo_planilla": l.tipo_planilla,
        "planilla_asociada": 0, "fecha_planilla_asociada": "",
        "forma_presentacion": "U",
        "cod_sucursal": ap.cod_sucursal or "", "nombre_sucursal": ap.nombre_sucursal or "",
        "cod_arl": ap.cod_arl or "",
        "periodo_pago_otros": l.periodo_cotizacion, "periodo_pago_salud": l.periodo_pago,
        "numero_planilla": l.numero_planilla or 0,
        "fecha_pago": l.fecha_limite_pago or "",
        "total_cotizantes": l.total_cotizantes or 0,
        "valor_total_nomina": int(sum((d.ibc_salud or d.ibc_pension or 0) for d in detalles)),
        "tipo_aportante": ap.tipo_aportante or 1, "cod_operador": 0,
    })

    cuerpo = "\r\n".join([encabezado] + [d.linea_plana for d in detalles if d.linea_plana])
    nombre = f"PILA_{ap.num_doc}_{l.periodo_cotizacion}_{l.tipo_planilla}.txt"
    return PlainTextResponse(
        cuerpo + "\r\n",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/{liquidacion_id}/anular")
def anular(liquidacion_id: int, db: Session = Depends(get_db),
           token=Depends(require_admin_or_empleado)):
    """Anula una planilla para poder volver a liquidar el período.

    No se borra: queda como rastro de que existió y de lo que decía.
    """
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if l.estado == "pagada":
        raise HTTPException(409, "Una planilla pagada no se anula: corrígela con una "
                                 "planilla tipo N")
    l.estado = "anulada"
    db.commit()
    _log(db, token.get("sub", ""), "anuló planilla PILA", "Liquidación",
         f"{l.cliente_ref} {l.periodo_cotizacion}")
    db.commit()
    return {"ok": True, "estado": l.estado}


@router.delete("/{liquidacion_id}")
def eliminar(liquidacion_id: int, db: Session = Depends(get_db),
             token=Depends(require_admin)):
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    if l.estado not in ESTADOS_EDITABLES and l.estado != "anulada":
        raise HTTPException(409, f"No se puede borrar una planilla en estado '{l.estado}'")
    desc = f"{l.cliente_ref} {l.periodo_cotizacion}"
    db.delete(l)          # los detalles caen por CASCADE
    db.commit()
    _log(db, token.get("sub", ""), "eliminó planilla PILA", "Liquidación", desc)
    db.commit()
    return {"ok": True}
