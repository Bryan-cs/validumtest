"""CRUD de facturas."""
import json, os
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import text as _text
import models, schemas
from models import COL_TZ
from crud_cache import cache_invalidar
from crud_helpers import _factura_to_dict, _log


def _next_codigo(db):
    from tenant import current_org_id
    org = current_org_id.get()
    db_url = str(db.bind.url) if db.bind else os.environ.get("DATABASE_URL", "")
    if "postgresql" in db_url:
        # Advisory lock por organización (evita colisión de secuencia con concurrencia dentro de la org).
        # La forma de dos argumentos es pg_advisory_xact_lock(int4, int4). El literal
        # 9876543210 excede int4, asi que Postgres lo tipaba como bigint y buscaba una
        # sobrecarga (bigint, integer) que no existe: toda creacion de factura moria con
        # UndefinedFunction. Se usa una clave de namespace dentro del rango de int4 y se
        # castean ambos argumentos de forma explicita.
        db.execute(_text("SELECT pg_advisory_xact_lock(CAST(987654321 AS int), CAST(:org AS int))"),
                   {"org": org or 0})
        # codigo es único por organización → la secuencia también debe scoparse por org.
        result = db.execute(_text(
            "SELECT MAX(CAST(SPLIT_PART(codigo, '-', 2) AS INTEGER)) "
            "FROM facturas WHERE codigo LIKE 'FVE-%' AND organizacion_id = :org"
        ), {"org": org}).scalar()
        n = max(2650, result) if result else 2650
    else:
        # ORM → auto-filtrado por organización (secuencia por org).
        last = db.query(models.Factura).filter(models.Factura.codigo.like("FVE-%")).order_by(models.Factura.id.desc()).first()
        n = 2650
        if last:
            try: n = max(n, int(last.codigo.split("-")[1]))
            except: pass
    return f"FVE-{str(n+1).zfill(4)}"

def get_facturas(db, anio="", mes="", cliente="", estado="", banco="", doc="",
                skip: int = 0, limit: int = 0, exclude_planilla: bool = False):
    q = db.query(models.Factura)
    if anio:    q = q.filter_by(anio=anio)
    if mes:     q = q.filter_by(mes=mes)
    if cliente: q = q.filter_by(cliente=cliente)
    if estado:  q = q.filter_by(estado=estado)
    elif exclude_planilla:
        q = q.filter(models.Factura.estado != 'planilla_pagada')
    if banco:   q = q.filter_by(banco=banco)
    if doc:     q = q.filter_by(doc=doc)
    total = q.count()
    q = q.order_by(models.Factura.id.desc())
    # Sin limit el listado traía la tabla entera. 5.000 cubre un mes de las
    # cuatro empresas; el Excel pide un tope explícito más alto.
    if limit > 0:
        q = q.offset(skip).limit(min(limit, 20_000))
    else:
        q = q.limit(5_000)
    items = q.all()
    docs = list({f.doc for f in items if f.doc})
    afil_map = {}
    if docs:
        for a in db.query(
            models.Afiliado.doc, models.Afiliado.tel, models.Afiliado.fecha_afiliacion,
            models.Afiliado.eps, models.Afiliado.afp, models.Afiliado.arl,
            models.Afiliado.ccf, models.Afiliado.ibc, models.Afiliado.email,
            models.Afiliado.dir, models.Afiliado.ciudad, models.Afiliado.empresa,
            models.Afiliado.estado, models.Afiliado.detalle,
        ).filter(models.Afiliado.doc.in_(docs)).all():
            afil_map[a.doc] = {
                "tel": a.tel or "", "fecha_afiliacion": a.fecha_afiliacion or "",
                "eps": a.eps or "", "afp": a.afp or "", "arl": a.arl or "",
                "ccf": a.ccf or "", "ibc": a.ibc or 0, "email": a.email or "",
                "dir": a.dir or "", "ciudad": a.ciudad or "",
                "empresa": a.empresa or "", "estado_afil": a.estado or "",
                "detalle": a.detalle or "",
            }
    result = []
    for f in items:
        d = _factura_to_dict(f)
        info = afil_map.get(f.doc, {})
        d["tel"] = info.get("tel", "")
        d["fecha_afiliacion"] = info.get("fecha_afiliacion", "")
        d["afil_info"] = info
        result.append(d)
    return {"total": total, "items": result}

def get_factura(db, id):
    return db.query(models.Factura).filter_by(id=id).first()

def get_facturas_pendientes_by_doc(db, doc, mes=None):
    q = db.query(models.Factura).filter_by(doc=doc, estado="pendiente")
    if mes: q = q.filter_by(mes=mes)
    return q.all()

def create_factura(db, data: schemas.FacturaCreate):
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException

    if not data.doc or not data.doc.strip():
        raise HTTPException(400, "El documento del afiliado es requerido")
    if not data.mes or not data.mes.strip():
        raise HTTPException(400, "El mes es requerido")

    anio_fact = data.anio or str(datetime.now(COL_TZ).year)
    duplicada = db.query(models.Factura).filter_by(
        doc=data.doc, mes=data.mes, anio=anio_fact
    ).first()
    if duplicada:
        raise HTTPException(400, f"Ya existe una factura del mes")

    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    max_retries = 3
    for attempt in range(max_retries):
        codigo = data.codigo or _next_codigo(db)
        f = models.Factura(
            codigo=codigo, nombre_afiliado=data.nombre_afiliado, doc=data.doc,
            cliente=data.cliente, anio=data.anio or str(datetime.now(COL_TZ).year),
            mes=data.mes, periodo=data.periodo, estado=data.estado, banco=data.banco,
            ingresos=data.ingresos, costos=data.costos, costo_adm=data.costo_adm,
            conceptos_extra=data.conceptos_extra,
            utilidad=(data.ingresos or 0) - (data.costos or 0) - (data.costo_adm or 0) + (data.conceptos_extra or 0),
            novedades=data.novedades,
            servicios_detalle=json.dumps(data.servicios_detalle),
            conceptos_detalle=json.dumps(data.conceptos_detalle),
            creado_por=data.creado_por,
        )
        db.add(f); _log(db, data.creado_por, "agregó una factura", "Facturación", codigo)
        try:
            db.commit()
            db.refresh(f)
            return _factura_to_dict(f)
        except IntegrityError:
            db.rollback()
            if attempt == max_retries - 1:
                raise HTTPException(400, f"No se pudo generar código de factura único. Intente nuevamente.")
            data.codigo = ""

def update_factura(db, id, data: schemas.FacturaUpdate, editor=""):
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    f = db.query(models.Factura).filter_by(id=id).first()
    if not f: return None

    PAGADAS = {"pagado", "planilla_pagada"}
    campos = data.model_dump(exclude_none=True)

    if campos.get("estado") == "planilla_pagada" and f.estado == "pendiente":
        raise HTTPException(400, "No se puede marcar como planilla_pagada sin pasar por pagado")

    if f.estado in PAGADAS:
        if campos.get("estado") == "pendiente":
            raise HTTPException(400, "No se puede revertir una factura pagada a pendiente")
        if ("mes" in campos and campos["mes"] != f.mes) or \
           ("anio" in campos and campos["anio"] != f.anio):
            raise HTTPException(400, "No se puede cambiar el período de una factura ya pagada")

    for k, v in data.model_dump(exclude_none=True).items():
        if k in ("servicios_detalle","conceptos_detalle"): v = json.dumps(v)
        setattr(f, k, v)

    # Las columnas de dinero son Numeric -> la base devuelve Decimal, pero los campos que
    # acaba de escribir setattr() son float del request. Mezclarlos lanzaba
    # "unsupported operand type(s) for -: 'decimal.Decimal' and 'float'" y editar los
    # costos de cualquier factura daba 500. Se normaliza todo a Decimal antes de operar.
    def _dec(v):
        return v if isinstance(v, Decimal) else Decimal(str(v or 0))
    f.utilidad = (_dec(f.ingresos) - _dec(f.costos)
                  - _dec(f.costo_adm) + _dec(f.conceptos_extra))

    _log(db, editor, "editó una factura", "Facturación", f.codigo)
    db.commit(); db.refresh(f); return _factura_to_dict(f)

def pagar_factura(db, id, banco="", user="", monto=None):
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    f = db.query(models.Factura).filter_by(id=id).with_for_update().first()
    if not f: return None
    if f.estado in ("pagado", "planilla_pagada"):
        return _factura_to_dict(f)
    if not banco or not banco.strip():
        raise HTTPException(400, "Debe seleccionar un banco antes de marcar como pagada")
    f.banco = banco
    f.estado = "pagado"
    f.pagado_en = datetime.now(timezone.utc)
    _log(db, user, "marcó factura como pagada", "Facturación", f.codigo)
    db.commit(); db.refresh(f); return _factura_to_dict(f)

def marcar_planilla_pagada(db, id, user=""):
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    f = db.query(models.Factura).filter_by(id=id).with_for_update().first()
    if not f: return None
    if f.estado == "planilla_pagada":
        return _factura_to_dict(f)
    if f.estado != "pagado":
        return {"error": "La factura debe estar en estado 'Pagada' antes de marcar planilla como pagada"}
    f.estado = "planilla_pagada"
    _log(db, user, "marcó planilla como pagada", "Facturación", f.codigo)
    db.commit(); db.refresh(f); return _factura_to_dict(f)

def delete_factura(db, id, user=""):
    f = db.query(models.Factura).filter_by(id=id).first()
    if not f: return None
    codigo = f.codigo
    db.delete(f)
    _log(db, user, "eliminó una factura", "Facturación", codigo)
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    db.commit()
