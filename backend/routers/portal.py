"""Router del Portal de Cliente."""
import io
import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
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
            "detalle": a.detalle or "",
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


@router.get("/novedades-pago/{id}/exportar-excel")
def exportar_novedad_pago_excel(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Admin descarga Excel con la info completa de los afiliados reportados en una novedad de pago."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    if token.get("rol") != "admin":
        raise HTTPException(403, "Solo administradores pueden exportar")

    nov = db.query(models.NovedadPago).filter_by(id=id).first()
    if not nov:
        raise HTTPException(404, "Novedad no encontrada")

    docs = json.loads(nov.afiliados_docs or "[]")
    afiliados = db.query(models.Afiliado).filter(models.Afiliado.doc.in_(docs)).all()
    # Ordenar según el orden original reportado por el cliente
    orden = {doc: i for i, doc in enumerate(docs)}
    afiliados.sort(key=lambda a: orden.get(a.doc, 999))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Novedad {nov.mes} {nov.anio}"

    header_fill = PatternFill("solid", fgColor="0D3B6E")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    headers = ["Nombre", "Tipo Doc", "Documento", "Empresa", "Cargo",
               "Estado", "EPS", "AFP", "CCF", "ARL",
               "Teléfono", "Email", "IBC"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row, a in enumerate(afiliados, 2):
        ws.cell(row=row, column=1,  value=a.nombre)
        ws.cell(row=row, column=2,  value=a.tipo_doc)
        ws.cell(row=row, column=3,  value=a.doc)
        ws.cell(row=row, column=4,  value=a.empresa)
        ws.cell(row=row, column=5,  value=a.cargo)
        ws.cell(row=row, column=6,  value=a.estado)
        ws.cell(row=row, column=7,  value=a.eps)
        ws.cell(row=row, column=8,  value=a.afp)
        ws.cell(row=row, column=9,  value=a.ccf)
        ws.cell(row=row, column=10, value=a.arl)
        ws.cell(row=row, column=11, value=a.tel)
        ws.cell(row=row, column=12, value=a.email)
        ws.cell(row=row, column=13, value=a.ibc)

    # Fila de resumen al final
    if afiliados:
        ws.append([])
        ws.append([f"Novedad de Pago — {nov.mes} {nov.anio}",
                   f"Cliente: {nov.cliente_ref or nov.username_cliente}",
                   f"Total afiliados: {len(afiliados)}",
                   f"Obs: {nov.obs or '—'}"])

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    nombre_archivo = f"novedad-pago-{nov.mes}-{nov.anio}-{id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


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


# ─── EXPORTAR EXCEL ───────────────────────────────────────────────────────────

@router.get("/exportar-excel")
def portal_exportar_excel(db: Session = Depends(get_db), token=Depends(_require_portal)):
    """Exporta los afiliados del cliente como archivo Excel."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    rol = token.get("rol", "")
    cliente_ref = (token.get("cliente_ref") or "").strip()

    if rol != "admin" and not cliente_ref:
        raise HTTPException(400, "Este usuario no tiene un cliente asociado.")

    query = db.query(models.Afiliado).filter(models.Afiliado.activo == True)
    if rol != "admin":
        query = query.filter(
            models.Afiliado.cliente_txt == cliente_ref,
            models.Afiliado.cliente_txt != None,
            models.Afiliado.cliente_txt != "",
        )
    afiliados = query.order_by(models.Afiliado.nombre).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mis Afiliados"

    headers = ["Nombre", "Tipo Doc", "Documento", "Empresa", "Cargo",
               "Estado", "Estado Servicio", "EPS", "AFP", "CCF", "ARL",
               "Teléfono", "Email", "Fecha Ingreso", "Fecha Afiliación"]

    header_fill = PatternFill("solid", fgColor="0D3B6E")
    header_font = Font(bold=True, color="FFFFFF", size=11)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row, a in enumerate(afiliados, 2):
        ws.cell(row=row, column=1,  value=a.nombre)
        ws.cell(row=row, column=2,  value=a.tipo_doc)
        ws.cell(row=row, column=3,  value=a.doc)
        ws.cell(row=row, column=4,  value=a.empresa)
        ws.cell(row=row, column=5,  value=a.cargo)
        ws.cell(row=row, column=6,  value=a.estado)
        ws.cell(row=row, column=7,  value=a.estado_srv)
        ws.cell(row=row, column=8,  value=a.eps)
        ws.cell(row=row, column=9,  value=a.afp)
        ws.cell(row=row, column=10, value=a.ccf)
        ws.cell(row=row, column=11, value=a.arl)
        ws.cell(row=row, column=12, value=a.tel)
        ws.cell(row=row, column=13, value=a.email)
        ws.cell(row=row, column=14, value=a.fecha_ingreso)
        ws.cell(row=row, column=15, value=a.fecha_afiliacion)

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="mis-afiliados.xlsx"'},
    )


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


# ─── ESTADO DE CUENTA PDF (accesible para clientes) ─────────────────────────

@router.get("/afiliados/{doc}/estado-cuenta")
def portal_estado_cuenta(doc: str, db: Session = Depends(get_db), token=Depends(_require_portal)):
    """Genera PDF de estado de cuenta accesible para clientes."""
    from routers.afiliados import estado_cuenta_afiliado as _gen_pdf

    rol = token.get("rol", "")
    cliente_ref = (token.get("cliente_ref") or "").strip()

    afil = db.query(models.Afiliado).filter_by(doc=doc, activo=True).first()
    if not afil:
        raise HTTPException(404, "Afiliado no encontrado")
    if rol != "admin" and afil.cliente_txt != cliente_ref:
        raise HTTPException(403, "Sin acceso a este afiliado")

    return _gen_pdf(afil.id, db, token)
