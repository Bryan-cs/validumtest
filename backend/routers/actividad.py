from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import crud
from .deps import require_admin

router = APIRouter(tags=["actividad"])


@router.get("/actividad")
def actividad(modulo: str = "", usuario: str = "",
              desde: str = "", hasta: str = "",
              skip: int = 0, limit: int = 200,
              db: Session = Depends(get_db), token=Depends(require_admin)):
    limit = min(limit, 1000) if limit > 0 else 200
    return crud.get_actividad(db, modulo=modulo, usuario=usuario, desde=desde, hasta=hasta,
                              skip=skip, limit=limit)


@router.delete("/actividad")
def clear_actividad(db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.clear_actividad(db, user=token.get("sub", "sistema"))
    return {"ok": True}
