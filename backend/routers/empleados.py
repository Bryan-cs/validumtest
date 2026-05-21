from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, crud
from .deps import require_admin

router = APIRouter(prefix="/empleados", tags=["empleados"])


@router.get("")
def list_empleados(db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_empleados(db)


@router.post("", status_code=201)
def create_empleado(data: schemas.EmpleadoCreate,
                    db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_empleado(db, data)


@router.put("/{id}")
def update_empleado(id: int, data: schemas.EmpleadoCreate,
                    db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_empleado(db, id, data)
    if not result: raise HTTPException(404, "Empleado no encontrado")
    return result


@router.delete("/{id}")
def delete_empleado(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "Empleado no encontrado")
    crud.delete_empleado(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}
