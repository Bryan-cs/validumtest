from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models, crud
from .deps import require_admin, require_admin_or_empleado

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(anio: str = "", mes: str = "",
              db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    return crud.get_dashboard(db, anio=anio, mes=mes)


@router.get("/dashboard/clientes")
def dashboard_clientes(anio: str = "", mes: str = "",
                       db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_resumen_clientes(db, anio=anio, mes=mes)


@router.get("/dashboard/cliente/{cliente}")
def dashboard_cliente(cliente: str, anio: str = "", mes: str = "",
                      db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_dashboard_cliente(db, cliente=cliente, anio=anio, mes=mes)


@router.get("/clientes")
def list_clientes(db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    """Retorna la lista de clientes únicos (cliente_txt) de afiliados activos."""
    rows = (db.query(models.Afiliado.cliente_txt)
              .filter(models.Afiliado.activo == True,
                      models.Afiliado.cliente_txt != None,
                      models.Afiliado.cliente_txt != "")
              .distinct()
              .order_by(models.Afiliado.cliente_txt)
              .all())
    return [r[0] for r in rows]
