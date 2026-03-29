"""Router de Planillas de Pago SS."""
import os
import re
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import require_admin
import models, crud

router = APIRouter(prefix="/planillas", tags=["planillas"])


@router.get("")
def listar_planillas(cliente: str = "", mes: str = "", anio: str = "",
                     db: Session = Depends(get_db), token=Depends(require_admin)):
    q = db.query(models.PlanillaPago).order_by(models.PlanillaPago.id.desc())
    if cliente: q = q.filter(models.PlanillaPago.cliente_ref == cliente)
    if mes:     q = q.filter(models.PlanillaPago.mes == mes)
    if anio:    q = q.filter(models.PlanillaPago.anio == anio)
    rows = q.all()
    if not rows:
        return []
    # Batch load all documents (avoid N+1)
    planilla_ids = [p.id for p in rows]
    all_docs = db.query(models.Documento).filter(
        models.Documento.contexto == "planilla_pago",
        models.Documento.contexto_id.in_(planilla_ids),
    ).all()
    docs_by_planilla = {}
    for d in all_docs:
        docs_by_planilla.setdefault(d.contexto_id, []).append(d)
    return [
        {
            "id": p.id, "cliente_ref": p.cliente_ref, "mes": p.mes, "anio": p.anio,
            "observaciones": p.observaciones, "subido_por": p.subido_por,
            "creado": p.creado.isoformat() if p.creado else None,
            "archivos": [{"id": d.id, "nombre": d.nombre, "tamano": d.tamano} for d in docs_by_planilla.get(p.id, [])],
        }
        for p in rows
    ]


@router.post("")
async def crear_planilla(
    cliente_ref: str = Form(...),
    mes: str = Form(...),
    anio: str = Form(...),
    observaciones: str = Form(""),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    token=Depends(require_admin),
):
    planilla = models.PlanillaPago(
        cliente_ref=cliente_ref, mes=mes, anio=anio,
        observaciones=observaciones, subido_por=token.get("sub", ""),
    )
    db.add(planilla)
    db.commit()
    db.refresh(planilla)

    from routers.documentos import _get_s3, _R2_BUCKET, ALLOWED_EXT, MAX_SIZE
    s3 = _get_s3()
    subidos = []
    for file in files:
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        if ext not in ALLOWED_EXT:
            continue
        content = await file.read()
        if len(content) > MAX_SIZE:
            continue
        safe_name = re.sub(r'[^\w.\-]', '_', file.filename or 'archivo')
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        if s3:
            key = f"planillas/{unique_name}"
            s3.put_object(Bucket=_R2_BUCKET, Key=key, Body=content, ContentType=file.content_type or "application/octet-stream")
            ruta = key
        else:
            os.makedirs("uploads/planillas", exist_ok=True)
            ruta = f"uploads/planillas/{unique_name}"
            with open(ruta, "wb") as f:
                f.write(content)
        doc = models.Documento(
            afiliado_doc="", nombre=file.filename, tipo=ext, ruta=ruta,
            tamano=len(content), subido_por=token.get("sub", ""),
            contexto="planilla_pago", contexto_id=planilla.id,
        )
        db.add(doc)
        subidos.append(file.filename)
    crud._log(db, token.get("sub", ""), "Subió planilla SS", "Facturación",
              f"{cliente_ref} - {mes} {anio} ({len(subidos)} archivos)")
    db.commit()
    return {"ok": True, "id": planilla.id, "archivos": subidos}


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
