from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud
from .deps import verify_token, require_admin, require_admin_or_empleado

router = APIRouter(tags=["config"])


@router.get("/config")
def get_config(db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    return crud.get_config(db)


@router.put("/config")
def update_config(data: schemas.ConfigUpdate,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_config(db, data, user=token.get("sub", "sistema"))


@router.get("/listas")
def get_listas(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_listas(db)


@router.put("/listas/{nombre}")
def update_lista(nombre: str, data: schemas.ListaUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_lista(db, nombre, data.items, user=token.get("sub", "sistema"))
