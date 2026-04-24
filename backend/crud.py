from sqlalchemy.orm import Session
from sqlalchemy import or_
import models, schemas, json, math
from datetime import datetime, timezone, timedelta
from models import COL_TZ
from typing import Optional
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    if not hashed or not hashed.startswith("$2"):
        return False  # contraseñas plaintext ya no son soportadas
    return bcrypt.checkpw(plain.encode(), hashed.encode())

from const import MESES

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def _get_rol_usuario(db: Session, username: str) -> str:
    """Rol cacheado 10 min — evita query extra en cada operación de escritura."""
    key = f"usuario_rol:{username}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    u = db.query(models.Usuario.rol).filter_by(username=username).first()
    rol = u.rol if u else "empleado"
    _cache_set(key, rol, ttl=600)
    return rol

def _log(db: Session, usuario: str, accion: str, modulo: str, detalle: str = ""):
    try:
        from logger import logger as _logger
        _logger.info(f"[AUDIT] {usuario} | {modulo} | {accion} | {detalle}")
    except Exception:
        pass
    if _get_rol_usuario(db, usuario) == "admin":
        return
    db.add(models.Actividad(usuario=usuario, accion=accion, modulo=modulo, detalle=detalle))

def _get_ibc(db: Session, afiliado: models.Afiliado = None) -> float:
    if afiliado and afiliado.ibc and afiliado.ibc > 0:
        return afiliado.ibc
    cfg = db.query(models.Config).first()
    return float(cfg.ibc_global) if cfg else 1_950_905

def _get_pct(db: Session, servicio: str) -> float:
    cfg = db.query(models.Config).first()
    if not cfg: return 0.0
    pcts = json.loads(cfg.porcentajes or "{}")
    key = servicio.upper().strip()
    if "ARL" in key:
        for n in ["1","2","3","4","5"]:
            if n in key: return pcts.get(f"ARL {n}", 0.0)
    return pcts.get(key, 0.0)

def _ceil100(valor: float) -> int:
    return int(math.ceil(valor / 100)) * 100

def _servicios_afiliado(afiliado: models.Afiliado) -> list:
    raw = json.loads(afiliado.servicios or "[]")
    result = []
    for s in raw:
        su = s.strip().upper()
        if "EPS" in su and "EPS" not in result:
            result.append("EPS")
        elif ("CCF" in su or "CAJA" in su) and "CCF" not in result:
            result.append("CCF")
        elif ("AFP" in su or "PENSION" in su) and not any("AFP" in r for r in result):
            result.append("AFP")
        elif "ARL" in su:
            for n in ["1","2","3","4","5"]:
                if n in su and f"ARL {n}" not in result:
                    result.append(f"ARL {n}"); break
    # También del campo arl directo
    arl = (afiliado.arl or "").strip()
    if arl and arl not in ("N/A","") and not any("ARL" in r for r in result):
        for n in ["1","2","3","4","5"]:
            if n in arl and f"ARL {n}" not in result:
                result.append(f"ARL {n}"); break
    return list(dict.fromkeys(result))

def _planilla(db: Session, afiliado: models.Afiliado, dias: int = 30) -> dict:
    ibc = _get_ibc(db, afiliado)
    servicios = _servicios_afiliado(afiliado)
    detalle = []
    total = 0
    for srv in servicios:
        pct = _get_pct(db, srv)
        val30 = _ceil100(ibc * pct)
        valor = _ceil100(val30 * dias / 30) if dias > 0 else 0
        total += valor
        detalle.append({"servicio": srv, "pct": pct, "valor": valor, "val30": val30})
    return {"detalle": detalle, "total": total, "ibc": ibc}

def _afiliado_to_dict(a: models.Afiliado) -> dict:
    return {
        "id": a.id, "nombre": a.nombre, "tipo_doc": a.tipo_doc, "doc": a.doc,
        "empresa": a.empresa, "cargo": a.cargo,
        "cliente_txt": a.cliente_txt, "eps": a.eps, "arl": a.arl,
        "ccf": a.ccf, "afp": a.afp, "subtipo": a.subtipo,
        "estado": a.estado, "estado_srv": a.estado_srv,
        "servicios": json.loads(a.servicios or "[]"),
        "tel": a.tel, "email": a.email, "dir": a.dir, "ciudad": a.ciudad or "", "novedades": a.novedades, "detalle": a.detalle or "",
        "ibc": float(a.ibc) if a.ibc is not None else None, "fecha_ingreso": a.fecha_ingreso,
        "fecha_afiliacion": a.fecha_afiliacion,
        "registrado_por": a.registrado_por, "activo": a.activo,
    }

def _factura_to_dict(f: models.Factura) -> dict:
    try:
        srv = json.loads(f.servicios_detalle or "[]")
        if not isinstance(srv, list): srv = []
    except (json.JSONDecodeError, TypeError):
        srv = []
    try:
        conc = json.loads(f.conceptos_detalle or "[]")
        if not isinstance(conc, list): conc = []
    except (json.JSONDecodeError, TypeError):
        conc = []
    return {
        "id": f.id, "codigo": f.codigo,
        "nombre_afiliado": f.nombre_afiliado, "doc": f.doc,
        "cliente": f.cliente, "anio": f.anio, "mes": f.mes,
        "periodo": f.periodo, "estado": f.estado, "banco": f.banco,
        "ingresos": float(f.ingresos or 0), "costos": float(f.costos or 0),
        "costo_adm": float(f.costo_adm or 0), "conceptos_extra": float(f.conceptos_extra or 0),
        "utilidad": float(f.utilidad or 0), "novedades": f.novedades,
        "servicios_detalle": srv,
        "conceptos_detalle": conc,
        "afiliado_eliminado": f.afiliado_eliminado,
        "pagado_en": f.pagado_en.isoformat() if f.pagado_en else None,
        "monto_pagado": float(f.monto_pagado or 0),
        "saldo_pendiente": max(0.0, float(f.ingresos or 0) - float(f.monto_pagado or 0)),
        "creado_por": f.creado_por,
        "creado": f.creado.isoformat() if f.creado else None,
    }

# ─── USUARIOS ─────────────────────────────────────────────────────────────────
def get_user_by_username(db, username): return db.query(models.Usuario).filter(models.Usuario.username.ilike(username)).first()
def get_usuario(db, id): return db.query(models.Usuario).filter_by(id=id).first()
def get_usuarios(db): return [{"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"activo":u.activo,"cliente_ref":u.cliente_ref} for u in db.query(models.Usuario).all()]
def create_usuario(db, data: schemas.UsuarioCreate):
    u = models.Usuario(nombre=data.nombre, username=data.username, password=hash_password(data.password), rol=data.rol, cliente_ref=data.cliente_ref)
    db.add(u); db.commit(); db.refresh(u)
    return {"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"cliente_ref":u.cliente_ref}
def update_usuario_password(db, id: int, new_password: str, user: str = ""):
    u = db.query(models.Usuario).filter_by(id=id).first()
    if not u:
        return None
    u.password = hash_password(new_password)
    _log(db, user, "cambió contraseña de usuario", "Usuarios", u.username)
    db.commit()
    return u

def delete_usuario(db, id, user=""):
    u = db.query(models.Usuario).filter_by(id=id).first()
    if u:
        _log(db, user, "eliminó un usuario", "Usuarios", u.username)
        from routers.deps import invalidate_user_cache
        invalidate_user_cache(u.username)
        cache_invalidar(f"usuario_rol:{u.username}")
    db.query(models.Usuario).filter_by(id=id).delete()
    db.commit()

# ─── AFILIADOS ────────────────────────────────────────────────────────────────
def _split_csv(val: str) -> list:
    """Convierte string CSV en lista, ignorando vacíos."""
    return [v.strip() for v in val.split(",") if v.strip()] if val else []


def get_afiliados_filter_options(db):
    """Retorna opciones únicas para cada filtro de afiliados (sin cargar datos completos).
    Cacheado para no consultar en cada render.
    Una sola query con DISTINCT en vez de 6 queries separadas.
    """
    cached = _cache_get("afiliados:filtros")
    if cached is not None:
        return cached
    A = models.Afiliado
    rows = db.query(
        A.empresa, A.cliente_txt, A.subtipo, A.estado_srv, A.tipo_doc, A.ccf
    ).filter_by(activo=True).distinct().all()
    result = {
        "empresas":  sorted({r.empresa     for r in rows if r.empresa}),
        "clientes":  sorted({r.cliente_txt for r in rows if r.cliente_txt}),
        "subtipos":  sorted({r.subtipo     for r in rows if r.subtipo}),
        "estados":   sorted({r.estado_srv  for r in rows if r.estado_srv}),
        "tipos_doc": sorted({r.tipo_doc    for r in rows if r.tipo_doc}),
        "ccfs":      sorted({r.ccf         for r in rows if r.ccf}),
    }
    _cache_set("afiliados:filtros", result, ttl=120)
    return result


def get_afiliados(db, q="", estado="", empresa="", cliente="", subtipo="",
                  tipo_doc="", ccf="", fecha_desde="", fecha_hasta="",
                  skip: int = 0, limit: int = 0):
    """Lista afiliados con filtros opcionales y paginación (skip/limit).
    Si limit=0 devuelve todos (para compatibilidad con exportaciones Excel).
    Cada filtro acepta múltiples valores separados por coma (CSV).
    Sin filtros ni paginación → devuelve resultado cacheado (TTL_AFILIADOS).
    """
    sin_filtros = not any([q, estado, empresa, cliente, subtipo, tipo_doc, ccf, fecha_desde, fecha_hasta])
    if sin_filtros and skip == 0 and limit == 0:
        cached = _cache_get("afiliados:all")
        if cached is not None:
            return cached

    query = db.query(models.Afiliado).filter_by(activo=True)
    if q:
        query = query.filter(or_(
            models.Afiliado.nombre.ilike(f"%{q}%"),
            models.Afiliado.doc.ilike(f"%{q}%"),
            models.Afiliado.empresa.ilike(f"%{q}%"),
            models.Afiliado.cliente_txt.ilike(f"%{q}%"),
        ))
    # Filtros multi-valor: acepta "valor1,valor2" → IN clause
    estados = _split_csv(estado)
    if estados:
        query = query.filter(or_(
            models.Afiliado.estado_srv.in_(estados),
            models.Afiliado.estado.in_(estados),
        ))
    empresas = _split_csv(empresa)
    if empresas: query = query.filter(models.Afiliado.empresa.in_(empresas))
    clientes = _split_csv(cliente)
    if clientes: query = query.filter(models.Afiliado.cliente_txt.in_(clientes))
    subtipos = _split_csv(subtipo)
    if subtipos: query = query.filter(models.Afiliado.subtipo.in_(subtipos))
    tipos_doc = _split_csv(tipo_doc)
    if tipos_doc: query = query.filter(models.Afiliado.tipo_doc.in_(tipos_doc))
    ccfs = _split_csv(ccf)
    if ccfs: query = query.filter(models.Afiliado.ccf.in_(ccfs))
    if fecha_desde: query = query.filter(models.Afiliado.fecha_afiliacion >= fecha_desde)
    if fecha_hasta: query = query.filter(models.Afiliado.fecha_afiliacion <= fecha_hasta)
    total = query.count()
    query = query.order_by(models.Afiliado.nombre)
    if limit > 0:
        query = query.offset(skip).limit(limit)
    else:
        query = query.limit(50_000)  # cap de seguridad — evita retornar millones de filas
    result = {"total": total, "items": [_afiliado_to_dict(a) for a in query.all()]}
    if sin_filtros and skip == 0 and limit == 0:
        _cache_set("afiliados:all", result, ttl=TTL_AFILIADOS)
    return result

def get_afiliado(db, id): a = db.query(models.Afiliado).filter_by(id=id, activo=True).first(); return _afiliado_to_dict(a) if a else None
def get_afiliado_by_doc(db, doc): return db.query(models.Afiliado).filter_by(doc=doc, activo=True).first()

def create_afiliado(db, data: schemas.AfiliadoCreate):
    from sqlalchemy.exc import IntegrityError
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:"); cache_invalidar("afiliados:")
    a = models.Afiliado(**{
        "nombre":data.nombre,"tipo_doc":data.tipo_doc,"doc":data.doc,"empresa":data.empresa,
        "cargo":data.cargo,"cliente_txt":data.cliente_txt,
        "eps":data.eps,"arl":data.arl,"ccf":data.ccf,"afp":data.afp,
        "subtipo":data.subtipo,"estado":data.estado,"estado_srv":data.estado_srv,
        "servicios":json.dumps(data.servicios),"tel":data.tel,
        "email":data.email,"dir":data.dir,"ciudad":data.ciudad,"novedades":data.novedades,"detalle":data.detalle,
        "ibc":data.ibc,"fecha_ingreso":data.fecha_ingreso,
        "fecha_afiliacion":data.fecha_afiliacion,"registrado_por":data.registrado_por,
    })
    db.add(a); _log(db, data.registrado_por, "agregó un afiliado nuevo", "Afiliados", data.nombre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(400, f"Ya existe un afiliado con documento {data.doc}")
    db.refresh(a); return _afiliado_to_dict(a)

def update_afiliado(db, id, data: schemas.AfiliadoCreate, editor=""):
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:"); cache_invalidar("afiliados:")
    # Lock de fila para evitar edición concurrente con eliminación
    a = db.query(models.Afiliado).filter_by(id=id, activo=True).with_for_update().first()
    if not a:
        raise HTTPException(404, "Afiliado no encontrado o fue eliminado por otro usuario")
    for field, val in [
        ("nombre",data.nombre),("tipo_doc",data.tipo_doc),("doc",data.doc),("empresa",data.empresa),
        ("cargo",data.cargo),("cliente_txt",data.cliente_txt),
        ("eps",data.eps),("arl",data.arl),("ccf",data.ccf),("afp",data.afp),
        ("subtipo",data.subtipo),("estado",data.estado),("estado_srv",data.estado_srv),
        ("servicios",json.dumps(data.servicios)),("tel",data.tel),
        ("email",data.email),("dir",data.dir),("ciudad",data.ciudad),("novedades",data.novedades),("detalle",data.detalle),
        ("ibc",data.ibc),("fecha_ingreso",data.fecha_ingreso),
        ("fecha_afiliacion",data.fecha_afiliacion),
    ]:
        setattr(a, field, val)
    _log(db, editor, "editó un afiliado", "Afiliados", data.nombre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(400, f"Ya existe otro afiliado con documento {data.doc}")
    db.refresh(a); return _afiliado_to_dict(a)

def delete_afiliado(db, id, deleted_by=""):
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:"); cache_invalidar("afiliados:")
    a = db.query(models.Afiliado).filter_by(id=id).first()
    if not a: return
    # Guardar en eliminados
    elim = models.Eliminado(
        nombre=a.nombre, doc=a.doc, empresa=a.empresa,
        datos_completos=json.dumps(_afiliado_to_dict(a)),
        fecha_eliminacion=datetime.now(COL_TZ).strftime("%Y-%m-%d"),
        mes=MESES[datetime.now(COL_TZ).month-1], eliminado_por=deleted_by,
    )
    db.add(elim)
    # Marcar TODAS las facturas del afiliado como huérfanas (no solo pendientes)
    db.query(models.Factura).filter_by(doc=a.doc).update(
        {"afiliado_eliminado": True})
    a.activo = False
    _log(db, deleted_by, "eliminó un afiliado", "Afiliados", a.nombre)
    db.commit()

# ─── FACTURAS ─────────────────────────────────────────────────────────────────
def _next_codigo(db):
    last = db.query(models.Factura).filter(models.Factura.codigo.like("FVE-%")).order_by(models.Factura.id.desc()).first()
    n = 2650
    if last:
        try: n = max(n, int(last.codigo.split("-")[1]))
        except: pass
    return f"FVE-{str(n+1).zfill(4)}"

def get_facturas(db, anio="", mes="", cliente="", estado="", banco="", doc="",
                skip: int = 0, limit: int = 0):
    """Lista facturas con filtros opcionales y paginación (skip/limit).
    Si limit=0 devuelve todas (para exportaciones Excel y dashboard).
    """
    q = db.query(models.Factura)
    if anio:    q = q.filter_by(anio=anio)
    if mes:     q = q.filter_by(mes=mes)
    if cliente: q = q.filter_by(cliente=cliente)
    if estado:  q = q.filter_by(estado=estado)
    if banco:   q = q.filter_by(banco=banco)
    if doc:     q = q.filter_by(doc=doc)
    total = q.count()
    q = q.order_by(models.Factura.id.desc())
    if limit > 0:
        q = q.offset(skip).limit(limit)
    items = q.all()
    # Obtener datos del afiliado en una sola consulta
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

def get_factura(db, id): f = db.query(models.Factura).filter_by(id=id).first(); return f
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
    # Retry para manejar race condition en código FVE concurrente
    max_retries = 3
    for attempt in range(max_retries):
        codigo = data.codigo or _next_codigo(db)
        f = models.Factura(
            codigo=codigo, nombre_afiliado=data.nombre_afiliado, doc=data.doc,
            cliente=data.cliente, anio=data.anio or str(datetime.now(COL_TZ).year),
            mes=data.mes, periodo=data.periodo, estado=data.estado, banco=data.banco,
            ingresos=data.ingresos, costos=data.costos, costo_adm=data.costo_adm,
            conceptos_extra=data.conceptos_extra,
            # utilidad server-side: ingreso − planilla_SS − cargo_adm + conceptos_extra
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
            data.codigo = ""  # forzar regeneración de código

def update_factura(db, id, data: schemas.FacturaUpdate, editor=""):
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    f = db.query(models.Factura).filter_by(id=id).first()
    if not f: return None

    # Punto 5: bloquear cambio de mes/anio en facturas ya pagadas
    PAGADAS = {"pagado", "planilla_pagada"}
    if f.estado in PAGADAS:
        campos = data.model_dump(exclude_none=True)
        if ("mes" in campos and campos["mes"] != f.mes) or \
           ("anio" in campos and campos["anio"] != f.anio):
            raise HTTPException(400, "No se puede cambiar el período de una factura ya pagada")

    for k, v in data.model_dump(exclude_none=True).items():
        if k in ("servicios_detalle","conceptos_detalle"): v = json.dumps(v)
        setattr(f, k, v)

    # recalcular utilidad server-side: ingreso − planilla_SS − cargo_adm + conceptos_extra
    f.utilidad = (f.ingresos or 0) - (f.costos or 0) - (f.costo_adm or 0) + (f.conceptos_extra or 0)

    _log(db, editor, "editó una factura", "Facturación", f.codigo)
    db.commit(); db.refresh(f); return _factura_to_dict(f)

def pagar_factura(db, id, banco="", user="", monto=None):
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    f = db.query(models.Factura).filter_by(id=id).with_for_update().first()
    if not f: return None
    if f.estado in ("pagado", "planilla_pagada"):
        return _factura_to_dict(f)  # idempotente
    if banco:
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
        return _factura_to_dict(f)  # idempotente
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
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")  # invalidar caché antes del commit
    db.commit()

# ─── RETIROS ──────────────────────────────────────────────────────────────────
def get_retiros(db, anio="", mes="", doc="", skip: int = 0, limit: int = 500):
    q = db.query(models.Retiro)
    if doc:  q = q.filter(models.Retiro.doc == doc)
    if anio: q = q.filter_by(anio=anio)
    if mes:  q = q.filter_by(mes=mes)
    total = q.count()
    rows = q.order_by(models.Retiro.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
                   "fecha":r.fecha,"motivo":r.motivo,"obs":r.obs,"mes":r.mes,
                   "anio":r.anio,"registrado_por":r.registrado_por} for r in rows],
    }

def create_retiro(db, data: schemas.RetiroCreate):
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    afil = get_afiliado_by_doc(db, data.doc)
    if not afil: return None
    # Verificar si ya tiene un retiro registrado
    retiro_existente = db.query(models.Retiro).filter_by(doc=data.doc).first()
    if retiro_existente:
        raise HTTPException(400,
            f"El afiliado ya tiene un retiro registrado del {retiro_existente.fecha}")
    afil.estado = "RETIRADO"; afil.estado_srv = "RETIRADO"
    anio_actual = str(datetime.now(COL_TZ).year)
    mes_actual  = MESES[datetime.now(COL_TZ).month-1]
    r = models.Retiro(
        nombre=afil.nombre, doc=data.doc, empresa=afil.empresa,
        fecha=data.fecha, motivo=data.motivo, obs=data.obs,
        mes=mes_actual, anio=anio_actual, registrado_por=data.registrado_por,
    )
    db.add(r)
    # Mover afiliado a eliminados al aplicar el retiro
    elim_existente = db.query(models.Eliminado).filter_by(doc=afil.doc).first()
    if not elim_existente:
        db.add(models.Eliminado(
            nombre=afil.nombre, doc=afil.doc, empresa=afil.empresa,
            datos_completos=json.dumps(_afiliado_to_dict(afil)),
            fecha_eliminacion=datetime.now(COL_TZ).strftime("%Y-%m-%d"),
            mes=mes_actual, eliminado_por=data.registrado_por,
        ))
    afil.activo = False
    _log(db, data.registrado_por, "aplicó un retiro y movió a eliminados", "Retiros", afil.nombre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Otro empleado ya registró este retiro. Recargue la página.")
    db.refresh(r)
    return {"id":r.id,"nombre":r.nombre,"doc":r.doc,"fecha":r.fecha,"motivo":r.motivo}

def delete_retiro(db, id, user=""):
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    r = db.query(models.Retiro).filter_by(id=id).first()
    if not r:
        return
    _log(db, user, "eliminó un retiro (→ eliminados)", "Retiros", r.nombre)
    # Mover el afiliado a eliminados en lugar de reactivarlo
    afil = db.query(models.Afiliado).filter_by(doc=r.doc).first()
    if afil:
        elim_existente = db.query(models.Eliminado).filter_by(doc=r.doc).first()
        if not elim_existente:
            elim = models.Eliminado(
                nombre=afil.nombre, doc=afil.doc, empresa=afil.empresa,
                datos_completos=json.dumps(_afiliado_to_dict(afil)),
                fecha_eliminacion=datetime.now(COL_TZ).strftime("%Y-%m-%d"),
                mes=MESES[datetime.now(COL_TZ).month-1], eliminado_por=user,
            )
            db.add(elim)
        afil.activo = False
        _log(db, user, "afiliado movido a eliminados por eliminación de retiro", "Afiliados", afil.nombre)
    db.query(models.Retiro).filter_by(id=id).delete()
    db.commit()


def eliminado_a_retiro(db, eliminado_id, user=""):
    """Crea un registro de retiro a partir de un eliminado (para historial)."""
    from fastapi import HTTPException
    e = db.query(models.Eliminado).filter_by(id=eliminado_id).first()
    if not e:
        raise HTTPException(404, "Eliminado no encontrado")
    retiro_existente = db.query(models.Retiro).filter_by(doc=e.doc).first()
    if retiro_existente:
        raise HTTPException(400, f"Ya existe un retiro registrado para el documento {e.doc}")
    anio_actual = str(datetime.now(COL_TZ).year)
    mes_actual  = MESES[datetime.now(COL_TZ).month-1]
    r = models.Retiro(
        nombre=e.nombre, doc=e.doc, empresa=e.empresa,
        fecha=e.fecha_eliminacion or datetime.now(COL_TZ).strftime("%Y-%m-%d"),
        motivo="ELIMINADO", obs="",
        mes=mes_actual, anio=anio_actual, registrado_por=user,
    )
    db.add(r)
    _log(db, user, "agregó a historial de retiros desde eliminados", "Retiros", e.nombre)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "nombre": r.nombre, "doc": r.doc}

# ─── EMPLEADOS ────────────────────────────────────────────────────────────────
def get_empleados(db):
    return [{"id":e.id,"nombre":e.nombre,"doc":e.doc,"cargo":e.cargo,
             "tel":e.tel,"email":e.email,"usuario":e.usuario,
             "nomina":e.nomina,"activo":e.activo,"fecha_ingreso":e.fecha_ingreso}
            for e in db.query(models.Empleado).all()]

def create_empleado(db, data: schemas.EmpleadoCreate):
    e = models.Empleado(**data.model_dump())
    db.add(e); db.commit(); db.refresh(e)
    return {"id":e.id,"nombre":e.nombre,"nomina":e.nomina}

def update_empleado(db, id, data: schemas.EmpleadoCreate):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if not e: return None
    for k,v in data.model_dump().items(): setattr(e,k,v)
    db.commit(); db.refresh(e)
    return {"id":e.id,"nombre":e.nombre,"nomina":e.nomina}

def delete_empleado(db, id, user=""):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if e:
        _log(db, user, "eliminó un empleado", "Empleados", e.nombre)
        db.delete(e)
        db.commit()

# ─── GASTOS MENSUALES ─────────────────────────────────────────────────────────
def get_ingresos_adicionales(db, mes: int = None, anio: int = None):
    q = db.query(models.IngresoAdicional)
    if mes:  q = q.filter_by(mes=mes)
    if anio: q = q.filter_by(anio=anio)
    return [{"id": i.id, "concepto": i.concepto, "descripcion": i.descripcion,
             "valor": i.valor, "mes": i.mes, "anio": i.anio, "creado_por": i.creado_por,
             "creado": i.creado.isoformat() if i.creado else None}
            for i in q.order_by(models.IngresoAdicional.creado.desc()).all()]

def create_ingreso_adicional(db, data, user=""):
    cache_invalidar("dashboard:")
    i = models.IngresoAdicional(concepto=data.concepto, descripcion=data.descripcion,
                                 valor=data.valor, mes=data.mes, anio=data.anio, creado_por=user)
    db.add(i); db.commit(); db.refresh(i)
    _log(db, user, "agregó ingreso adicional", "Facturación", f"{data.concepto} ${data.valor:,.0f}")
    return {"id": i.id, "concepto": i.concepto, "descripcion": i.descripcion,
            "valor": i.valor, "mes": i.mes, "anio": i.anio, "creado_por": i.creado_por,
            "creado": i.creado.isoformat() if i.creado else None}

def delete_ingreso_adicional(db, id, user=""):
    cache_invalidar("dashboard:")
    i = db.query(models.IngresoAdicional).filter_by(id=id).first()
    if not i: return False
    _log(db, user, "eliminó ingreso adicional", "Facturación", f"{i.concepto} ${i.valor:,.0f}")
    db.delete(i); db.commit(); return True


def get_gastos(db, mes: int, anio: int):
    return [{"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}
            for g in db.query(models.Gasto).filter_by(mes=mes, anio=anio).order_by(models.Gasto.nombre).all()]

def create_gasto(db, data: schemas.GastoCreate):
    g = models.Gasto(nombre=data.nombre, valor=data.valor, mes=data.mes, anio=data.anio)
    db.add(g); db.commit(); db.refresh(g)
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}

def update_gasto(db, id: int, data: schemas.GastoUpdate):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if not g: return None
    g.nombre = data.nombre; g.valor = data.valor
    db.commit()
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}

def delete_gasto(db, id, user=""):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if g:
        _log(db, user, "eliminó un gasto", "Gastos", g.nombre)
        db.delete(g)
        db.commit()

def copiar_gastos_mes_anterior(db, origen_mes: int, origen_anio: int, dest_mes: int, dest_anio: int, user: str = ""):
    db.query(models.Gasto).filter_by(mes=dest_mes, anio=dest_anio).delete()
    origen = db.query(models.Gasto).filter_by(mes=origen_mes, anio=origen_anio).all()
    for g in origen:
        db.add(models.Gasto(nombre=g.nombre, valor=g.valor, mes=dest_mes, anio=dest_anio))
    db.commit()
    _log(db, user, "copió gastos", "Gastos", f"{origen_mes}/{origen_anio} → {dest_mes}/{dest_anio}")
    return get_gastos(db, dest_mes, dest_anio)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
def get_config(db):
    cached = _cache_get("config:global")
    if cached is not None:
        return cached
    c = db.query(models.Config).first()
    if not c: return {"ibc_global":1_950_905,"porcentajes":{},"plantilla_whatsapp":"","cargo_adicional":2200,"mes_inicio_cobro":None,"anio_inicio_cobro":None}
    result = {
        "ibc_global": float(c.ibc_global) if c.ibc_global is not None else 1_950_905,
        "porcentajes": json.loads(c.porcentajes or "{}"),
        "plantilla_whatsapp": c.plantilla_whatsapp or "",
        "cargo_adicional": float(c.cargo_adicional) if c.cargo_adicional is not None else 2200,
        "mes_inicio_cobro": c.mes_inicio_cobro,
        "anio_inicio_cobro": c.anio_inicio_cobro,
    }
    _cache_set("config:global", result, ttl=TTL_CONFIG)
    return result

def update_config(db, data: schemas.ConfigUpdate, user="sistema"):
    c = db.query(models.Config).first()
    if not c:
        c = models.Config()
        db.add(c)
    if data.ibc_global is not None: c.ibc_global = data.ibc_global
    if data.porcentajes is not None: c.porcentajes = json.dumps(data.porcentajes)
    if data.plantilla_whatsapp is not None: c.plantilla_whatsapp = data.plantilla_whatsapp
    if data.cargo_adicional is not None: c.cargo_adicional = data.cargo_adicional
    if data.mes_inicio_cobro is not None: c.mes_inicio_cobro = data.mes_inicio_cobro
    if data.anio_inicio_cobro is not None: c.anio_inicio_cobro = data.anio_inicio_cobro
    _log(db, user, "actualizó configuración global", "Config", "")
    cache_invalidar("config:")
    db.commit(); return get_config(db)

# ─── LISTAS ───────────────────────────────────────────────────────────────────
def get_listas(db):
    cached = _cache_get("listas:all")
    if cached is not None:
        return cached
    result = {l.nombre: json.loads(l.items or "[]") for l in db.query(models.Lista).all()}
    _cache_set("listas:all", result, ttl=TTL_LISTAS)
    return result

def update_lista(db, nombre, items, user="sistema"):
    l = db.query(models.Lista).filter_by(nombre=nombre).first()
    if not l: l = models.Lista(nombre=nombre); db.add(l)
    l.items = json.dumps(items)
    _log(db, user, "actualizó lista", "Listas", nombre)
    cache_invalidar("listas:")
    db.commit()
    return {"nombre":nombre,"items":items}

# ─── ACTIVIDAD ────────────────────────────────────────────────────────────────
def get_actividad(db, modulo="", usuario="", desde="", hasta="",
                  skip: int = 0, limit: int = 200):
    from datetime import datetime as _dt
    q = db.query(models.Actividad)
    if modulo:  q = q.filter_by(modulo=modulo)
    if usuario: q = q.filter_by(usuario=usuario)
    if desde:
        try:
            q = q.filter(models.Actividad.fecha >= _dt.fromisoformat(desde))
        except ValueError:
            pass
    if hasta:
        try:
            hasta_fin = _dt.fromisoformat(hasta).replace(hour=23, minute=59, second=59)
            q = q.filter(models.Actividad.fecha <= hasta_fin)
        except ValueError:
            pass
    total = q.count()
    q = q.order_by(models.Actividad.id.desc())
    if limit > 0:
        q = q.offset(skip).limit(limit)
    rows = q.all()
    return {"total": total, "items": [
        {"id":r.id,"usuario":r.usuario,"accion":r.accion,"modulo":r.modulo,
         "detalle":r.detalle,"fecha":r.fecha.replace(tzinfo=timezone.utc).astimezone(COL_TZ).strftime("%d/%m/%Y %H:%M:%S") if r.fecha else ""}
        for r in rows
    ]}

def clear_actividad(db, user=""):
    db.query(models.Actividad).delete()
    db.add(models.Actividad(usuario=user, accion="limpió el historial de actividad",
                            modulo="Sistema", detalle="Historial borrado"))
    db.commit()

# ─── NÓMINA MENSUAL ───────────────────────────────────────────────────────────
def get_nomina_mensual(db, mes: int, anio: int):
    empleados = db.query(models.Empleado).filter_by(activo=True).order_by(models.Empleado.nombre).all()
    registros = {r.empleado_id: r.valor for r in
                 db.query(models.NominaMensual).filter_by(mes=mes, anio=anio).all()}
    return [{"empleado_id": e.id, "nombre": e.nombre, "cargo": e.cargo,
             "valor": registros.get(e.id, 0.0)} for e in empleados]

def upsert_nomina_mensual(db, empleado_id: int, mes: int, anio: int, valor: float, user: str = ""):
    r = db.query(models.NominaMensual).filter_by(empleado_id=empleado_id, mes=mes, anio=anio).first()
    if r:
        r.valor = valor
    else:
        db.add(models.NominaMensual(empleado_id=empleado_id, mes=mes, anio=anio, valor=valor))
    db.commit()
    e = db.query(models.Empleado).filter_by(id=empleado_id).first()
    nombre = e.nombre if e else str(empleado_id)
    _log(db, user, "actualizó nómina mensual", "Nómina", f"{nombre} {mes}/{anio}")
    return {"empleado_id": empleado_id, "mes": mes, "anio": anio, "valor": valor}

def copiar_nomina_mes_anterior(db, origen_mes: int, origen_anio: int, dest_mes: int, dest_anio: int, user: str = ""):
    empleados = db.query(models.Empleado).filter_by(activo=True).all()
    registros_origen = {r.empleado_id: r.valor for r in
                        db.query(models.NominaMensual).filter_by(mes=origen_mes, anio=origen_anio).all()}
    db.query(models.NominaMensual).filter_by(mes=dest_mes, anio=dest_anio).delete()
    for e in empleados:
        valor = registros_origen.get(e.id, e.nomina)
        db.add(models.NominaMensual(empleado_id=e.id, mes=dest_mes, anio=dest_anio, valor=valor))
    db.commit()
    _log(db, user, "copió nómina", "Nómina", f"{origen_mes}/{origen_anio} → {dest_mes}/{dest_anio}")
    return get_nomina_mensual(db, dest_mes, dest_anio)

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
def get_dashboard(db, anio="", mes=""):
    cache_key = f"dashboard:{anio}:{mes}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from sqlalchemy import func, case
    # Contar afiliados por estado con una sola query SQL
    stats = db.query(
        func.count(models.Afiliado.id).label("total"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%ACTIVO%"), 1), else_=0)).label("activos"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%RETIR%"),  1), else_=0)).label("retirados"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%SUSPENDIDO%"), 1), else_=0)).label("suspendidos"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%DOBLE%"), 1), else_=0)).label("doble_afiliacion"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%NO SE ENCUENTRA%"), 1), else_=0)).label("no_encontrado"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%ESPERA%"), 1), else_=0)).label("en_espera"),
    ).filter(models.Afiliado.activo==True).one()

    # Una sola query cubre el período filtrado Y el total histórico de pendiente.
    # Se usan CASE en vez de WHERE para poder calcular pend_total (sin filtro) en el mismo SELECT.
    from sqlalchemy import and_, true as sa_true
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
        # total_impuestos: cargo adicional/mora/4x1000 de facturas planilla_pagada en el período
        func.coalesce(func.sum(case((and_(planilla_ok, period_ok),   models.Factura.costo_adm), else_=0)), 0).label("total_impuestos"),
        func.sum(case((and_(planilla_ok, period_ok), 1), else_=0)).label("n_planillas"),
        func.coalesce(func.sum(case((and_(pending_ok, period_ok), models.Factura.ingresos), else_=0)), 0).label("pendiente"),
        func.sum(case((and_(pending_ok, period_ok), 1), else_=0)).label("n_pend"),
        # pend_total: saldo histórico cobrable — excluye afiliados eliminados
        func.coalesce(func.sum(case(
            (and_(pending_ok, models.Factura.afiliado_eliminado == False), models.Factura.ingresos),
            else_=0
        )), 0).label("pend_total"),
    ).one()


    # Nómina y gastos: si hay mes específico → ese mes; si hay solo año → suma todos los meses del año
    _anio_ref = int(anio) if anio else datetime.now(COL_TZ).year
    if mes:
        # mes llega como nombre español ("Enero") — convertir a índice 1-12
        _mes_ref = (MESES.index(mes) + 1) if mes in MESES else int(mes)
        nominas = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(
            mes=_mes_ref, anio=_anio_ref).scalar()
        gastos  = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(
            mes=_mes_ref, anio=_anio_ref).scalar()
        ing_adic = db.query(func.coalesce(func.sum(models.IngresoAdicional.valor), 0)).filter_by(
            mes=_mes_ref, anio=_anio_ref).scalar()
    elif anio:
        # Año completo: sumar todos los meses registrados de ese año
        nominas = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(
            anio=_anio_ref).scalar()
        gastos  = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(
            anio=_anio_ref).scalar()
        ing_adic = db.query(func.coalesce(func.sum(models.IngresoAdicional.valor), 0)).filter_by(
            anio=_anio_ref).scalar()
    else:
        # Sin filtro → mes actual
        _mes_ref = datetime.now(COL_TZ).month
        nominas = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(
            mes=_mes_ref, anio=_anio_ref).scalar()
        gastos  = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(
            mes=_mes_ref, anio=_anio_ref).scalar()
        ing_adic = db.query(func.coalesce(func.sum(models.IngresoAdicional.valor), 0)).filter_by(
            mes=_mes_ref, anio=_anio_ref).scalar()

    ing_adic = float(ing_adic)
    util_neta = float(facts.utilidad) + ing_adic - float(nominas) - float(gastos)

    pend_total = float(facts.pend_total)

    # total_impuestos: usa costo_adm si fue guardado; si no (facturas históricas),
    # fallback a count(planilla_pagada) × cargo_adicional del config
    _total_impuestos = float(facts.total_impuestos)
    if _total_impuestos == 0 and int(facts.n_planillas or 0) > 0:
        _cfg = db.query(models.Config.cargo_adicional).first()
        _cargo = float(_cfg.cargo_adicional) if _cfg and _cfg.cargo_adicional else 2200.0
        _total_impuestos = int(facts.n_planillas) * _cargo

    # Factor de meses para las etiquetas
    meses_factor = 1 if (mes or not anio) else 12

    # Ingresos por banco (facturas pagadas/planilla_pagada en el período)
    banco_q = db.query(
        models.Factura.banco,
        func.coalesce(func.sum(models.Factura.ingresos), 0).label("total"),
    ).filter(
        models.Factura.estado.in_(["pagado", "planilla_pagada"]),
        period_ok,
    ).group_by(models.Factura.banco).all()
    # Normaliza nombres (ej. "DaviPlata" y "Daviplata" → mismo grupo)
    _BANCO_CANON = {
        "daviplata": "Daviplata",
        "nequi": "Nequi",
        "davivienda": "Davivienda",
        "bancolombia": "Bancolombia",
        "banco de bogotá": "Banco de Bogotá",
        "banco de bogota": "Banco de Bogotá",
        "efectivo": "Efectivo",
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
    """Rentabilidad por cliente — tabla comparativa para módulo Finanzas."""
    cache_key = f"dashboard_clientes:{anio}:{mes}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    from sqlalchemy import func, case, and_, true as sa_true

    period_conds = []
    if anio: period_conds.append(models.Factura.anio == anio)
    if mes:  period_conds.append(models.Factura.mes  == mes)
    period_ok  = and_(*period_conds) if period_conds else sa_true()
    paid_ok    = models.Factura.estado.in_(["pagado", "planilla_pagada"])
    pending_ok = models.Factura.estado == "pendiente"

    fact_rows = db.query(
        models.Factura.cliente,
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.ingresos), else_=0)), 0).label("ingresos"),
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.costos),   else_=0)), 0).label("costos"),
        func.coalesce(func.sum(case((and_(pending_ok, period_ok), models.Factura.ingresos), else_=0)), 0).label("pendiente"),
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
        ing  = float(r.ingresos)
        cos  = float(r.costos)
        util = ing - cos
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
    """KPIs financieros + afiliados + historial para un cliente específico."""
    from sqlalchemy import func, case, and_, true as sa_true

    period_conds = []
    if anio: period_conds.append(models.Factura.anio == anio)
    if mes:  period_conds.append(models.Factura.mes  == mes)
    period_ok  = and_(*period_conds) if period_conds else sa_true()
    paid_ok    = models.Factura.estado.in_(["pagado", "planilla_pagada"])
    pending_ok = models.Factura.estado == "pendiente"

    facts = db.query(
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.ingresos), else_=0)), 0).label("ingresos"),
        func.coalesce(func.sum(case((and_(paid_ok,    period_ok), models.Factura.costos),   else_=0)), 0).label("costos"),
        func.coalesce(func.sum(case((and_(pending_ok, period_ok), models.Factura.ingresos), else_=0)), 0).label("pendiente"),
        func.sum(case((and_(paid_ok,    period_ok), 1), else_=0)).label("n_pagadas"),
        func.sum(case((and_(pending_ok, period_ok), 1), else_=0)).label("n_pendientes"),
    ).filter(models.Factura.cliente == cliente).one()

    stats = db.query(
        func.count(models.Afiliado.id).label("total"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%ACTIVO%"),           1), else_=0)).label("activos"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%SUSPENDIDO%"),       1), else_=0)).label("suspendidos"),
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
    ).order_by(models.Factura.anio.desc(), models.Factura.mes.desc()).limit(6).all()

    historial = []
    for r in reversed(hist_rows):
        mes_num = (MESES.index(r.mes) + 1) if r.mes in MESES else 0
        historial.append({
            "anio": r.anio, "mes": r.mes, "mes_num": mes_num,
            "ingresos": float(r.ingresos), "costos": float(r.costos),
            "n": int(r.n or 0),
        })

    ing  = float(facts.ingresos)
    cos  = float(facts.costos)
    util = ing - cos
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


# ─── CACHÉ (Redis en producción, dict en memoria para dev) ───────────────────
import time as _time
import os as _os

# TTL diferenciados según frecuencia de cambio
TTL_COBRO     = 600    # 10 min — cambia con cada factura/afiliado; invalidación explícita en mutaciones
TTL_DASHBOARD = 300    # 5 min  — mismo ritmo que cobro
TTL_AFILIADOS = 180    # 3 min  — consultas frecuentes durante jornada
TTL_CONFIG    = 600    # 10 min — cambia solo cuando admin edita configuración
TTL_LISTAS    = 1800   # 30 min — EPS, ARL, tipos de cotizante (casi estáticos)

# Intentar conectar a Redis si REDIS_URL está disponible
_redis_client = None
try:
    _redis_url = _os.getenv("REDIS_URL")
    if _redis_url:
        import redis as _redis_mod
        _redis_client = _redis_mod.from_url(_redis_url, decode_responses=True)
        _redis_client.ping()  # verificar conexión
except Exception as _redis_err:
    _redis_client = None  # fallback a cache en memoria
    from logger import logger as _rlog
    _rlog.warning(f"Redis no disponible, usando cache en memoria: {_redis_err}")

# Fallback: cache en memoria (para desarrollo local sin Redis)
import threading as _threading
_mem_cache: dict = {}
_cache_lock = _threading.Lock()

# Circuit breaker para Redis — evita que Redis lento bloquee la app
_cb_failures   = 0
_cb_open_until = 0.0
_CB_MAX_FAILS  = 5
_CB_COOLDOWN   = 30  # segundos antes de reintentar Redis


def _redis_disponible() -> bool:
    """Retorna True si Redis está disponible según el circuit breaker."""
    global _cb_failures, _cb_open_until
    if not _redis_client:
        return False
    if _cb_failures >= _CB_MAX_FAILS:
        if _time.time() < _cb_open_until:
            return False  # circuito abierto
        # Cooldown terminó — half-open: dejar pasar un intento
    return True


def _redis_on_success():
    global _cb_failures
    _cb_failures = 0


def _redis_on_failure():
    global _cb_failures, _cb_open_until
    _cb_failures += 1
    if _cb_failures >= _CB_MAX_FAILS:
        _cb_open_until = _time.time() + _CB_COOLDOWN
        from logger import logger as _cblog
        _cblog.warning(f"Redis circuit breaker abierto — {_CB_COOLDOWN}s de pausa")


def _use_mem_cache() -> bool:
    """True solo cuando Redis no está configurado (desarrollo sin Redis).
    En producción con Redis configurado, nunca usar dict en memoria — evita
    inconsistencia entre workers cuando el circuit breaker está abierto.
    """
    return _redis_client is None


def _cache_get(key: str):
    """Obtiene un valor del caché (Redis o memoria)."""
    if _redis_disponible():
        try:
            raw = _redis_client.get(key)
            _redis_on_success()
            if raw:
                return json.loads(raw)
        except Exception:
            _redis_on_failure()
        return None
    if not _use_mem_cache():
        return None  # Redis configurado pero caído → cache miss (dato fresco de DB)
    # Fallback memoria solo en dev (sin Redis)
    with _cache_lock:
        entry = _mem_cache.get(key)
        if entry and (_time.time() - entry["ts"]) < entry["ttl"]:
            return entry["data"]
        return None


def _cache_set(key: str, data, ttl: int = TTL_COBRO):
    """Guarda un valor en el caché con TTL configurable."""
    if _redis_disponible():
        try:
            _redis_client.setex(key, ttl, json.dumps(data, default=str))
            _redis_on_success()
        except Exception:
            _redis_on_failure()
        return
    if not _use_mem_cache():
        return  # Redis configurado pero caído → no guardar en dict
    # Fallback memoria solo en dev (sin Redis)
    with _cache_lock:
        _mem_cache[key] = {"data": data, "ts": _time.time(), "ttl": ttl}
        if len(_mem_cache) > 500:
            now = _time.time()
            expired = [k for k, v in list(_mem_cache.items()) if (now - v["ts"]) >= v["ttl"]]
            for k in expired:
                _mem_cache.pop(k, None)
            if len(_mem_cache) > 500:
                oldest = sorted(_mem_cache.items(), key=lambda x: x[1]["ts"])[:100]
                for k, _ in oldest:
                    _mem_cache.pop(k, None)


def cache_invalidar(prefijo: str = ""):
    """Invalida entradas del caché que empiecen con el prefijo dado."""
    if _redis_disponible():
        try:
            cursor = 0
            while True:
                cursor, keys = _redis_client.scan(cursor, match=f"{prefijo}*", count=100)
                if keys:
                    _redis_client.delete(*keys)
                if cursor == 0:
                    break
            _redis_on_success()
        except Exception:
            _redis_on_failure()
        return
    # Fallback memoria
    with _cache_lock:
        keys = [k for k in _mem_cache if k.startswith(prefijo)]
        for k in keys:
            del _mem_cache[k]

# ─── MÓDULO DE COBRO ──────────────────────────────────────────────────────────
def get_cobro(db, empresa="", cliente="", tipo="", mes="", anio="", doc=""):
    """Calcula el estado de cobro por afiliado y mes (últimos 6 meses).
    Genera una fila por cada mes pendiente de cada afiliado.
    El caché se invalida automáticamente al crear/editar/eliminar facturas o afiliados.

    Optimizaciones:
    - Filtros empresa/cliente/doc van al SQL — no al Python
    - estado_srv usa notin() en vez de ilike(%RETIR%) — permite Index-Only Scan
    - load_only() carga solo las columnas necesarias — no trae obs/detalle/dir/etc.
    - Filtros tipo/mes/anio aplicados dentro del loop — no construye rows descartables
    """
    cache_key = f"cobro:{empresa}:{cliente}:{tipo}:{mes}:{anio}:{doc}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    hoy = datetime.now(COL_TZ)
    dia_hoy = hoy.day

    # Generar los últimos 6 meses (mes-5 ... mes actual) como lista (año, mes_idx 1-12)
    meses_ventana = []
    for i in range(5, -1, -1):
        m = hoy.month - i
        y = hoy.year
        while m <= 0:
            m += 12
            y -= 1
        meses_ventana.append((y, m))   # [(2025,10),(2025,11),...,(2026,3)]

    # Pre-cargar config
    cfg = db.query(models.Config).first()
    ibc_global = float(cfg.ibc_global) if cfg else 1_950_905
    pcts = json.loads(cfg.porcentajes or "{}") if cfg else {}
    # Fecha de corte global: el módulo de cobro ignora meses anteriores a esta fecha
    _corte = (cfg.anio_inicio_cobro, cfg.mes_inicio_cobro) if cfg and cfg.anio_inicio_cobro and cfg.mes_inicio_cobro else None

    # Pre-cargar TODAS las facturas de los últimos 6 meses → set de (doc, mes, anio)
    # Usamos pares exactos (anio, mes) para evitar que una factura de Nov 2026 cuente como Nov 2025
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
        if (f.anio, f.mes) in _pares_validos  # excluye combinaciones inválidas entre años
    )

    # Filtros SQL — empresa/cliente/doc reducen filas antes de cargar objetos
    # notin() en estado_srv permite usar ix_afiliado_cobro_cobertura (Index-Only Scan)
    # load_only() evita traer campos Text pesados (obs, detalle, dir, email, etc.)
    from sqlalchemy.orm import load_only
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
    ))
    if empresa: q = q.filter(models.Afiliado.empresa == empresa)
    if cliente: q = q.filter(models.Afiliado.cliente_txt == cliente)
    if doc:     q = q.filter(models.Afiliado.doc == doc)

    afils = q.all()

    rows = []
    for a in afils:
        fa = a.fecha_afiliacion or a.fecha_ingreso or ""
        if not fa or "-" not in fa: continue
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

        # Primer cobro = mes siguiente a la afiliación
        primer_cobro_m = afil_month + 1
        primer_cobro_y = afil_year
        if primer_cobro_m > 12:
            primer_cobro_m = 1
            primer_cobro_y += 1

        for (y, m) in meses_ventana:
            # No mostrar meses anteriores al primer cobro (mes siguiente a afiliación)
            if (y, m) < (primer_cobro_y, primer_cobro_m): continue
            # No mostrar meses anteriores a la fecha de corte global del sistema
            if _corte and (y, m) < _corte: continue
            # Filtros mes/anio dentro del loop — evita construir rows que se descartan
            if mes  and MESES[m - 1] != mes: continue
            if anio and str(y) != anio:      continue

            mes_nombre = MESES[m - 1]
            anio_str   = str(y)
            tiene_fac  = (a.doc, mes_nombre, anio_str) in facturas_set
            es_actual  = (y == hoy.year and m == hoy.month)

            if tiene_fac:
                estado = "COBRADO"
            elif not es_actual:
                estado = "VENCIDO"   # mes pasado sin factura
            else:
                # Mes actual: usar día de cobro
                if dia_afil < dia_hoy:        estado = "VENCIDO"
                elif dia_afil == dia_hoy:     estado = "HOY"
                elif dia_afil == dia_hoy + 1: estado = "PROXIMO"
                else:
                    continue  # aún no se muestra — el día no ha llegado

            # Filtro tipo dentro del loop — no construir el dict para descartarlo
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

# ─── TAREAS ───────────────────────────────────────────────────────────────────
_ESTADO_LABEL = {
    "pendiente":   "Pendiente",
    "en_proceso":  "En proceso",
    "completada":  "Completada",
    "finalizada":  "Finalizada",
}

def _tarea_to_dict(t, comentarios_map=None):
    coms = comentarios_map.get(t.id, []) if comentarios_map else []
    return {
        "id": t.id, "titulo": t.titulo, "descripcion": t.descripcion,
        "asignado_a": t.asignado_a, "creado_por": t.creado_por,
        "estado": t.estado,
        "fecha_limite": t.fecha_limite or "",
        "privada": bool(t.privada),
        "creado": t.creado.isoformat(),
        "completado_en": t.completado_en.isoformat() if t.completado_en else None,
        "finalizado_en": t.finalizado_en.isoformat() if t.finalizado_en else None,
        "finalizado_por": t.finalizado_por or "",
        "comentarios": [{"id": c.id, "usuario": c.usuario, "texto": c.texto,
                         "creado": c.creado.isoformat()} for c in coms]
    }

def _load_comments_map(db, task_ids):
    """Carga todos los comentarios para una lista de tareas en una sola query."""
    if not task_ids:
        return {}
    comments = db.query(models.TareaComentario)\
        .filter(models.TareaComentario.tarea_id.in_(task_ids))\
        .order_by(models.TareaComentario.creado).all()
    m = {}
    for c in comments:
        m.setdefault(c.tarea_id, []).append(c)
    return m

def create_tarea(db, data: schemas.TareaCreate):
    t = models.Tarea(**data.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    # No notificar en tareas privadas (el creador es el asignado)
    if not data.privada:
        db.add(models.Notificacion(
            usuario=data.asignado_a,
            mensaje=f"Nueva tarea asignada: {data.titulo}",
            tarea_id=t.id
        ))
        db.commit()
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def get_tareas(db, username: str, rol: str, skip: int = 0, limit: int = 200):
    from sqlalchemy import or_
    q = db.query(models.Tarea)
    if rol != "admin":
        q = q.filter_by(asignado_a=username)
    q = q.filter(or_(models.Tarea.privada == False, models.Tarea.creado_por == username))
    total = q.count()
    tareas = q.order_by(models.Tarea.creado.desc()).offset(skip).limit(limit).all()
    # Batch load comments: 1 query instead of N
    cmap = _load_comments_map(db, [t.id for t in tareas])
    return {
        "total": total,
        "items": [_tarea_to_dict(t, cmap) for t in tareas],
    }

def cambiar_estado_tarea(db, tarea_id: int, nuevo_estado: str, usuario: str, nota: str = "", rol: str = ""):
    """Empleado cambia estado (pendiente→en_proceso→completada). Notifica al admin."""
    estados_validos = ["pendiente", "en_proceso", "completada"]
    if nuevo_estado not in estados_validos:
        return None
    t = db.query(models.Tarea).filter_by(id=tarea_id).with_for_update().first()
    if not t:
        return {"error": "not_found"}
    # Solo admin o el asignado pueden cambiar el estado
    if rol != "admin" and t.asignado_a != usuario:
        return {"error": "unauthorized"}
    estado_anterior = t.estado
    t.estado = nuevo_estado
    if nuevo_estado == "completada":
        t.completado_en = datetime.now(timezone.utc)
    if nota:
        db.add(models.TareaComentario(tarea_id=tarea_id, usuario=usuario, texto=nota))
    label_nuevo = _ESTADO_LABEL.get(nuevo_estado, nuevo_estado)
    db.add(models.Notificacion(
        usuario=t.creado_por,
        mensaje=f"{usuario} cambió la tarea '{t.titulo}' a: {label_nuevo}",
        tarea_id=tarea_id
    ))
    db.commit()
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def finalizar_tarea(db, tarea_id: int, admin_username: str):
    """Admin finaliza una tarea completada. Queda en historial como finalizada."""
    t = db.query(models.Tarea).filter_by(id=tarea_id).with_for_update().first()
    if not t: return None
    if t.estado != "completada":
        return {"error": "Solo se pueden finalizar tareas en estado 'completada'"}
    t.estado = "finalizada"
    t.finalizado_en = datetime.now(timezone.utc)
    t.finalizado_por = admin_username
    db.add(models.Notificacion(
        usuario=t.asignado_a,
        mensaje=f"Tu tarea '{t.titulo}' fue finalizada por {admin_username}",
        tarea_id=tarea_id
    ))
    db.commit()
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def add_comentario(db, tarea_id: int, data: schemas.TareaComentarioCreate):
    t = db.query(models.Tarea).filter_by(id=tarea_id).first()
    if not t: return None
    c = models.TareaComentario(tarea_id=tarea_id, **data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "tarea_id": c.tarea_id, "usuario": c.usuario,
            "texto": c.texto, "creado": c.creado.isoformat()}

def get_notificaciones(db, username: str):
    items = db.query(models.Notificacion).filter_by(usuario=username)\
               .order_by(models.Notificacion.creado.desc()).limit(50).all()
    return [{"id": n.id, "mensaje": n.mensaje, "leida": n.leida,
             "tarea_id": n.tarea_id, "creado": n.creado.isoformat()} for n in items]

def marcar_notificaciones_leidas(db, username: str):
    db.query(models.Notificacion).filter_by(usuario=username, leida=False)\
      .update({"leida": True})
    db.commit()
