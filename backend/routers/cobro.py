from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import crud
from .deps import require_admin_or_empleado

router = APIRouter(tags=["cobro"])


@router.get("/cobro")
def cobro(empresa: str = "", cliente: str = "", tipo: str = "",
          mes: str = "", anio: str = "", doc: str = "",
          db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    return crud.get_cobro(db, empresa=empresa, cliente=cliente, tipo=tipo,
                          mes=mes, anio=anio, doc=doc)
