"""Router de tareas y notificaciones."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud, models
from .deps import verify_token, require_admin

router = APIRouter(prefix="/tareas", tags=["tareas"])


@router.get("")
def list_tareas(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_tareas(db, token["sub"], token["rol"])


@router.post("", status_code=201)
def create_tarea(data: schemas.TareaCreate, db: Session = Depends(get_db), token=Depends(require_admin)):
    data.creado_por = token["sub"]
    return crud.create_tarea(db, data)


# ── Rutas estáticas ANTES de las dinámicas ────────────────────────────────────

@router.get("/notificaciones")
def notificaciones(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_notificaciones(db, token["sub"])


@router.put("/notificaciones/leer")
def leer_notificaciones(db: Session = Depends(get_db), token=Depends(verify_token)):
    crud.marcar_notificaciones_leidas(db, token["sub"])
    return {"ok": True}


@router.delete("/notificaciones")
def limpiar_notificaciones(db: Session = Depends(get_db), token=Depends(verify_token)):
    db.query(models.Notificacion).filter_by(usuario=token["sub"]).delete()
    db.commit()
    return {"ok": True}


@router.put("/finalizar-lote")
def finalizar_lote(body: dict, db: Session = Depends(get_db), token=Depends(require_admin)):
    """Admin finaliza varias tareas completadas a la vez."""
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "Lista de IDs vacía")
    resultados = []
    for tid in ids:
        t = crud.finalizar_tarea(db, tid, token["sub"])
        if t:
            resultados.append(t)
    return {"finalizadas": len(resultados), "tareas": resultados}


# ── Rutas dinámicas ───────────────────────────────────────────────────────────

@router.put("/{id}/estado")
def cambiar_estado(id: int, body: dict = {}, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Empleado cambia estado: pendiente → en_proceso → completada."""
    nuevo = body.get("estado", "")
    nota  = body.get("nota", "")
    t = crud.cambiar_estado_tarea(db, id, nuevo, token["sub"], nota, rol=token.get("rol", ""))
    if not t:
        raise HTTPException(400, "Estado inválido o tarea no encontrada")
    return t


@router.put("/{id}/finalizar")
def finalizar(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    """Admin finaliza una tarea completada. Queda en historial."""
    t = crud.finalizar_tarea(db, id, token["sub"])
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    if isinstance(t, dict) and "error" in t:
        raise HTTPException(400, t["error"])
    return t


@router.post("/{id}/comentarios", status_code=201)
def comentar(id: int, data: schemas.TareaComentarioCreate,
             db: Session = Depends(get_db), token=Depends(verify_token)):
    data.usuario = token["sub"]
    result = crud.add_comentario(db, id, data)
    if not result:
        raise HTTPException(404, "Tarea no encontrada")
    return result
