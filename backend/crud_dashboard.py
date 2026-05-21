"""Dashboard y resumen por clientes."""
from datetime import datetime
from sqlalchemy import func, case, and_
from sqlalchemy import true as sa_true
import models
from models import COL_TZ
from const import MESES
from crud_cache import _cache_get, _cache_set, TTL_DASHBOARD


def get_dashboard(db, anio="", mes=""):
    cache_key = f"dashboard:{anio}:{mes}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    stats = db.query(
        func.count(models.Afiliado.id).label("total"),
        func.sum(case((models.Afiliado.estado_srv == "ACTIVO",      1), else_=0)).label("activos"),
        func.sum(case((models.Afiliado.estado_srv == "RETIRADO",    1), else_=0)).label("retirados"),
        func.sum(case((models.Afiliado.estado_srv == "SUSPENDIDO",  1), else_=0)).label("suspendidos"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%DOBLE%"),          1), else_=0)).label("doble_afiliacion"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%NO SE ENCUENTRA%"),1), else_=0)).label("no_encontrado"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%ESPERA%"),         1), else_=0)).label("en_espera"),
    ).filter(models.Afiliado.activo==True).one()

    period_conds = []
    if anio: period_conds.append(models.Factura.anio == anio)
    if mes:  period_conds.append(models.Factura.mes == mes)
    period_ok  = and_(*period_conds) if period_conds else sa_true()
    paid_ok        = models.Factura.estado.in_(["pagado", "planilla_pagada"])
    pending_ok     = models.Factura.estado == "pendiente"
    planilla_ok    = models.Factura.estado == "planilla_pagada"

    facts = db.query(
        func.sum(case((period_ok, 1), else_=0)).label("n"),
        func.coalesce(func.sum(case((and_(paid_ok, period_ok),       models.Factura.ingresos), else_=0)), 0).label("ingresos"),
        func.coalesce(func.sum(case((and_(paid_ok, period_ok),       models.Factura.utilidad), else_=0)), 0).label("utilidad"),
        func.coalesce(func.sum(case((and_(planilla_ok, period_ok), models.Factura.costo_adm), else_=0)), 0).label("sum_cargo_adm"),
        func.coalesce(func.sum(case((and_(pending_ok, period_ok), models.Factura.ingresos), else_=0)), 0).label("pendiente"),
        func.sum(case((and_(pending_ok, period_ok), 1), else_=0)).label("n_pend"),
        func.coalesce(func.sum(case(
            (and_(pending_ok, models.Factura.afiliado_eliminado == False), models.Factura.ingresos),
            else_=0
        )), 0).label("pend_total"),
    ).one()

    _anio_ref = int(anio) if anio else datetime.now(COL_TZ).year
    if mes:
        _mes_ref = (MESES.index(mes) + 1) if mes in MESES else int(mes)
        nominas  = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(mes=_mes_ref, anio=_anio_ref).scalar()
        gastos   = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(mes=_mes_ref, anio=_anio_ref).scalar()
        ing_adic = db.query(func.coalesce(func.sum(models.IngresoAdicional.valor), 0)).filter_by(mes=_mes_ref, anio=_anio_ref).scalar()
    elif anio:
        nominas  = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(anio=_anio_ref).scalar()
        gastos   = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(anio=_anio_ref).scalar()
        ing_adic = db.query(func.coalesce(func.sum(models.IngresoAdicional.valor), 0)).filter_by(anio=_anio_ref).scalar()
    else:
        _mes_ref = datetime.now(COL_TZ).month
        nominas  = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(mes=_mes_ref, anio=_anio_ref).scalar()
        gastos   = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(mes=_mes_ref, anio=_anio_ref).scalar()
        ing_adic = db.query(func.coalesce(func.sum(models.IngresoAdicional.valor), 0)).filter_by(mes=_mes_ref, anio=_anio_ref).scalar()

    ing_adic = float(ing_adic)
    util_neta = float(facts.utilidad) + ing_adic - float(nominas) - float(gastos)
    pend_total = float(facts.pend_total)
    _total_impuestos = float(facts.sum_cargo_adm or 0)
    meses_factor = 1 if (mes or not anio) else 12

    banco_q = db.query(
        models.Factura.banco,
        func.coalesce(func.sum(models.Factura.ingresos), 0).label("total"),
    ).filter(
        models.Factura.estado.in_(["pagado", "planilla_pagada"]),
        period_ok,
    ).group_by(models.Factura.banco).all()
    _BANCO_CANON = {
        "daviplata": "Daviplata", "nequi": "Nequi", "davivienda": "Davivienda",
        "bancolombia": "Bancolombia", "banco de bogotá": "Banco de Bogotá",
        "banco de bogota": "Banco de Bogotá", "efectivo": "Efectivo",
    }
    _merged: dict[str, float] = {}
    for row in banco_q:
        if float(row.total) <= 0:
            continue
        raw = (row.banco or "Sin banco").strip()
        canon = _BANCO_CANON.get(raw.lower(), raw)
        _merged[canon] = _merged.get(canon, 0.0) + float(row.total)
    ingresos_por_banco = [{"banco": k, "total": v} for k, v in _merged.items()]
    ingresos_por_banco.sort(key=lambda x: x["total"], reverse=True)

    result = {
        "activos": int(stats.activos or 0), "suspendidos": int(stats.suspendidos or 0),
        "doble_afiliacion": int(stats.doble_afiliacion or 0),
        "no_encontrado": int(stats.no_encontrado or 0),
        "en_espera": int(stats.en_espera or 0),
        "total_afiliados": int(stats.total or 0),
        "facturas": int(facts.n or 0), "ingresos": float(facts.ingresos) + ing_adic,
        "utilidad_bruta": float(facts.utilidad) + ing_adic, "nominas": float(nominas),
        "gastos_fijos": float(gastos), "utilidad_neta": util_neta, "ingresos_adicionales": ing_adic,
        "pendiente_cobro": float(facts.pendiente), "facturas_pendientes": int(facts.n_pend or 0),
        "pendiente_cobro_total": float(pend_total), "meses_factor": meses_factor,
        "ingresos_por_banco": ingresos_por_banco,
        "total_impuestos_planillas": _total_impuestos,
    }
    _cache_set(cache_key, result, ttl=TTL_DASHBOARD)
    return result


def get_resumen_clientes(db, anio="", mes=""):
    cache_key = f"dashboard_clientes:{anio}:{mes}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    period_conds = []
    if anio: period_conds.append(models.Factura.anio == anio)
    if mes:  period_conds.append(models.Factura.mes  == mes)
    period_ok  = and_(*period_conds) if period_conds else sa_true()
    paid_ok    = models.Factura.estado.in_(["pagado", "planilla_pagada"])
    pending_ok = models.Factura.estado == "pendiente"

    fact_rows = db.query(
        models.Factura.cliente,
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.ingresos),  else_=0)), 0).label("ingresos"),
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.costos),    else_=0)), 0).label("costos"),
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.costo_adm), else_=0)), 0).label("costo_adm"),
        func.coalesce(func.sum(case((and_(pending_ok, period_ok), models.Factura.ingresos),  else_=0)), 0).label("pendiente"),
        func.sum(case((and_(paid_ok, period_ok), 1), else_=0)).label("n_pagadas"),
    ).filter(
        models.Factura.cliente != None,
        models.Factura.cliente != "",
    ).group_by(models.Factura.cliente).all()

    afil_rows = db.query(
        models.Afiliado.cliente_txt,
        func.count(models.Afiliado.id).label("n"),
    ).filter(
        models.Afiliado.activo == True,
        models.Afiliado.cliente_txt != None,
        models.Afiliado.cliente_txt != "",
    ).group_by(models.Afiliado.cliente_txt).all()

    afil_map = {r.cliente_txt: int(r.n) for r in afil_rows}

    result = []
    for r in fact_rows:
        ing      = float(r.ingresos)
        cos      = float(r.costos)
        costo_adm = float(r.costo_adm)
        util     = ing - cos - costo_adm
        result.append({
            "cliente":     r.cliente,
            "n_afiliados": afil_map.get(r.cliente, 0),
            "ingresos":    ing,
            "costos":      cos,
            "utilidad":    util,
            "margen_pct":  round(util / ing * 100, 1) if ing > 0 else 0.0,
            "pendiente":   float(r.pendiente),
            "n_pagadas":   int(r.n_pagadas or 0),
        })
    result.sort(key=lambda x: x["ingresos"], reverse=True)
    _cache_set(cache_key, result, ttl=TTL_DASHBOARD)
    return result


def get_dashboard_cliente(db, cliente, anio="", mes=""):
    period_conds = []
    if anio: period_conds.append(models.Factura.anio == anio)
    if mes:  period_conds.append(models.Factura.mes  == mes)
    period_ok  = and_(*period_conds) if period_conds else sa_true()
    paid_ok    = models.Factura.estado.in_(["pagado", "planilla_pagada"])
    pending_ok = models.Factura.estado == "pendiente"

    facts = db.query(
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.ingresos),  else_=0)), 0).label("ingresos"),
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.costos),    else_=0)), 0).label("costos"),
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.costo_adm), else_=0)), 0).label("costo_adm"),
        func.coalesce(func.sum(case((and_(pending_ok, period_ok), models.Factura.ingresos),  else_=0)), 0).label("pendiente"),
        func.sum(case((and_(paid_ok,    period_ok), 1), else_=0)).label("n_pagadas"),
        func.sum(case((and_(pending_ok, period_ok), 1), else_=0)).label("n_pendientes"),
    ).filter(models.Factura.cliente == cliente).one()

    stats = db.query(
        func.count(models.Afiliado.id).label("total"),
        func.sum(case((models.Afiliado.estado_srv == "ACTIVO",                  1), else_=0)).label("activos"),
        func.sum(case((models.Afiliado.estado_srv == "SUSPENDIDO",             1), else_=0)).label("suspendidos"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%DOBLE%"),            1), else_=0)).label("doble_afiliacion"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%NO SE ENCUENTRA%"),  1), else_=0)).label("no_encontrado"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%ESPERA%"),           1), else_=0)).label("en_espera"),
    ).filter(
        models.Afiliado.activo == True,
        models.Afiliado.cliente_txt == cliente,
    ).one()

    banco_q = db.query(
        models.Factura.banco,
        func.coalesce(func.sum(models.Factura.ingresos), 0).label("total"),
    ).filter(
        models.Factura.cliente == cliente,
        models.Factura.estado.in_(["pagado", "planilla_pagada"]),
        period_ok,
    ).group_by(models.Factura.banco).all()

    _BANCO_CANON = {
        "daviplata": "Daviplata", "nequi": "Nequi", "davivienda": "Davivienda",
        "bancolombia": "Bancolombia", "banco de bogotá": "Banco de Bogotá",
        "banco de bogota": "Banco de Bogotá", "efectivo": "Efectivo",
    }
    _merged: dict[str, float] = {}
    for row in banco_q:
        if float(row.total) <= 0:
            continue
        raw   = (row.banco or "Sin banco").strip()
        canon = _BANCO_CANON.get(raw.lower(), raw)
        _merged[canon] = _merged.get(canon, 0.0) + float(row.total)
    ingresos_por_banco = sorted(
        [{"banco": k, "total": v} for k, v in _merged.items()],
        key=lambda x: x["total"], reverse=True,
    )

    hist_rows = db.query(
        models.Factura.anio,
        models.Factura.mes,
        func.coalesce(func.sum(case((paid_ok, models.Factura.ingresos), else_=0)), 0).label("ingresos"),
        func.coalesce(func.sum(case((paid_ok, models.Factura.costos),   else_=0)), 0).label("costos"),
        func.sum(case((paid_ok, 1), else_=0)).label("n"),
    ).filter(models.Factura.cliente == cliente).group_by(
        models.Factura.anio, models.Factura.mes,
    ).all()

    hist_rows = sorted(
        hist_rows,
        key=lambda r: (r.anio, MESES.index(r.mes) if r.mes in MESES else 99),
    )[-6:]

    historial = []
    for r in hist_rows:
        mes_num = (MESES.index(r.mes) + 1) if r.mes in MESES else 0
        historial.append({
            "anio": r.anio, "mes": r.mes, "mes_num": mes_num,
            "ingresos": float(r.ingresos), "costos": float(r.costos),
            "n": int(r.n or 0),
        })

    ing       = float(facts.ingresos)
    cos       = float(facts.costos)
    costo_adm = float(facts.costo_adm)
    util      = ing - cos - costo_adm
    return {
        "cliente":           cliente,
        "ingresos":          ing,
        "costos":            cos,
        "utilidad":          util,
        "margen_pct":        round(util / ing * 100, 1) if ing > 0 else 0.0,
        "pendiente":         float(facts.pendiente),
        "n_pagadas":         int(facts.n_pagadas    or 0),
        "n_pendientes":      int(facts.n_pendientes or 0),
        "afiliados": {
            "total":            int(stats.total            or 0),
            "activos":          int(stats.activos          or 0),
            "suspendidos":      int(stats.suspendidos      or 0),
            "doble_afiliacion": int(stats.doble_afiliacion or 0),
            "no_encontrado":    int(stats.no_encontrado    or 0),
            "en_espera":        int(stats.en_espera        or 0),
        },
        "ingresos_por_banco": ingresos_por_banco,
        "historial":          historial,
    }
