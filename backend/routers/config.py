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


@router.post("/listas/sincronizar-pila")
def sincronizar_listas_pila(db: Session = Depends(get_db), token=Depends(require_admin)):
    """Rehace las listas de EPS, AFP y caja desde el catálogo PILA.

    Se mantenían a mano y se desincronizaron del catálogo, que es el que tiene
    los códigos que van al archivo plano. Esto las vuelve a alinear.
    """
    return crud.sincronizar_listas_pila(db, user=token.get("sub", "sistema"))


@router.put("/listas/{nombre}")
def update_lista(nombre: str, data: schemas.ListaUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_lista(db, nombre, data.items, user=token.get("sub", "sistema"))
