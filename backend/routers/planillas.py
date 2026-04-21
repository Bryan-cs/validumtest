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
    if not rows:
        return {"total": 0, "items": []}
    # Batch load all documents (avoid N+1)
    planilla_ids = [p.id for p in rows]
    all_docs = db.query(models.Documento).filter(
        models.Documento.contexto == "planilla_pago",
        models.Documento.contexto_id.in_(planilla_ids),
    ).all()
    docs_by_planilla = {}
    for d in all_docs:
        docs_by_planilla.setdefault(d.contexto_id, []).append(d)
    items = [
        {
            "id": p.id, "cliente_ref": p.cliente_ref, "mes": p.mes, "anio": p.anio,
            "observaciones": p.observaciones, "subido_por": p.subido_por,
            "creado": p.creado.isoformat() if p.creado else None,
            "archivos": [{"id": d.id, "nombre": d.nombre, "tamano": d.tamano} for d in docs_by_planilla.get(p.id, [])],
        }
        for p in rows
    ]
    return {"total": total, "items": items}


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
    from routers.documentos import _get_s3, _R2_BUCKET, ALLOWED_EXT, MAX_SIZE
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
    planilla = models.PlanillaPago(
        cliente_ref=cliente_ref, mes=mes, anio=anio,
        observaciones=observaciones, subido_por=token.get("sub", ""),
    )
    db.add(planilla)
    db.flush()

    for d in docs_pendientes:
        db.add(models.Documento(
            afiliado_doc="", nombre=d["nombre"], tipo=d["ext"], ruta=d["ruta"],
            tamano=d["tamano"], subido_por=token.get("sub", ""),
            contexto="planilla_pago", contexto_id=planilla.id,
        ))
    crud._log(db, token.get("sub", ""), "Subió planilla SS", "Facturación",
              f"{cliente_ref} - {mes} {anio} ({len(subidos)} archivos, {len(omitidos)} omitidos)")
    db.commit()
    return {"ok": True, "id": planilla.id, "archivos": subidos, "omitidos": omitidos}


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
