"""Router de seguimiento ARL."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import models, schemas
from .deps import verify_token

router = APIRouter(prefix="/seguimiento-arl", tags=["seguimiento-arl"])


@router.get("")
def list_seguimiento(
    cliente: Optional[str] = None,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    q = db.query(models.SeguimientoArl)
    if cliente:
        q = q.filter(models.SeguimientoArl.cliente == cliente)
    return q.order_by(models.SeguimientoArl.creado_en.desc()).all()


@router.post("", status_code=201)
def create_seguimiento(
    data: schemas.SeguimientoArlCreate,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    row = models.SeguimientoArl(**data.model_dump(), estado="activo")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/bulk-estado")
def bulk_estado(
    body: schemas.BulkEstadoBody,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    if not body.ids:
        raise HTTPException(400, "Lista de IDs vacía")
    if body.estado not in ("activo", "retirar", "retirado"):
        raise HTTPException(400, "Estado inválido")
    db.query(models.SeguimientoArl)\
      .filter(models.SeguimientoArl.id.in_(body.ids))\
      .update({"estado": body.estado}, synchronize_session=False)
    db.commit()
    return {"ok": True, "actualizados": len(body.ids)}


@router.put("/{id}")
def update_seguimiento(
    id: int,
    data: schemas.SeguimientoArlUpdate,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    row = db.query(models.SeguimientoArl).filter_by(id=id).first()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{id}")
def delete_seguimiento(
    id: int,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    row = db.query(models.SeguimientoArl).filter_by(id=id).first()
    if not row:
        raise HTTPException(404, "Registro no encontrado")
    db.delete(row)
    db.commit()
    return {"ok": True}
