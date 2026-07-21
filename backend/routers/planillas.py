"""Router de Planillas de Pago SS."""
import os
import re
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import require_admin, require_admin_or_empleado
import models, crud
from utils.planillas_query import list_planillas_with_docs

router = APIRouter(prefix="/planillas", tags=["planillas"])


@router.get("")
def listar_planillas(cliente: str = "", mes: str = "", anio: str = "",
                     skip: int = 0, limit: int = 300,
                     db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    q = db.query(models.PlanillaPago).order_by(models.PlanillaPago.id.desc())
    if cliente: q = q.filter(models.PlanillaPago.cliente_ref == cliente)
    if mes:     q = q.filter(models.PlanillaPago.mes == mes)
    if anio:    q = q.filter(models.PlanillaPago.anio == anio)
    total = q.count()
    rows = q.offset(skip).limit(limit).all()
    return {"total": total, "items": list_planillas_with_docs(db, rows)}


@router.post("")
async def crear_planilla(
    cliente_ref: str = Form(...),
    mes: str = Form(...),
    anio: str = Form(...),
    observaciones: str = Form(""),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    token=Depends(require_admin_or_empleado),
):
    import asyncio
    from routers.documentos import _get_s3, _R2_BUCKET, ALLOWED_EXT, MAX_SIZE, _validar_magic
    s3 = _get_s3()
    safe_cliente = re.sub(r'[^\w\-]', '_', cliente_ref or 'sin_cliente')
    safe_mes     = re.sub(r'[^\w\-]', '_', mes or 'sin_mes')
    safe_anio    = re.sub(r'[^\w\-]', '_', anio or 'sin_anio')

    # ── 1. Leer y validar todos los archivos primero ──────────────────────────
    validos  = []  # lista de dicts listos para subir
    omitidos = []

    for file in files:
        nombre = file.filename or "archivo"
        ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        if ext not in ALLOWED_EXT:
            omitidos.append({"nombre": nombre, "motivo": f"Formato .{ext} no permitido"})
            continue
        content = await file.read()
        if len(content) > MAX_SIZE:
            omitidos.append({"nombre": nombre, "motivo": f"Excede {MAX_SIZE // (1024*1024)} MB"})
            continue
        # SEC2-M2: validar magic bytes del contenido
        if not _validar_magic(ext, content):
            omitidos.append({"nombre": nombre, "motivo": f"El contenido no corresponde a un {ext.upper()} válido"})
            continue
        safe_name   = re.sub(r'[^\w.\-]', '_', nombre)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        if s3:
            # Estructura: planillas/{cliente}/{anio}/{mes}/{archivo}
            ruta = f"planillas/{safe_cliente}/{safe_anio}/{safe_mes}/{unique_name}"
        else:
            ruta = f"uploads/planillas/{safe_cliente}/{safe_anio}/{safe_mes}/{unique_name}"
        validos.append({
            "nombre": nombre, "ext": ext, "ruta": ruta,
            "tamano": len(content), "content": content,
            "content_type": file.content_type or "application/octet-stream",
        })

    if not validos:
        raise HTTPException(400, f"Ningún archivo fue aceptado. Omitidos: {[o['motivo'] for o in omitidos]}")

    # ── 2. Subir todos a R2 en paralelo ───────────────────────────────────────
    async def _subir(d):
        try:
            if s3:
                await asyncio.to_thread(
                    s3.put_object,
                    Bucket=_R2_BUCKET, Key=d["ruta"],
                    Body=d["content"], ContentType=d["content_type"],
                )
            else:
                dir_path = os.path.dirname(d["ruta"])
                await asyncio.to_thread(os.makedirs, dir_path, exist_ok=True)
                def _write():
                    with open(d["ruta"], "wb") as fh:
                        fh.write(d["content"])
                await asyncio.to_thread(_write)
            return d, None
        except Exception as e:
            return d, str(e)

    resultados = await asyncio.gather(*[_subir(d) for d in validos])

    subidos       = []
    docs_pendientes = []
    for d, err in resultados:
        if err:
            omitidos.append({"nombre": d["nombre"], "motivo": f"Error al guardar: {err}"})
        else:
            subidos.append(d["nombre"])
            docs_pendientes.append(d)

    if not subidos:
        raise HTTPException(500, f"Todos los archivos fallaron al subirse: {[o['motivo'] for o in omitidos]}")

    # ── 3. Guardar en DB solo si hay archivos subidos ─────────────────────────
    # Si ya existe una planilla para este cliente+mes+año, se agregan los
    # archivos a esa (evita cards duplicadas del mismo periodo).
    planilla = (db.query(models.PlanillaPago)
                .filter_by(cliente_ref=cliente_ref, mes=mes, anio=anio)
                .order_by(models.PlanillaPago.id.asc())
                .first())
    reutilizada = planilla is not None
    if not planilla:
        planilla = models.PlanillaPago(
            cliente_ref=cliente_ref, mes=mes, anio=anio,
            observaciones=observaciones, subido_por=token.get("sub", ""),
        )
        db.add(planilla)
        db.flush()
    elif observaciones and not (planilla.observaciones or "").strip():
        planilla.observaciones = observaciones

    for d in docs_pendientes:
        db.add(models.Documento(
            afiliado_doc="", nombre=d["nombre"], tipo=d["ext"], ruta=d["ruta"],
            tamano=d["tamano"], subido_por=token.get("sub", ""),
            contexto="planilla_pago", contexto_id=planilla.id,
        ))
    accion = "Agregó archivos a planilla SS" if reutilizada else "Subió planilla SS"
    crud._log(db, token.get("sub", ""), accion, "Facturación",
              f"{cliente_ref} - {mes} {anio} ({len(subidos)} archivos, {len(omitidos)} omitidos)")
    db.commit()
    return {"ok": True, "id": planilla.id, "archivos": subidos,
            "omitidos": omitidos, "reutilizada": reutilizada}



@router.post("/{planilla_id}/archivos")
async def agregar_archivos(
    planilla_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    token=Depends(require_admin_or_empleado),
):
    import asyncio
    from routers.documentos import _get_s3, _R2_BUCKET, ALLOWED_EXT, MAX_SIZE, _validar_magic
    planilla = db.query(models.PlanillaPago).filter_by(id=planilla_id).first()
    if not planilla:
        raise HTTPException(404, "Planilla no encontrada")
    s3 = _get_s3()
    safe_cliente = re.sub(r'[^\w\-]', '_', planilla.cliente_ref or 'sin_cliente')
    safe_mes     = re.sub(r'[^\w\-]', '_', planilla.mes or 'sin_mes')
    safe_anio    = re.sub(r'[^\w\-]', '_', planilla.anio or 'sin_anio')
    validos, omitidos = [], []
    for file in files:
        nombre = file.filename or "archivo"
        ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
        if ext not in ALLOWED_EXT:
            omitidos.append({"nombre": nombre, "motivo": f"Formato .{ext} no permitido"}); continue
        content = await file.read()
        if len(content) > MAX_SIZE:
            omitidos.append({"nombre": nombre, "motivo": f"Excede {MAX_SIZE // (1024*1024)} MB"}); continue
        if not _validar_magic(ext, content):
            omitidos.append({"nombre": nombre, "motivo": f"Contenido no válido para {ext.upper()}"}); continue
        safe_name = re.sub(r'[^\w.\-]', '_', nombre)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        ruta = (f"planillas/{safe_cliente}/{safe_anio}/{safe_mes}/{unique_name}" if s3
                else f"uploads/planillas/{safe_cliente}/{safe_anio}/{safe_mes}/{unique_name}")
        validos.append({"nombre": nombre, "ext": ext, "ruta": ruta, "tamano": len(content),
                        "content": content, "content_type": file.content_type or "application/octet-stream"})
    if not validos:
        raise HTTPException(400, f"Ningún archivo aceptado: {[o['motivo'] for o in omitidos]}")

    async def _subir(d):
        try:
            if s3:
                await asyncio.to_thread(s3.put_object, Bucket=_R2_BUCKET, Key=d["ruta"],
                                        Body=d["content"], ContentType=d["content_type"])
            else:
                await asyncio.to_thread(os.makedirs, os.path.dirname(d["ruta"]), exist_ok=True)
                def _w():
                    with open(d["ruta"], "wb") as fh: fh.write(d["content"])
                await asyncio.to_thread(_w)
            return d, None
        except Exception as e:
            return d, str(e)

    resultados = await asyncio.gather(*[_subir(d) for d in validos])
    subidos = []
    for d, err in resultados:
        if err:
            omitidos.append({"nombre": d["nombre"], "motivo": f"Error al guardar: {err}"})
        else:
            db.add(models.Documento(
                afiliado_doc="", nombre=d["nombre"], tipo=d["ext"], ruta=d["ruta"],
                tamano=d["tamano"], subido_por=token.get("sub", ""),
                contexto="planilla_pago", contexto_id=planilla_id,
            ))
            subidos.append(d["nombre"])
    db.commit()
    return {"ok": True, "archivos": subidos, "omitidos": omitidos}


@router.post("/consolidar")
def consolidar_duplicadas(db: Session = Depends(get_db), token=Depends(require_admin)):
    """Une planillas duplicadas del mismo cliente+mes+año en una sola (la más
    antigua). Reasigna los documentos (mueve contexto_id) y borra las planillas
    vacías. NO borra archivos de R2 — solo cambia el puntero en la DB."""
    from sqlalchemy import func
    dups = (db.query(models.PlanillaPago.cliente_ref, models.PlanillaPago.mes, models.PlanillaPago.anio)
            .group_by(models.PlanillaPago.cliente_ref, models.PlanillaPago.mes, models.PlanillaPago.anio)
            .having(func.count(models.PlanillaPago.id) > 1)
            .all())
    grupos, eliminadas = 0, 0
    for cliente_ref, mes, anio in dups:
        planillas = (db.query(models.PlanillaPago)
                     .filter_by(cliente_ref=cliente_ref, mes=mes, anio=anio)
                     .order_by(models.PlanillaPago.id.asc())
                     .all())
        if len(planillas) < 2:
            continue
        principal = planillas[0]
        for extra in planillas[1:]:
            (db.query(models.Documento)
             .filter_by(contexto="planilla_pago", contexto_id=extra.id)
             .update({"contexto_id": principal.id}, synchronize_session=False))
            if extra.observaciones and not (principal.observaciones or "").strip():
                principal.observaciones = extra.observaciones
            db.delete(extra)
            eliminadas += 1
        grupos += 1
    if grupos:
        crud._log(db, token.get("sub", ""), "Unió planillas duplicadas", "Facturación",
                  f"{grupos} grupos, {eliminadas} planillas eliminadas")
    db.commit()
    return {"ok": True, "grupos": grupos, "planillas_eliminadas": eliminadas}


@router.delete("/{planilla_id}/archivos/{doc_id}")
def eliminar_archivo(planilla_id: int, doc_id: int, db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    doc = db.query(models.Documento).filter_by(id=doc_id, contexto="planilla_pago", contexto_id=planilla_id).first()
    if not doc:
        raise HTTPException(404, "Archivo no encontrado")
    from routers.documentos import _get_s3, _R2_BUCKET
    s3 = _get_s3()
    if s3 and not doc.ruta.startswith("uploads/"):
        try: s3.delete_object(Bucket=_R2_BUCKET, Key=doc.ruta)
        except Exception: pass
    elif not s3 and os.path.exists(doc.ruta):
        try: os.remove(doc.ruta)
        except Exception: pass
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.delete("/{planilla_id}")
def eliminar_planilla(planilla_id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    planilla = db.query(models.PlanillaPago).filter_by(id=planilla_id).first()
    if not planilla:
        raise HTTPException(404, "Planilla no encontrada")
    docs = db.query(models.Documento).filter_by(contexto="planilla_pago", contexto_id=planilla.id).all()
    from routers.documentos import _get_s3, _R2_BUCKET
    s3 = _get_s3()
    for d in docs:
        if s3 and not d.ruta.startswith("uploads/"):
            try: s3.delete_object(Bucket=_R2_BUCKET, Key=d.ruta)
            except Exception: pass
        db.delete(d)
    cliente = planilla.cliente_ref
    mes_anio = f"{planilla.mes} {planilla.anio}"
    db.delete(planilla)
    crud._log(db, token.get("sub", ""), "Eliminó planilla SS", "Facturación", f"{cliente} - {mes_anio}")
    db.commit()
    return {"ok": True}
