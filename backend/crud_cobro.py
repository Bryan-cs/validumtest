"""Módulo de cobro."""
import json, calendar
from datetime import datetime
from sqlalchemy.orm import load_only
import models
from models import COL_TZ
from const import MESES
from crud_cache import _cache_get, _cache_set, TTL_COBRO
from crud_helpers import _servicios_afiliado, _ceil100
from logger import logger as log


def get_cobro(db, empresa="", cliente="", tipo="", mes="", anio="", doc=""):
    cache_key = f"cobro:{empresa}:{cliente}:{tipo}:{mes}:{anio}:{doc}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    hoy = datetime.now(COL_TZ)
    dia_hoy = hoy.day

    meses_ventana = []
    if mes and anio:
        try:
            _m_idx = MESES.index(mes) + 1
            meses_ventana = [(int(anio), _m_idx)]
        except (ValueError, IndexError):
            pass
    if not meses_ventana:
        for i in range(1, -1, -1):
            m = hoy.month - i
            y = hoy.year
            while m <= 0:
                m += 12
                y -= 1
            meses_ventana.append((y, m))

    cfg = db.query(models.Config).first()
    ibc_global = float(cfg.ibc_global) if cfg else 1_750_905
    pcts = json.loads(cfg.porcentajes or "{}") if cfg else {}
    _corte = (cfg.anio_inicio_cobro, cfg.mes_inicio_cobro) if cfg and cfg.anio_inicio_cobro and cfg.mes_inicio_cobro else None

    anios_ventana = list({str(y) for y, _ in meses_ventana})
    meses_ventana_nombres = list({MESES[m-1] for _, m in meses_ventana})
    _pares_validos = {(str(y), MESES[m-1]) for y, m in meses_ventana}
    facturas_set = set(
        (f.doc, f.mes, f.anio)
        for f in db.query(models.Factura.doc, models.Factura.mes, models.Factura.anio)
        .filter(models.Factura.anio.in_(anios_ventana))
        .filter(models.Factura.mes.in_(meses_ventana_nombres))
        .filter(models.Factura.estado.in_(["pagado", "planilla_pagada"]))
        .all()
        if (f.anio, f.mes) in _pares_validos
    )

    q = db.query(models.Afiliado).filter(
        models.Afiliado.activo == True,
        models.Afiliado.estado_srv.notin_(["RETIRADO"]),
        models.Afiliado.cliente_txt != "EMPLEADO",
    ).options(load_only(
        models.Afiliado.id,
        models.Afiliado.nombre,
        models.Afiliado.doc,
        models.Afiliado.tipo_doc,
        models.Afiliado.empresa,
        models.Afiliado.cliente_txt,
        models.Afiliado.estado_srv,
        models.Afiliado.subtipo,
        models.Afiliado.fecha_afiliacion,
        models.Afiliado.fecha_ingreso,
        models.Afiliado.ibc,
        models.Afiliado.servicios,
        models.Afiliado.arl,
        models.Afiliado.novedades,
        models.Afiliado.creado,
    ))
    if empresa: q = q.filter(models.Afiliado.empresa == empresa)
    if cliente: q = q.filter(models.Afiliado.cliente_txt == cliente)
    if doc:     q = q.filter(models.Afiliado.doc == doc)

    afils = q.all()

    # Mapa de primera factura por doc — fallback para afiliados con Afiliado.creado=NULL
    # (datos legacy importados sin timestamp). Evita que aparezcan como VENCIDO en meses
    # anteriores al inicio real de facturación.
    docs_afils = [a.doc for a in afils if a.doc]
    first_factura_map: dict = {}
    if docs_afils:
        for f in db.query(
            models.Factura.doc, models.Factura.mes, models.Factura.anio
        ).filter(models.Factura.doc.in_(docs_afils)).all():
            mes_norm = (f.mes or "").strip().title()
            anio_norm = str(f.anio or "").strip()
            if mes_norm in MESES and anio_norm.isdigit():
                key = (int(anio_norm), MESES.index(mes_norm) + 1)
                prev = first_factura_map.get(f.doc)
                if prev is None or key < prev:
                    first_factura_map[f.doc] = key

    # Mes siguiente al actual — fallback final para afiliados sin creado y sin facturas
    # (recién registrados sin historial). No deben aparecer en cobro hasta el siguiente ciclo.
    next_month = hoy.month + 1
    next_year = hoy.year
    if next_month > 12:
        next_month, next_year = 1, next_year + 1

    rows = []
    for a in afils:
        fa = a.fecha_afiliacion or a.fecha_ingreso or ""
        if not fa or "-" not in fa:
            log.warning(f"cobro: afiliado doc={a.doc} omitido — sin fecha_afiliacion")
            continue
        try:
            partes = fa.split("-")
            dia_afil  = int(partes[2])
            afil_year = int(partes[0])
            afil_month= int(partes[1])
        except: continue

        ibc = float(a.ibc) if (a.ibc and a.ibc > 0) else ibc_global
        srvs = _servicios_afiliado(a)
        planilla = sum(_ceil100(ibc * pcts.get(s, pcts.get(s.upper(), 0.0))) for s in srvs)
        cliente_afil = a.cliente_txt or ""

        primer_cobro_m = afil_month + 1
        primer_cobro_y = afil_year
        if primer_cobro_m > 12:
            primer_cobro_m = 1
            primer_cobro_y += 1

        # Piso: el cobro no puede empezar antes del mes siguiente al registro en sistema
        if a.creado:
            reg = a.creado
            reg_m = reg.month + 1
            reg_y = reg.year
            if reg_m > 12:
                reg_m, reg_y = 1, reg_y + 1
            if (reg_y, reg_m) > (primer_cobro_y, primer_cobro_m):
                primer_cobro_y, primer_cobro_m = reg_y, reg_m
        else:
            # Afiliado.creado=NULL (data legacy): usar primera factura como piso.
            first_fact = first_factura_map.get(a.doc)
            if first_fact:
                if first_fact > (primer_cobro_y, primer_cobro_m):
                    primer_cobro_y, primer_cobro_m = first_fact
            else:
                # Sin creado y sin factura: tratar como recién registrado.
                # No aparece en cobro hasta el siguiente ciclo (mes siguiente al actual).
                if (next_year, next_month) > (primer_cobro_y, primer_cobro_m):
                    primer_cobro_y, primer_cobro_m = next_year, next_month

        for (y, m) in meses_ventana:
            if (y, m) < (primer_cobro_y, primer_cobro_m): continue
            if _corte and (y, m) < _corte: continue
            if mes  and MESES[m - 1] != mes: continue
            if anio and str(y) != anio:      continue

            mes_nombre = MESES[m - 1]
            anio_str   = str(y)
            tiene_fac  = (a.doc, mes_nombre, anio_str) in facturas_set
            es_actual  = (y == hoy.year and m == hoy.month)

            if tiene_fac:
                estado = "COBRADO"
            elif not es_actual:
                estado = "VENCIDO"
            else:
                if dia_afil < dia_hoy:        estado = "VENCIDO"
                elif dia_afil == dia_hoy:     estado = "HOY"
                elif dia_afil == (dia_hoy % calendar.monthrange(hoy.year, hoy.month)[1]) + 1: estado = "PROXIMO"
                else:
                    continue

            if tipo and estado != tipo: continue

            rows.append({
                "id":        f"{a.id}_{m}_{y}",
                "afil_id":   a.id,
                "nombre":    a.nombre,
                "empresa":   a.empresa,
                "doc":       a.doc,
                "tipo_doc":  a.tipo_doc or "",
                "dia_cobro": dia_afil,
                "mes":       mes_nombre,
                "anio":      anio_str,
                "fecha_afiliacion": fa,
                "cliente":   cliente_afil,
                "servicios": srvs,
                "planilla":  planilla,
                "estado":    estado,
                "novedades": a.novedades or "",
                "subtipo":   a.subtipo or "",
                "estado_srv": a.estado_srv or "",
            })

    orden = {"VENCIDO": 0, "HOY": 1, "PROXIMO": 2, "COBRADO": 3}
    rows.sort(key=lambda r: (orden.get(r["estado"], 4), r["nombre"], r["anio"], r["mes"]))
    _cache_set(cache_key, rows, ttl=TTL_COBRO)
    return rows
