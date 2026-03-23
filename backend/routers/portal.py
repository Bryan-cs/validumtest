"""Router del Portal de Cliente."""
import json
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from .deps import verify_token

router = APIRouter(prefix="/portal", tags=["portal"])


def _require_portal(token=Depends(verify_token)):
    if token.get("rol") not in ("admin", "cliente"):
        raise HTTPException(status_code=403, detail="Acceso solo para clientes o administradores")
    return token


# ─── AFILIADOS ────────────────────────────────────────────────────────────────

@router.get("/afiliados")
def portal_afiliados(q: str = "", db: Session = Depends(get_db), token=Depends(_require_portal)):
    rol = token.get("rol", "")
    cliente_ref = (token.get("cliente_ref") or "").strip()

    # Cliente sin cliente_ref configurado → no mostrar nada
    if rol != "admin" and not cliente_ref:
        raise HTTPException(400, "Este usuario no tiene un cliente asociado. Contacte al administrador.")

    query = db.query(models.Afiliado).filter(models.Afiliado.activo == True)
    if rol != "admin":
        # Filtro estricto: solo afiliados cuyo cliente_txt coincide exactamente
        query = query.filter(
            models.Afiliado.cliente_txt == cliente_ref,
            models.Afiliado.cliente_txt != None,
            models.Afiliado.cliente_txt != "",
        )
    if q:
        from sqlalchemy import or_
        query = query.filter(
            or_(models.Afiliado.nombre.ilike(f"%{q}%"), models.Afiliado.doc.ilike(f"%{q}%"))
        )
    afiliados = query.order_by(models.Afiliado.nombre).all()

    result = []
    for a in afiliados:
        try:
            srvs = json.loads(a.servicios or "[]")
        except Exception:
            srvs = []
        result.append({
            "id": a.id, "nombre": a.nombre, "doc": a.doc, "tipo_doc": a.tipo_doc,
            "empresa": a.empresa, "cargo": a.cargo,
            "eps": a.eps, "afp": a.afp, "ccf": a.ccf, "arl": a.arl,
            "estado": a.estado, "estado_srv": a.estado_srv,
            "servicios": srvs, "tel": a.tel, "email": a.email,
            "fecha_ingreso": a.fecha_ingreso, "fecha_afiliacion": a.fecha_afiliacion,
            "novedades": a.novedades or "",
        })
    return result


@router.get("/afiliados/{doc}/resumen")
def portal_resumen(doc: str, db: Session = Depends(get_db), token=Depends(_require_portal)):
    rol = token.get("rol", "")
    cliente_ref = (token.get("cliente_ref") or "").strip()
    afil = db.query(models.Afiliado).filter_by(doc=doc, activo=True).first()
    if not afil:
        raise HTTPException(404, "Afiliado no encontrado")
    if rol != "admin" and afil.cliente_txt != cliente_ref:
        raise HTTPException(403, "Sin acceso a este afiliado")

    facturas = (db.query(models.Factura)
                .filter_by(doc=doc, afiliado_eliminado=False)
                .order_by(models.Factura.anio.desc(), models.Factura.id.desc())
                .all())

    try:
        srvs = json.loads(afil.servicios or "[]")
    except Exception:
        srvs = []

    return {
        "afiliado": {
            "id": afil.id, "nombre": afil.nombre, "doc": afil.doc, "tipo_doc": afil.tipo_doc,
            "empresa": afil.empresa, "cargo": afil.cargo,
            "eps": afil.eps, "afp": afil.afp, "ccf": afil.ccf, "arl": afil.arl,
            "estado": afil.estado, "estado_srv": afil.estado_srv,
            "servicios": srvs, "tel": afil.tel, "email": afil.email,
            "dir": afil.dir, "obs": afil.obs, "ibc": afil.ibc,
            "fecha_ingreso": afil.fecha_ingreso, "fecha_afiliacion": afil.fecha_afiliacion,
        },
        "facturas": [{
            "id": f.id, "codigo": f.codigo, "mes": f.mes, "anio": f.anio,
            "estado": f.estado, "costos": f.costos, "banco": f.banco,
            "pagado_en": f.pagado_en.isoformat() if f.pagado_en else None,
        } for f in facturas],
        "total_pendiente": sum(f.costos or 0 for f in facturas if f.estado == "pendiente"),
        "total_pagado":    sum(f.costos or 0 for f in facturas if f.estado == "pagado"),
    }


# ─── NOVEDADES DE PAGO ────────────────────────────────────────────────────────

@router.post("/novedades-pago", status_code=201)
def portal_novedad_pago(
    data: schemas.NovedadPagoCreate,
    db: Session = Depends(get_db),
    token=Depends(_require_portal),
):
    rol             = token.get("rol", "")
    cliente_ref     = (token.get("cliente_ref") or "").strip()
    username        = token.get("sub", "")
    nombre_cliente  = token.get("nombre", username)

    if not data.afiliados_docs:
        raise HTTPException(400, "Debe seleccionar al menos un afiliado")

    afiliados = []
    for doc in data.afiliados_docs:
        afil = db.query(models.Afiliado).filter_by(doc=doc, activo=True).first()
        if not afil:
            raise HTTPException(404, f"Afiliado con documento {doc} no encontrado")
        if rol != "admin" and afil.cliente_txt != cliente_ref:
            raise HTTPException(403, f"Sin acceso al afiliado con documento {doc}")
        afiliados.append(afil)

    novedad = models.NovedadPago(
        cliente_ref=cliente_ref,
        username_cliente=username,
        mes=data.mes,
        anio=data.anio,
        afiliados_docs=json.dumps(data.afiliados_docs),
        afiliados_nombres=json.dumps([a.nombre for a in afiliados]),
        obs=data.obs,
        estado="pendiente",
    )
    db.add(novedad)

    admins = db.query(models.Usuario).filter_by(rol="admin", activo=True).all()
    for admin in admins:
        db.add(models.Notificacion(
            usuario=admin.username,
            mensaje=f"Cliente '{nombre_cliente}' reportó novedad SS para {len(afiliados)} afiliado(s) — {data.mes} {data.anio}",
        ))

    db.commit()
    db.refresh(novedad)
    return {"ok": True, "id": novedad.id}


@router.get("/novedades-pago")
def portal_list_novedades(db: Session = Depends(get_db), token=Depends(_require_portal)):
    query = db.query(models.NovedadPago)
    if token.get("rol") != "admin":
        query = query.filter_by(username_cliente=token.get("sub"))
    rows = query.order_by(models.NovedadPago.id.desc()).all()
    return [{
        "id": r.id, "cliente_ref": r.cliente_ref, "username_cliente": r.username_cliente,
        "mes": r.mes, "anio": r.anio,
        "afiliados": json.loads(r.afiliados_nombres or "[]"),
        "obs": r.obs, "estado": r.estado, "respuesta": r.respuesta or "",
        "creado": r.creado.isoformat() if r.creado else None,
    } for r in rows]


@router.patch("/novedades-pago/{id}/estado")
def portal_update_novedad_estado(
    id: int, body: dict,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    from .deps import require_admin as _ra
    if token.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores pueden actualizar el estado")
    nov = db.query(models.NovedadPago).filter_by(id=id).first()
    if not nov:
        raise HTTPException(404, "Novedad no encontrada")
    nuevo_estado = body.get("estado", nov.estado)
    nov.estado = nuevo_estado
    if body.get("respuesta") is not None:
        nov.respuesta = body["respuesta"]
    if nov.username_cliente:
        msg = f"Tu novedad de pago ({nov.mes} {nov.anio}) fue marcada como '{nuevo_estado}'"
        if nov.respuesta:
            msg += f". Nota del administrador: {nov.respuesta}"
        db.add(models.Notificacion(usuario=nov.username_cliente, mensaje=msg))
    db.commit()
    return {"ok": True}


# ─── SOLICITUDES DE RETIRO ────────────────────────────────────────────────────

@router.post("/solicitar-retiro", status_code=201)
def portal_solicitar_retiro(
    data: schemas.SolicitudRetiroCreate,
    db: Session = Depends(get_db),
    token=Depends(_require_portal),
):
    rol            = token.get("rol", "")
    cliente_ref    = (token.get("cliente_ref") or "").strip()
    username       = token.get("sub", "")
    nombre_cliente = token.get("nombre", username)

    afil = db.query(models.Afiliado).filter_by(doc=data.afiliado_doc, activo=True).first()
    if not afil:
        raise HTTPException(404, "Afiliado no encontrado")
    if rol != "admin" and afil.cliente_txt != cliente_ref:
        raise HTTPException(403, "Sin acceso a este afiliado")

    solicitud = models.SolicitudRetiro(
        cliente_ref=cliente_ref,
        username_cliente=username,
        afiliado_doc=data.afiliado_doc,
        afiliado_nombre=afil.nombre,
        motivo=data.motivo,
        obs=data.obs,
        estado="pendiente",
    )
    db.add(solicitud)

    admins = db.query(models.Usuario).filter_by(rol="admin", activo=True).all()
    for admin in admins:
        db.add(models.Notificacion(
            usuario=admin.username,
            mensaje=f"Cliente '{nombre_cliente}' solicita retiro de '{afil.nombre}' — {data.motivo}",
        ))

    db.commit()
    db.refresh(solicitud)
    return {"ok": True, "id": solicitud.id}


@router.get("/solicitudes-retiro")
def portal_list_solicitudes(db: Session = Depends(get_db), token=Depends(_require_portal)):
    query = db.query(models.SolicitudRetiro)
    if token.get("rol") != "admin":
        query = query.filter_by(username_cliente=token.get("sub"))
    rows = query.order_by(models.SolicitudRetiro.id.desc()).all()
    return [{
        "id": r.id, "cliente_ref": r.cliente_ref,
        "afiliado_doc": r.afiliado_doc, "afiliado_nombre": r.afiliado_nombre,
        "motivo": r.motivo, "obs": r.obs, "estado": r.estado, "respuesta": r.respuesta or "",
        "creado": r.creado.isoformat() if r.creado else None,
    } for r in rows]


@router.patch("/solicitudes-retiro/{id}/estado")
def portal_update_solicitud_estado(
    id: int, body: dict,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    if token.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores pueden actualizar el estado")
    sol = db.query(models.SolicitudRetiro).filter_by(id=id).first()
    if not sol:
        raise HTTPException(404, "Solicitud no encontrada")
    nuevo_estado = body.get("estado", sol.estado)
    sol.estado = nuevo_estado
    if body.get("respuesta") is not None:
        sol.respuesta = body["respuesta"]
    if sol.username_cliente:
        msg = f"Tu solicitud de retiro de '{sol.afiliado_nombre}' fue marcada como '{nuevo_estado}'"
        if sol.respuesta:
            msg += f". Nota del administrador: {sol.respuesta}"
        db.add(models.Notificacion(usuario=sol.username_cliente, mensaje=msg))
    db.commit()
    return {"ok": True}


# ─── SOLICITUDES DE NOVEDAD ───────────────────────────────────────────────────

@router.post("/solicitudes-novedad", status_code=201)
def portal_crear_novedad(
    data: schemas.SolicitudNovedadCreate,
    db: Session = Depends(get_db),
    token=Depends(_require_portal),
):
    rol            = token.get("rol", "")
    cliente_ref    = (token.get("cliente_ref") or "").strip()
    username       = token.get("sub", "")
    nombre_cliente = token.get("nombre", username)

    afil = db.query(models.Afiliado).filter_by(doc=data.afiliado_doc, activo=True).first()
    if not afil:
        raise HTTPException(404, "Afiliado no encontrado")
    if rol != "admin" and afil.cliente_txt != cliente_ref:
        raise HTTPException(403, "Sin acceso a este afiliado")

    solicitud = models.SolicitudNovedad(
        cliente_ref=cliente_ref,
        username_cliente=username,
        afiliado_doc=data.afiliado_doc,
        afiliado_nombre=afil.nombre,
        tipo=data.tipo,
        descripcion=data.descripcion,
        estado="pendiente",
    )
    db.add(solicitud)

    admins = db.query(models.Usuario).filter_by(rol="admin", activo=True).all()
    for admin in admins:
        db.add(models.Notificacion(
            usuario=admin.username,
            mensaje=f"Cliente '{nombre_cliente}' reportó novedad '{data.tipo}' para '{afil.nombre}'",
        ))

    db.commit()
    db.refresh(solicitud)
    return {"ok": True, "id": solicitud.id}


@router.get("/solicitudes-novedad")
def portal_list_novedades_afil(db: Session = Depends(get_db), token=Depends(_require_portal)):
    query = db.query(models.SolicitudNovedad)
    if token.get("rol") != "admin":
        query = query.filter_by(username_cliente=token.get("sub"))
    rows = query.order_by(models.SolicitudNovedad.id.desc()).all()
    return [{
        "id": r.id, "cliente_ref": r.cliente_ref,
        "afiliado_doc": r.afiliado_doc, "afiliado_nombre": r.afiliado_nombre,
        "tipo": r.tipo, "descripcion": r.descripcion,
        "estado": r.estado, "respuesta": r.respuesta or "",
        "creado": r.creado.isoformat() if r.creado else None,
    } for r in rows]


@router.patch("/solicitudes-novedad/{id}/estado")
def portal_update_novedad_afil_estado(
    id: int, body: dict,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    if token.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores pueden actualizar el estado")
    s = db.query(models.SolicitudNovedad).filter_by(id=id).first()
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    nuevo_estado = body.get("estado", s.estado)
    s.estado = nuevo_estado
    if body.get("respuesta") is not None:
        s.respuesta = body["respuesta"]
    if s.username_cliente:
        msg = f"Tu novedad '{s.tipo}' para '{s.afiliado_nombre}' fue marcada como '{nuevo_estado}'"
        if s.respuesta:
            msg += f". Nota del administrador: {s.respuesta}"
        db.add(models.Notificacion(usuario=s.username_cliente, mensaje=msg))
    db.commit()
    return {"ok": True}
