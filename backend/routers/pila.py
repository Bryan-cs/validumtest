"""Catálogos PILA — códigos normativos que consumen los formularios.

`pila_codigos` es una tabla global (no lleva `organizacion_id`): la define la
norma y es idéntica para todas las organizaciones. Por eso las rutas solo leen;
el catálogo se actualiza sembrando desde `services/pila/catalogos.py` cuando el
Ministerio publica una versión nueva del anexo, no desde la aplicación.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import require_admin_or_empleado
from services.pila import catalogos
import models

router = APIRouter(prefix="/pila", tags=["pila"])


@router.get("/codigos")
def listar_codigos(tipo: str = "", incluir_derogados: bool = False,
                   db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    """Códigos de un catálogo, o de todos si no se pide uno.

    Por defecto devuelve solo los vigentes: un formulario no debe ofrecer un
    código que el anexo actual ya no permite. `incluir_derogados` existe para
    poder mostrar el nombre de un código viejo al abrir una planilla histórica.
    """
    if tipo and tipo not in catalogos.CATALOGOS:
        raise HTTPException(400, f"Catálogo desconocido. Disponibles: "
                                 f"{', '.join(sorted(catalogos.CATALOGOS))}")

    q = db.query(models.PilaCodigo)
    if tipo:
        q = q.filter(models.PilaCodigo.tipo == tipo)
    if not incluir_derogados:
        q = q.filter(models.PilaCodigo.vigente == True)  # noqa: E712

    filas = q.order_by(models.PilaCodigo.tipo, models.PilaCodigo.codigo).all()
    items = [{"tipo": f.tipo, "codigo": f.codigo, "nombre": f.nombre, "vigente": bool(f.vigente)}
             for f in filas]

    return {
        "anexo_version": catalogos.ANEXO_VERSION,
        "anexo_fecha": catalogos.ANEXO_FECHA,
        "total": len(items),
        "items": items,
    }
