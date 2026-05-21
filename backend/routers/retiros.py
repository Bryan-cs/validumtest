from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud
from models import COL_TZ
from .deps import verify_token

router = APIRouter(prefix="/retiros", tags=["retiros"])

_MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
          "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]


@router.get("")
def list_retiros(anio: str = "", mes: str = "", doc: str = "",
                 skip: int = 0, limit: int = 500,
                 db: Session = Depends(get_db), token=Depends(verify_token)):
    limit = min(limit, 500)
    return crud.get_retiros(db, anio=anio, mes=mes, doc=doc, skip=skip, limit=limit)


@router.post("", status_code=201)
def create_retiro(data: schemas.RetiroCreate,
                  db: Session = Depends(get_db), token=Depends(verify_token)):
    afil = crud.get_afiliado_by_doc(db, data.doc)
    if not afil: raise HTTPException(404, "Afiliado no encontrado")
    mes_actual = _MESES[datetime.now(COL_TZ).month - 1]
    pendientes = crud.get_facturas_pendientes_by_doc(db, data.doc, mes=mes_actual)
    data.registrado_por = token.get("sub", "sistema")
    retiro = crud.create_retiro(db, data)
    return {"retiro": retiro, "facturas_pendientes": len(pendientes),
            "codigos_pendientes": [f.codigo for f in pendientes]}


@router.delete("/{id}")
def delete_retiro(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    crud.delete_retiro(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}
