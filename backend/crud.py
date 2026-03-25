from sqlalchemy.orm import Session
from sqlalchemy import or_
import models, schemas, json, math
from datetime import datetime
from typing import Optional
from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    # Soporta contraseñas antiguas en texto plano durante migración
    if not hashed.startswith("$2"):
        return plain == hashed
    return _pwd_ctx.verify(plain, hashed)

MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def _log(db: Session, usuario: str, accion: str, modulo: str, detalle: str = ""):
    db.add(models.Actividad(usuario=usuario, accion=accion, modulo=modulo, detalle=detalle))

def _get_ibc(db: Session, afiliado: models.Afiliado = None) -> float:
    if afiliado and afiliado.ibc and afiliado.ibc > 0:
        return afiliado.ibc
    cfg = db.query(models.Config).first()
    return cfg.ibc_global if cfg else 1_950_905

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
        "tel": a.tel, "email": a.email, "dir": a.dir, "obs": a.obs, "novedades": a.novedades, "detalle": a.detalle or "",
        "ibc": a.ibc, "fecha_ingreso": a.fecha_ingreso,
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
        "ingresos": f.ingresos, "costos": f.costos,
        "costo_adm": f.costo_adm, "conceptos_extra": f.conceptos_extra,
        "utilidad": f.utilidad, "novedades": f.novedades,
        "servicios_detalle": srv,
        "conceptos_detalle": conc,
        "afiliado_eliminado": f.afiliado_eliminado,
        "pagado_en": f.pagado_en.isoformat() if f.pagado_en else None,
        "creado_por": f.creado_por,
        "creado": f.creado.isoformat() if f.creado else None,
    }

# ─── USUARIOS ─────────────────────────────────────────────────────────────────
def get_user_by_username(db, username): return db.query(models.Usuario).filter_by(username=username).first()
def get_usuario(db, id): return db.query(models.Usuario).filter_by(id=id).first()
def get_usuarios(db): return [{"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"activo":u.activo,"cliente_ref":u.cliente_ref} for u in db.query(models.Usuario).all()]
def create_usuario(db, data: schemas.UsuarioCreate):
    u = models.Usuario(nombre=data.nombre, username=data.username, password=hash_password(data.password), rol=data.rol, cliente_ref=data.cliente_ref)
    db.add(u); db.commit(); db.refresh(u)
    return {"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"cliente_ref":u.cliente_ref}
def delete_usuario(db, id, user=""):
    u = db.query(models.Usuario).filter_by(id=id).first()
    if u:
        _log(db, user, "eliminó un usuario", "Usuarios", u.username)
    db.query(models.Usuario).filter_by(id=id).delete()
    db.commit()

# ─── AFILIADOS ────────────────────────────────────────────────────────────────
def get_afiliados(db, q="", estado="", empresa="", cliente="", subtipo="",
                  skip: int = 0, limit: int = 0):
    """Lista afiliados con filtros opcionales y paginación (skip/limit).
    Si limit=0 devuelve todos (para compatibilidad con exportaciones Excel).
    """
    query = db.query(models.Afiliado).filter_by(activo=True)
    if q:
        query = query.filter(or_(
            models.Afiliado.nombre.ilike(f"%{q}%"),
            models.Afiliado.doc.ilike(f"%{q}%"),
            models.Afiliado.empresa.ilike(f"%{q}%"),
            models.Afiliado.cliente_txt.ilike(f"%{q}%"),
        ))
    if estado:  query = query.filter(or_(models.Afiliado.estado_srv==estado, models.Afiliado.estado==estado))
    if empresa: query = query.filter_by(empresa=empresa)
    if cliente: query = query.filter_by(cliente_txt=cliente)
    if subtipo: query = query.filter_by(subtipo=subtipo)
    total = query.count()
    query = query.order_by(models.Afiliado.nombre)
    if limit > 0:
        query = query.offset(skip).limit(limit)
    return {"total": total, "items": [_afiliado_to_dict(a) for a in query.all()]}

def get_afiliado(db, id): a = db.query(models.Afiliado).filter_by(id=id, activo=True).first(); return _afiliado_to_dict(a) if a else None
def get_afiliado_by_doc(db, doc): return db.query(models.Afiliado).filter_by(doc=doc, activo=True).first()

def create_afiliado(db, data: schemas.AfiliadoCreate):
    from sqlalchemy.exc import IntegrityError
    cache_invalidar("cobro:")
    a = models.Afiliado(**{
        "nombre":data.nombre,"tipo_doc":data.tipo_doc,"doc":data.doc,"empresa":data.empresa,
        "cargo":data.cargo,"cliente_txt":data.cliente_txt,
        "eps":data.eps,"arl":data.arl,"ccf":data.ccf,"afp":data.afp,
        "subtipo":data.subtipo,"estado":data.estado,"estado_srv":data.estado_srv,
        "servicios":json.dumps(data.servicios),"tel":data.tel,
        "email":data.email,"dir":data.dir,"obs":data.obs,"novedades":data.novedades,"detalle":data.detalle,
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
    cache_invalidar("cobro:")  # novedades u otros campos del afiliado afectan el cobro
    a = db.query(models.Afiliado).filter_by(id=id).first()
    for field, val in [
        ("nombre",data.nombre),("tipo_doc",data.tipo_doc),("doc",data.doc),("empresa",data.empresa),
        ("cargo",data.cargo),("cliente_txt",data.cliente_txt),
        ("eps",data.eps),("arl",data.arl),("ccf",data.ccf),("afp",data.afp),
        ("subtipo",data.subtipo),("estado",data.estado),("estado_srv",data.estado_srv),
        ("servicios",json.dumps(data.servicios)),("tel",data.tel),
        ("email",data.email),("dir",data.dir),("obs",data.obs),("novedades",data.novedades),("detalle",data.detalle),
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
    cache_invalidar("cobro:")  # eliminar afiliado afecta cobro
    a = db.query(models.Afiliado).filter_by(id=id).first()
    if not a: return
    # Guardar en eliminados
    elim = models.Eliminado(
        nombre=a.nombre, doc=a.doc, empresa=a.empresa,
        datos_completos=json.dumps(_afiliado_to_dict(a)),
        fecha_eliminacion=datetime.now().strftime("%Y-%m-%d"),
        mes=MESES[datetime.now().month-1], eliminado_por=deleted_by,
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

def get_facturas(db, anio="", mes="", cliente="", estado="", banco="",
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
    total = q.count()
    q = q.order_by(models.Factura.id.desc())
    if limit > 0:
        q = q.offset(skip).limit(limit)
    items = q.all()
    # Obtener teléfonos y fecha_afiliacion de afiliados en una sola consulta
    docs = list({f.doc for f in items if f.doc})
    tels = {}
    fechas_afiliacion = {}
    if docs:
        for a in db.query(
            models.Afiliado.doc,
            models.Afiliado.tel,
            models.Afiliado.fecha_afiliacion
        ).filter(models.Afiliado.doc.in_(docs)).all():
            tels[a.doc] = a.tel or ""
            fechas_afiliacion[a.doc] = a.fecha_afiliacion or ""
    result = []
    for f in items:
        d = _factura_to_dict(f)
        d["tel"] = tels.get(f.doc, "")
        d["fecha_afiliacion"] = fechas_afiliacion.get(f.doc, "")
        result.append(d)
    return {"total": total, "items": result}

def get_factura(db, id): f = db.query(models.Factura).filter_by(id=id).first(); return f
def get_facturas_pendientes_by_doc(db, doc, mes=None):
    q = db.query(models.Factura).filter_by(doc=doc, estado="pendiente")
    if mes: q = q.filter_by(mes=mes)
    return q.all()

def create_factura(db, data: schemas.FacturaCreate):
    from sqlalchemy.exc import IntegrityError
    # Validar que no exista ya una factura para este afiliado en el mismo mes/año
    anio_fact = data.anio or str(datetime.now().year)
    duplicada = db.query(models.Factura).filter_by(
        doc=data.doc, mes=data.mes, anio=anio_fact
    ).first()
    if duplicada:
        from fastapi import HTTPException
        raise HTTPException(400, f"Ya existe una factura del mes")

    cache_invalidar("cobro:")  # invalidar caché de cobro al crear factura
    codigo = data.codigo or _next_codigo(db)
    f = models.Factura(
        codigo=codigo, nombre_afiliado=data.nombre_afiliado, doc=data.doc,
        cliente=data.cliente, anio=data.anio or str(datetime.now().year),
        mes=data.mes, periodo=data.periodo, estado=data.estado, banco=data.banco,
        ingresos=data.ingresos, costos=data.costos, costo_adm=data.costo_adm,
        conceptos_extra=data.conceptos_extra, utilidad=data.utilidad,
        novedades=data.novedades,
        servicios_detalle=json.dumps(data.servicios_detalle),
        conceptos_detalle=json.dumps(data.conceptos_detalle),
        creado_por=data.creado_por,
    )
    db.add(f); _log(db, data.creado_por, "agregó una factura", "Facturación", codigo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(400, f"Ya existe una factura con código {codigo}")
    db.refresh(f); return _factura_to_dict(f)

def update_factura(db, id, data: schemas.FacturaUpdate, editor=""):
    cache_invalidar("cobro:")  # editar factura afecta cobro
    f = db.query(models.Factura).filter_by(id=id).first()
    for k, v in data.model_dump(exclude_none=True).items():
        if k in ("servicios_detalle","conceptos_detalle"): v = json.dumps(v)
        setattr(f, k, v)
    _log(db, editor, "editó una factura", "Facturación", f.codigo)
    db.commit(); db.refresh(f); return _factura_to_dict(f)

def pagar_factura(db, id, user=""):
    cache_invalidar("cobro:")  # invalidar caché al pagar
    f = db.query(models.Factura).filter_by(id=id).first()
    if f.estado == "pagado":
        return _factura_to_dict(f)  # idempotente: ya está pagado
    f.estado = "pagado"
    f.pagado_en = datetime.utcnow()
    _log(db, user, "marcó factura como pagada", "Facturación", f.codigo)
    db.commit(); db.refresh(f); return _factura_to_dict(f)

def delete_factura(db, id, user=""):
    f = db.query(models.Factura).filter_by(id=id).first()
    codigo = f.codigo if f else "?"
    db.query(models.Factura).filter_by(id=id).delete()
    _log(db, user, "eliminó una factura", "Facturación", codigo)
    db.commit()
    cache_invalidar("cobro:")  # invalidar caché al eliminar factura

# ─── RETIROS ──────────────────────────────────────────────────────────────────
def get_retiros(db, anio="", mes=""):
    q = db.query(models.Retiro)
    if anio: q = q.filter_by(anio=anio)
    if mes:  q = q.filter_by(mes=mes)
    rows = q.order_by(models.Retiro.id.desc()).all()
    return [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
             "fecha":r.fecha,"motivo":r.motivo,"obs":r.obs,"mes":r.mes,
             "anio":r.anio,"registrado_por":r.registrado_por} for r in rows]

def create_retiro(db, data: schemas.RetiroCreate):
    cache_invalidar("cobro:")  # retiro cambia estado_srv → afecta cobro
    afil = get_afiliado_by_doc(db, data.doc)
    if not afil: return None
    # Verificar si ya tiene un retiro registrado
    retiro_existente = db.query(models.Retiro).filter_by(doc=data.doc).first()
    if retiro_existente:
        from fastapi import HTTPException
        raise HTTPException(400,
            f"El afiliado ya tiene un retiro registrado del {retiro_existente.fecha}")
    afil.estado = "RETIRADO"; afil.estado_srv = "RETIRADO"
    anio_actual = str(datetime.now().year)
    mes_actual  = MESES[datetime.now().month-1]
    r = models.Retiro(
        nombre=afil.nombre, doc=data.doc, empresa=afil.empresa,
        fecha=data.fecha, motivo=data.motivo, obs=data.obs,
        mes=mes_actual, anio=anio_actual, registrado_por=data.registrado_por,
    )
    db.add(r); _log(db, data.registrado_por, "aplicó un retiro", "Retiros", afil.nombre)
    db.commit(); db.refresh(r)
    return {"id":r.id,"nombre":r.nombre,"doc":r.doc,"fecha":r.fecha,"motivo":r.motivo}

def delete_retiro(db, id, user=""):
    cache_invalidar("cobro:")  # reactivación afecta cobro
    r = db.query(models.Retiro).filter_by(id=id).first()
    if r:
        _log(db, user, "eliminó un retiro", "Retiros", r.nombre)
        # Reactivar afiliado solo si no tiene otros retiros registrados
        otros = db.query(models.Retiro).filter(
            models.Retiro.doc == r.doc, models.Retiro.id != id
        ).count()
        if otros == 0:
            afil = db.query(models.Afiliado).filter_by(doc=r.doc).first()
            if afil:
                afil.estado = "ACTIVO"
                afil.estado_srv = "ACTIVO"
                afil.activo = True  # asegurar que esté activo
                _log(db, user, "reactivó afiliado por eliminación de retiro", "Afiliados", afil.nombre)
    db.query(models.Retiro).filter_by(id=id).delete()
    db.commit()

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

def update_nomina(db, id, nomina):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if not e: return None
    e.nomina = nomina; db.commit()
    return {"id":e.id,"nomina":e.nomina}

def delete_empleado(db, id, user=""):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if e:
        _log(db, user, "eliminó un empleado", "Empleados", e.nombre)
        db.delete(e)
        db.commit()

# ─── GASTOS ───────────────────────────────────────────────────────────────────
def get_gastos(db):
    return [{"id":g.id,"nombre":g.nombre,"valor":g.valor,"activo":g.activo}
            for g in db.query(models.Gasto).all()]

def create_gasto(db, data: schemas.GastoCreate):
    g = models.Gasto(nombre=data.nombre, valor=data.valor)
    db.add(g); db.commit(); db.refresh(g)
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"activo":g.activo}

def toggle_gasto(db, id):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if not g: return None
    g.activo = not g.activo; db.commit()
    return {"id":g.id,"activo":g.activo}

def delete_gasto(db, id, user=""):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if g:
        _log(db, user, "eliminó un gasto fijo", "Gastos", g.nombre)
    db.query(models.Gasto).filter_by(id=id).delete()
    db.commit()

# ─── CONFIG ───────────────────────────────────────────────────────────────────
def get_config(db):
    c = db.query(models.Config).first()
    if not c: return {"ibc_global":1_950_905,"porcentajes":{},"plantilla_whatsapp":""}
    return {
        "ibc_global": c.ibc_global,
        "porcentajes": json.loads(c.porcentajes or "{}"),
        "plantilla_whatsapp": c.plantilla_whatsapp or ""
    }

def update_config(db, data: schemas.ConfigUpdate, user="sistema"):
    c = db.query(models.Config).first()
    if not c:
        c = models.Config()
        db.add(c)
    if data.ibc_global is not None: c.ibc_global = data.ibc_global
    if data.porcentajes is not None: c.porcentajes = json.dumps(data.porcentajes)
    if data.plantilla_whatsapp is not None: c.plantilla_whatsapp = data.plantilla_whatsapp
    _log(db, user, "actualizó configuración global", "Config", "")
    db.commit(); return get_config(db)

# ─── LISTAS ───────────────────────────────────────────────────────────────────
def get_listas(db):
    return {l.nombre: json.loads(l.items or "[]") for l in db.query(models.Lista).all()}

def update_lista(db, nombre, items, user="sistema"):
    l = db.query(models.Lista).filter_by(nombre=nombre).first()
    if not l: l = models.Lista(nombre=nombre); db.add(l)
    l.items = json.dumps(items)
    _log(db, user, "actualizó lista", "Listas", nombre)
    db.commit()
    return {"nombre":nombre,"items":items}

# ─── ACTIVIDAD ────────────────────────────────────────────────────────────────
def get_actividad(db, modulo="", usuario="", desde="", hasta=""):
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
            # incluir todo el día "hasta"
            hasta_fin = _dt.fromisoformat(hasta).replace(hour=23, minute=59, second=59)
            q = q.filter(models.Actividad.fecha <= hasta_fin)
        except ValueError:
            pass
    rows = q.order_by(models.Actividad.id.desc()).limit(1000).all()
    return [{"id":r.id,"usuario":r.usuario,"accion":r.accion,"modulo":r.modulo,
             "detalle":r.detalle,"fecha":r.fecha.strftime("%d/%m/%Y %H:%M:%S") if r.fecha else ""}
            for r in rows]

def clear_actividad(db, user=""):
    db.query(models.Actividad).delete()
    db.add(models.Actividad(usuario=user, accion="limpió el historial de actividad",
                            modulo="Sistema", detalle="Historial borrado"))
    db.commit()

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
def get_dashboard(db, anio="", mes=""):
    from sqlalchemy import func, case
    # Contar afiliados por estado con una sola query SQL
    stats = db.query(
        func.count(models.Afiliado.id).label("total"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%ACTIVO%"), 1), else_=0)).label("activos"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%RETIR%"),  1), else_=0)).label("retirados"),
        func.sum(case((models.Afiliado.estado_srv.ilike("%SUSPENDIDO%"), 1), else_=0)).label("suspendidos"),
    ).filter(models.Afiliado.activo==True).one()

    fq = db.query(
        func.count(models.Factura.id).label("n"),
        func.coalesce(func.sum(models.Factura.ingresos), 0).label("ingresos"),
        func.coalesce(func.sum(models.Factura.utilidad), 0).label("utilidad"),
        func.coalesce(func.sum(case((models.Factura.estado=="pendiente", models.Factura.ingresos), else_=0)), 0).label("pendiente"),
        func.sum(case((models.Factura.estado=="pendiente", 1), else_=0)).label("n_pend"),
    )
    if anio: fq = fq.filter(models.Factura.anio==anio)
    if mes:  fq = fq.filter(models.Factura.mes==mes)
    facts = fq.one()

    nominas = db.query(func.coalesce(func.sum(models.Empleado.nomina), 0)).filter_by(activo=True).scalar()
    gastos  = db.query(func.coalesce(func.sum(models.Gasto.valor),    0)).filter_by(activo=True).scalar()

    # Nóminas y gastos son valores mensuales fijos.
    # Se multiplican según el período filtrado para comparar correctamente contra los ingresos.
    if anio and not mes:
        meses_factor = 12          # año completo → 12 meses de costos fijos
    elif mes:
        meses_factor = 1           # mes específico → 1 mes de costos fijos
    else:
        meses_factor = 1           # sin filtro → referencia mensual

    util_neta = float(facts.utilidad) - (float(nominas) + float(gastos)) * meses_factor

    return {
        "activos": int(stats.activos or 0), "retirados": int(stats.retirados or 0),
        "suspendidos": int(stats.suspendidos or 0), "total_afiliados": int(stats.total or 0),
        "facturas": int(facts.n or 0), "ingresos": float(facts.ingresos),
        "utilidad_bruta": float(facts.utilidad), "nominas": float(nominas),
        "gastos_fijos": float(gastos), "utilidad_neta": util_neta,
        "pendiente_cobro": float(facts.pendiente), "facturas_pendientes": int(facts.n_pend or 0),
        "meses_factor": meses_factor,
    }

# ─── DASHBOARD MESES ──────────────────────────────────────────────────────────
def get_dashboard_meses(db):
    """Retorna lista de {mes, anio, ingresos, facturas} de los últimos 6 meses."""
    from datetime import datetime
    result = []
    now = datetime.now()
    for i in range(5, -1, -1):
        month = (now.month - 1 - i) % 12 + 1
        year  = now.year + ((now.month - 1 - i) // 12)
        mes_nombre = MESES[month - 1]
        rows = db.query(models.Factura).filter_by(mes=mes_nombre, anio=str(year)).all()
        ingresos = sum(f.ingresos or 0 for f in rows)
        result.append({
            "mes": mes_nombre[:3],
            "anio": year,
            "ingresos": ingresos,
            "facturas": len(rows),
        })
    return result

# ─── CACHÉ EN MEMORIA ────────────────────────────────────────────────────────
import time as _time
_cache: dict = {}
CACHE_TTL = 120  # segundos que vive el caché (2 minutos)

def _cache_get(key: str):
    """Obtiene un valor del caché si no ha expirado."""
    entry = _cache.get(key)
    if entry and (_time.time() - entry["ts"]) < CACHE_TTL:
        return entry["data"]
    return None

def _cache_set(key: str, data):
    """Guarda un valor en el caché con timestamp actual. Evicta expiradas si crece."""
    _cache[key] = {"data": data, "ts": _time.time()}
    if len(_cache) > 500:
        now = _time.time()
        expired = [k for k, v in list(_cache.items()) if (now - v["ts"]) >= CACHE_TTL]
        for k in expired:
            _cache.pop(k, None)

def cache_invalidar(prefijo: str = ""):
    """Invalida entradas del caché que empiecen con el prefijo dado."""
    keys = [k for k in _cache if k.startswith(prefijo)]
    for k in keys:
        del _cache[k]

# ─── MÓDULO DE COBRO ──────────────────────────────────────────────────────────
def get_cobro(db, empresa="", cliente="", tipo="", mes="", anio="", doc=""):
    """Calcula el estado de cobro por afiliado y mes (últimos 6 meses).
    Genera una fila por cada mes pendiente de cada afiliado.
    El caché se invalida automáticamente al crear/editar/eliminar facturas o afiliados.
    """
    cache_key = f"cobro:{empresa}:{cliente}:{tipo}:{mes}:{anio}:{doc}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    hoy = datetime.now()
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
    ibc_global = cfg.ibc_global if cfg else 1_950_905
    pcts = json.loads(cfg.porcentajes or "{}") if cfg else {}

    # Pre-cargar TODAS las facturas de los últimos 6 meses → set de (doc, mes, anio)
    anios_ventana = list({str(y) for y, _ in meses_ventana})
    meses_ventana_nombres = list({MESES[m-1] for _, m in meses_ventana})
    facturas_set = set(
        (f.doc, f.mes, f.anio)
        for f in db.query(models.Factura.doc, models.Factura.mes, models.Factura.anio)
        .filter(models.Factura.anio.in_(anios_ventana))
        .filter(models.Factura.mes.in_(meses_ventana_nombres))
        .all()
    )

    afils = db.query(models.Afiliado).filter(
        models.Afiliado.activo == True,
        ~models.Afiliado.estado_srv.ilike("%RETIR%"),
        ~models.Afiliado.estado_srv.ilike("%SUSPENDIDO%"),
    ).all()

    rows = []
    for a in afils:
        if (a.cliente_txt or "").upper() == "EMPLEADO": continue
        fa = a.fecha_afiliacion or a.fecha_ingreso or ""
        if not fa or "-" not in fa: continue
        try:
            partes = fa.split("-")
            dia_afil  = int(partes[2])
            afil_year = int(partes[0])
            afil_month= int(partes[1])
        except: continue

        ibc = a.ibc if (a.ibc and a.ibc > 0) else ibc_global
        srvs = _servicios_afiliado(a)
        planilla = sum(_ceil100(ibc * pcts.get(s, pcts.get(s.upper(), 0.0))) for s in srvs)
        cliente_afil = a.cliente_txt or ""

        for (y, m) in meses_ventana:
            # No mostrar meses anteriores a la fecha de afiliación
            if (y, m) < (afil_year, afil_month): continue

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
                if dia_afil < dia_hoy:   estado = "VENCIDO"
                elif dia_afil == dia_hoy: estado = "HOY"
                else:                     estado = "PROXIMO"

            rows.append({
                "id":       f"{a.id}_{m}_{y}",
                "afil_id":  a.id,
                "nombre":   a.nombre,
                "empresa":  a.empresa,
                "doc":      a.doc,
                "dia_cobro":dia_afil,
                "mes":      mes_nombre,
                "anio":     anio_str,
                "fecha_afiliacion": fa,
                "cliente":  cliente_afil,
                "servicios":srvs,
                "planilla": planilla,
                "estado":   estado,
                "novedades":a.novedades or "",
                "subtipo":  a.subtipo or "",
            })

    if doc:     rows = [r for r in rows if r["doc"] == doc]
    if empresa: rows = [r for r in rows if r["empresa"] == empresa]
    if cliente: rows = [r for r in rows if r["cliente"] == cliente]
    if mes:     rows = [r for r in rows if r["mes"] == mes]
    if anio:    rows = [r for r in rows if r["anio"] == anio]
    if tipo == "HOY":     rows = [r for r in rows if r["estado"] == "HOY"]
    elif tipo == "VENCIDO": rows = [r for r in rows if r["estado"] == "VENCIDO"]
    elif tipo == "PROXIMO": rows = [r for r in rows if r["estado"] == "PROXIMO"]
    elif tipo == "COBRADO": rows = [r for r in rows if r["estado"] == "COBRADO"]

    orden = {"VENCIDO": 0, "HOY": 1, "PROXIMO": 2, "COBRADO": 3}
    rows.sort(key=lambda r: (orden.get(r["estado"], 4), r["nombre"], r["anio"], r["mes"]))
    _cache_set(cache_key, rows)
    return rows

# ─── TAREAS ───────────────────────────────────────────────────────────────────
_ESTADO_LABEL = {
    "pendiente":   "Pendiente",
    "en_proceso":  "En proceso",
    "completada":  "Completada",
    "finalizada":  "Finalizada",
}

def _tarea_to_dict(db, t):
    comentarios = db.query(models.TareaComentario).filter_by(tarea_id=t.id)\
                    .order_by(models.TareaComentario.creado).all()
    return {
        "id": t.id, "titulo": t.titulo, "descripcion": t.descripcion,
        "asignado_a": t.asignado_a, "creado_por": t.creado_por,
        "estado": t.estado,
        "fecha_limite": t.fecha_limite or "",
        "creado": t.creado.isoformat(),
        "completado_en": t.completado_en.isoformat() if t.completado_en else None,
        "finalizado_en": t.finalizado_en.isoformat() if t.finalizado_en else None,
        "finalizado_por": t.finalizado_por or "",
        "comentarios": [{"id": c.id, "usuario": c.usuario, "texto": c.texto,
                         "creado": c.creado.isoformat()} for c in comentarios]
    }

def create_tarea(db, data: schemas.TareaCreate):
    t = models.Tarea(**data.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    db.add(models.Notificacion(
        usuario=data.asignado_a,
        mensaje=f"Nueva tarea asignada: {data.titulo}",
        tarea_id=t.id
    ))
    db.commit()
    return _tarea_to_dict(db, t)

def get_tareas(db, username: str, rol: str):
    q = db.query(models.Tarea)
    if rol != "admin":
        q = q.filter_by(asignado_a=username)
    return [_tarea_to_dict(db, t) for t in q.order_by(models.Tarea.creado.desc()).all()]

def cambiar_estado_tarea(db, tarea_id: int, nuevo_estado: str, usuario: str, nota: str = ""):
    """Empleado cambia estado (pendiente→en_proceso→completada). Notifica al admin."""
    estados_validos = ["pendiente", "en_proceso", "completada"]
    if nuevo_estado not in estados_validos:
        return None
    t = db.query(models.Tarea).filter_by(id=tarea_id).first()
    if not t: return None
    estado_anterior = t.estado
    t.estado = nuevo_estado
    if nuevo_estado == "completada":
        t.completado_en = datetime.utcnow()
    if nota:
        db.add(models.TareaComentario(tarea_id=tarea_id, usuario=usuario, texto=nota))
    label_nuevo = _ESTADO_LABEL.get(nuevo_estado, nuevo_estado)
    db.add(models.Notificacion(
        usuario=t.creado_por,
        mensaje=f"{usuario} cambió la tarea '{t.titulo}' a: {label_nuevo}",
        tarea_id=tarea_id
    ))
    db.commit()
    return _tarea_to_dict(db, t)

def finalizar_tarea(db, tarea_id: int, admin_username: str):
    """Admin finaliza una tarea completada. Queda en historial como finalizada."""
    t = db.query(models.Tarea).filter_by(id=tarea_id).first()
    if not t: return None
    t.estado = "finalizada"
    t.finalizado_en = datetime.utcnow()
    t.finalizado_por = admin_username
    db.add(models.Notificacion(
        usuario=t.asignado_a,
        mensaje=f"Tu tarea '{t.titulo}' fue finalizada por {admin_username}",
        tarea_id=tarea_id
    ))
    db.commit()
    return _tarea_to_dict(db, t)

def add_comentario(db, tarea_id: int, data: schemas.TareaComentarioCreate):
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
