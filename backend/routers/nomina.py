from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud
from .deps import require_admin

router = APIRouter(prefix="/nomina", tags=["nomina"])


@router.get("")
def get_nomina(mes: int = Query(..., ge=1, le=12), anio: int = Query(..., ge=2000, le=2100),
               db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_nomina_mensual(db, mes=mes, anio=anio)


@router.post("/copiar")
def copiar_nomina(data: schemas.CopiarMesRequest,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.copiar_nomina_mes_anterior(
        db, data.mes_origen, data.anio_origen, data.mes_destino, data.anio_destino,
        user=token.get("sub", "sistema"))


@router.put("/{empleado_id}")
def update_nomina_mensual(empleado_id: int, mes: int, anio: int,
                          data: schemas.NominaItemUpdate,
                          db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.upsert_nomina_mensual(db, empleado_id, mes, anio, data.valor,
                                      user=token.get("sub", "sistema"))
