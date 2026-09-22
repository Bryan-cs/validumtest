"""El mes de PILA antes y después de enviar.

Cierre, rechazos del operador, novedades, conciliación de pagos y la
diferencia entre la ficha y la última consulta. Nada de esto reescribe
afiliados ni vuelve a liquidar una planilla ya enviada.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import const
import models
from database import get_db
from routers.deps import require_admin_or_empleado
from services.pila import liquidacion as motor
from services.pila.operacion import (
    accion_de_avisos, accion_rechazo, explicar_monto, mismo_nombre,
    nivel_de_avisos, nota_caja_minima,
)

router = APIRouter(prefix="/operacion", tags=["operacion"])

_TOPE = 400


def _periodo(anio: int, mes: int) -> str:
    if not 1 <= mes <= 12:
        raise HTTPException(400, "mes inválido")
    return f"{anio:04d}-{mes:02d}"


def _formas_mes(mes: int) -> set:
    return {const.MESES[mes - 1], str(mes), f"{mes:02d}"}


def _aportante_de(db, af):
    ref = (getattr(af, "empresa", None) or "").strip() or (af.cliente_txt or "").strip()
    ap = db.query(models.AportantePila).filter_by(cliente_ref=ref).first() if ref else None
    if not ap and (af.cliente_txt or "").strip() and (af.cliente_txt or "").strip() != ref:
        ap = db.query(models.AportantePila).filter_by(cliente_ref=af.cliente_txt.strip()).first()
    return ap, ref


@router.get("/cierre")
def cierre(anio: int, mes: int, db: Session = Depends(get_db),
           token=Depends(require_admin_or_empleado)):
    """Facturas pagadas del mes que todavía no tienen planilla, con semáforo."""
    periodo = _periodo(anio, mes)
    facturas = (db.query(models.Factura)
                .filter(models.Factura.anio == str(anio),
                        models.Factura.mes.in_(_formas_mes(mes)),
                        models.Factura.estado == "pagado")
                .order_by(models.Factura.nombre_afiliado)
                .limit(_TOPE).all())
    docs = {f.doc for f in facturas if f.doc}
    afiliados = {}
    if docs:
        for a in (db.query(models.Afiliado)
                  .filter(models.Afiliado.activo == True,  # noqa: E712
                          models.Afiliado.doc.in_(docs)).all()):
            afiliados[a.doc] = a
    con_planilla = {
        l.afiliado_doc for l in db.query(models.PlanillaLiquidacion)
        .filter(models.PlanillaLiquidacion.periodo_cotizacion == periodo,
                models.PlanillaLiquidacion.estado != "anulada").all()
        if l.afiliado_doc
    }

    filas, cuentas = [], {"rojo": 0, "amarillo": 0, "listo": 0}
    for f in facturas:
        if f.doc in con_planilla:
            continue
        a = afiliados.get(f.doc)
        avisos = []
        if a is None:
            avisos = [f"{f.nombre_afiliado or f.doc}: no está en el sistema"]
        else:
            ap, ref = _aportante_de(db, a)
            if not ap:
                avisos = [f"{a.nombre}: la empresa '{ref or '(sin empresa)'}' no tiene aportante"]
            else:
                resumen = motor.liquidar([a], ap, anio, mes)
                avisos = list(resumen.avisos)
                d = resumen.detalles[0] if resumen.detalles else None
                if d is not None:
                    caja = nota_caja_minima(d.ibc_ccf)
                    if caja:
                        avisos.append(caja)
        nivel = nivel_de_avisos(avisos)
        cuentas[nivel] += 1
        filas.append({
            "doc": f.doc,
            "nombre": (a.nombre if a is not None else f.nombre_afiliado) or "",
            "empresa": getattr(a, "empresa", None) or f.cliente or "",
            "factura": f.codigo,
            "afiliado_id": getattr(a, "id", None),
            "nivel": nivel,
            "accion": accion_de_avisos(avisos, nivel),
            "avisos": avisos,
        })
    return {"periodo": periodo, "cuentas": cuentas, "filas": filas}


@router.get("/rechazos")
def rechazos(anio: int, mes: int, db: Session = Depends(get_db),
             token=Depends(require_admin_or_empleado)):
    """Lo que el operador devolvió, agrupado por el texto del error."""
    periodo = _periodo(anio, mes)
    planes = (db.query(models.PlanillaLiquidacion)
              .filter(models.PlanillaLiquidacion.periodo_cotizacion == periodo,
                      models.PlanillaLiquidacion.estado != "anulada")
              .all())
    grupos = {}
    for l in planes:
        if not l.respuesta_operador:
            continue
        try:
            datos = json.loads(l.respuesta_operador)
        except (ValueError, TypeError):
            continue
        errores = datos.get("errores") or []
        advertencias = datos.get("advertencias") or []
        if not errores and not advertencias:
            continue
        for item in errores:
            _meter(grupos, item, "rojo", l)
        for item in advertencias:
            _meter(grupos, item, "amarillo", l)
    return {"periodo": periodo, "grupos": list(grupos.values())}


def _meter(grupos, item, nivel, liquidacion):
    if isinstance(item, str):
        texto = item
    else:
        texto = (item or {}).get("descripcion") or (item or {}).get("mensaje") or ""
    texto = (texto or "Sin descripción").strip()
    clave = texto.lower()
    grupo = grupos.setdefault(clave, {
        "nivel": nivel,
        "descripcion": texto,
        "accion": accion_rechazo(texto),
        "planillas": [],
    })
    if nivel == "rojo":
        grupo["nivel"] = "rojo"
    grupo["planillas"].append({
        "id": liquidacion.id,
        "doc": liquidacion.afiliado_doc,
        "nombre": liquidacion.afiliado_nombre,
        "estado": liquidacion.estado,
        "numero": liquidacion.numero_planilla or "",
        "codigo": liquidacion.planilla_corregida or "",
    })


@router.get("/novedades")
def novedades(anio: int, mes: int, db: Session = Depends(get_db),
              token=Depends(require_admin_or_empleado)):
    """Ingresos, retiros y cambios de sueldo que cambian los días del archivo."""
    periodo = _periodo(anio, mes)
    prefijo = f"{anio:04d}-{mes:02d}"
    filas = []

    for a in (db.query(models.Afiliado)
              .filter(models.Afiliado.activo == True,  # noqa: E712
                      models.Afiliado.fecha_ingreso.like(f"{prefijo}%"))
              .limit(_TOPE).all()):
        dias, nov, _ = motor.dias_cotizados(a, anio, mes)
        filas.append({
            "tipo": "ingreso",
            "doc": a.doc,
            "nombre": a.nombre,
            "empresa": a.empresa or "",
            "detalle": a.fecha_ingreso or "",
            "dias": dias,
            "marca": ",".join(nov.keys()) or "ING",
        })

    for r in (db.query(models.Retiro)
              .filter(models.Retiro.anio == str(anio),
                      models.Retiro.mes.in_(_formas_mes(mes)))
              .limit(_TOPE).all()):
        filas.append({
            "tipo": "retiro",
            "doc": r.doc,
            "nombre": r.nombre,
            "empresa": r.empresa or "",
            "detalle": r.fecha or r.motivo or "",
            "dias": None,
            "marca": "RET",
        })

    anterior = f"{anio - 1:04d}-12" if mes == 1 else f"{anio:04d}-{mes - 1:02d}"
    previas = (db.query(models.PlanillaDetalle)
               .join(models.PlanillaLiquidacion,
                     models.PlanillaDetalle.liquidacion_id == models.PlanillaLiquidacion.id)
               .filter(models.PlanillaLiquidacion.periodo_cotizacion == anterior,
                       models.PlanillaLiquidacion.estado != "anulada")
               .all())
    docs_previos = {d.doc for d in previas if d.doc}
    actuales = {}
    if docs_previos:
        actuales = {
            a.doc: a for a in db.query(models.Afiliado)
            .filter(models.Afiliado.activo == True,  # noqa: E712
                    models.Afiliado.doc.in_(docs_previos)).all()
        }
    for d in previas:
        a = actuales.get(d.doc)
        if not a or a.salario_basico is None or d.salario_basico is None:
            continue
        if int(a.salario_basico) != int(d.salario_basico):
            filas.append({
                "tipo": "sueldo",
                "doc": a.doc,
                "nombre": a.nombre,
                "empresa": a.empresa or "",
                "detalle": f"{int(d.salario_basico)} → {int(a.salario_basico)}",
                "dias": 30,
                "marca": "VSP",
            })
    return {"periodo": periodo, "filas": filas}


@router.get("/conciliacion")
def conciliacion(anio: int, mes: int, db: Session = Depends(get_db),
                 token=Depends(require_admin_or_empleado)):
    """Lo que pagó el cliente contra lo que se pagó de la planilla."""
    periodo = _periodo(anio, mes)
    facturas = (db.query(models.Factura)
                .filter(models.Factura.anio == str(anio),
                        models.Factura.mes.in_(_formas_mes(mes)))
                .limit(5000).all())
    planes = {
        l.afiliado_doc: l
        for l in db.query(models.PlanillaLiquidacion)
        .filter(models.PlanillaLiquidacion.periodo_cotizacion == periodo,
                models.PlanillaLiquidacion.estado != "anulada").all()
    }
    filas, cuentas = [], {"cliente_sin_pila": 0, "pila_sin_cliente": 0, "al_dia": 0, "pendiente": 0}
    vistos = set()
    for f in facturas:
        l = planes.get(f.doc)
        vistos.add(f.doc)
        fila = _cruce(f, l)
        cuentas[fila["cruce"]] += 1
        filas.append(fila)
    for doc, l in planes.items():
        if doc in vistos:
            continue
        fila = _cruce(None, l)
        cuentas[fila["cruce"]] += 1
        filas.append(fila)
    return {"periodo": periodo, "cuentas": cuentas, "filas": filas}


def _cruce(factura, liquidacion) -> dict:
    cliente_pago = bool(factura and factura.estado in ("pagado", "planilla_pagada"))
    pila_pagada = bool(liquidacion and liquidacion.estado == "pagada")
    if cliente_pago and not pila_pagada:
        cruce = "cliente_sin_pila" if liquidacion else "cliente_sin_pila"
    elif pila_pagada and factura and factura.estado == "pendiente":
        cruce = "pila_sin_cliente"
    elif cliente_pago and pila_pagada:
        cruce = "al_dia"
    else:
        cruce = "pendiente"
    return {
        "doc": (factura.doc if factura else liquidacion.afiliado_doc) or "",
        "nombre": (factura.nombre_afiliado if factura else liquidacion.afiliado_nombre) or "",
        "empresa": (factura.cliente if factura else liquidacion.cliente_ref) or "",
        "factura_estado": getattr(factura, "estado", None) or "sin factura",
        "planilla_id": getattr(liquidacion, "id", None),
        "planilla_estado": getattr(liquidacion, "estado", None) or "sin planilla",
        "fecha_limite": getattr(liquidacion, "fecha_limite_pago", None) or "",
        "cruce": cruce,
    }


@router.get("/diferencias")
def diferencias(db: Session = Depends(get_db),
                token=Depends(require_admin_or_empleado)):
    """Última consulta vigente contra la ficha. No aplica el cambio sola."""
    consultas = (db.query(models.ConsultaExterna)
                 .order_by(models.ConsultaExterna.id.desc())
                 .limit(2000).all())
    ultima = {}
    for c in consultas:
        ultima.setdefault(c.doc, c)
    if not ultima:
        return {"filas": []}
    afiliados = {
        a.doc: a for a in db.query(models.Afiliado)
        .filter(models.Afiliado.activo == True,  # noqa: E712
                models.Afiliado.doc.in_(list(ultima))).all()
    }
    filas = []
    for doc, c in ultima.items():
        a = afiliados.get(doc)
        if a is None:
            continue
        if not c.exito:
            detalle = (c.error_detalle or "").lower()
            if "bdua" in detalle or "no se encuentra" in detalle:
                filas.append(_dif(a, c, "no está en la base de la consulta", ""))
            continue
        if c.eps and not mismo_nombre("EPS", a.eps or "", c.eps):
            filas.append(_dif(a, c, a.eps or "", c.eps))
    return {"filas": filas}


def _dif(afiliado, consulta, ficha, hallado):
    return {
        "afiliado_id": afiliado.id,
        "doc": afiliado.doc,
        "nombre": afiliado.nombre,
        "fuente": consulta.fuente,
        "eps_ficha": ficha,
        "eps_consulta": hallado or consulta.eps or "",
        "cuando": consulta.creado.isoformat() if consulta.creado else "",
    }


@router.get("/porque/{liquidacion_id}")
def porque(liquidacion_id: int, db: Session = Depends(get_db),
           token=Depends(require_admin_or_empleado)):
    """Cómo se armó el monto de una planilla ya liquidada."""
    l = db.query(models.PlanillaLiquidacion).filter_by(id=liquidacion_id).first()
    if not l:
        raise HTTPException(404, "Liquidación no encontrada")
    d = (db.query(models.PlanillaDetalle)
         .filter_by(liquidacion_id=l.id)
         .order_by(models.PlanillaDetalle.secuencia).first())
    if not d:
        raise HTTPException(404, "La planilla no tiene línea congelada")
    ap = db.query(models.AportantePila).filter_by(id=l.aportante_id).first()
    return {
        "id": l.id,
        "nombre": l.afiliado_nombre,
        "doc": l.afiliado_doc,
        "periodo": l.periodo_cotizacion,
        "estado": l.estado,
        "notas": explicar_monto(d, bool(ap and ap.exonerado_parafiscales)),
    }
