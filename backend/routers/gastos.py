from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud
from .deps import require_admin

router = APIRouter(tags=["gastos"])


# ─── GASTOS ───────────────────────────────────────────────────────────────────

@router.get("/gastos")
def list_gastos(mes: int = Query(..., ge=1, le=12), anio: int = Query(..., ge=2000, le=2100),
                db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_gastos(db, mes=mes, anio=anio)


@router.post("/gastos", status_code=201)
def create_gasto(data: schemas.GastoCreate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_gasto(db, data)


@router.post("/gastos/copiar")
def copiar_gastos(data: schemas.CopiarMesRequest,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.copiar_gastos_mes_anterior(
        db, data.mes_origen, data.anio_origen, data.mes_destino, data.anio_destino,
        user=token.get("sub", "sistema"))


@router.put("/gastos/{id}")
def update_gasto(id: int, data: schemas.GastoUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_gasto(db, id, data)
    if not result: raise HTTPException(404, "Gasto no encontrado")
    return result


@router.delete("/gastos/{id}")
def delete_gasto(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.delete_gasto(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


# ─── INGRESOS ADICIONALES ────────────────────────────────────────────────────

@router.get("/ingresos-adicionales")
def list_ingresos_adicionales(mes: int = None, anio: int = None,
                               db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_ingresos_adicionales(db, mes=mes, anio=anio)


@router.post("/ingresos-adicionales", status_code=201)
def create_ingreso_adicional(data: schemas.IngresoAdicionalCreate,
                              db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_ingreso_adicional(db, data, user=token.get("sub", "sistema"))


@router.put("/ingresos-adicionales/{id}")
def update_ingreso_adicional(id: int, data: schemas.IngresoAdicionalCreate,
                              db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_ingreso_adicional(db, id, data, user=token.get("sub", "sistema"))
    if not result:
        raise HTTPException(404, "Ingreso adicional no encontrado")
    return result


@router.delete("/ingresos-adicionales/{id}")
def delete_ingreso_adicional(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    ok = crud.delete_ingreso_adicional(db, id, user=token.get("sub", "sistema"))
    if not ok: raise HTTPException(404, "Ingreso adicional no encontrado")
    return {"ok": True}
