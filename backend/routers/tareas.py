"""Router de tareas y notificaciones."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud, models
from .deps import verify_token, require_admin

router = APIRouter(prefix="/tareas", tags=["tareas"])


@router.get("")
def list_tareas(skip: int = 0, limit: int = 200,
                db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_tareas(db, token["sub"], token["rol"], skip=skip, limit=limit)


@router.post("", status_code=201)
def create_tarea(data: schemas.TareaCreate, db: Session = Depends(get_db), token=Depends(verify_token)):
    # Solo admin puede crear tareas no privadas (asignadas a otros)
    if not data.privada and token.get("rol") != "admin":
        # Empleados pueden crear solo privadas auto-asignadas
        data.privada = True
        data.asignado_a = token["sub"]
    data.creado_por = token["sub"]
    if data.privada:
        data.asignado_a = token["sub"]
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
def cambiar_estado(id: int, body: dict = None, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Empleado cambia estado: pendiente → en_proceso → completada."""
    if body is None:
        body = {}
    nuevo = body.get("estado", "")
    nota  = body.get("nota", "")
    t = crud.cambiar_estado_tarea(db, id, nuevo, token["sub"], nota, rol=token.get("rol", ""))
    if not t:
        raise HTTPException(400, "Estado inválido o tarea no encontrada")
    if isinstance(t, dict) and "error" in t:
        if t["error"] == "unauthorized":
            raise HTTPException(403, "No tienes permiso sobre esta tarea")
        raise HTTPException(400, t["error"])
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


@router.delete("/{id}")
def eliminar_tarea(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Admin puede eliminar tareas finalizadas o privadas que creó. Empleado solo sus privadas."""
    t = db.query(models.Tarea).filter_by(id=id).first()
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    es_admin = token.get("rol") == "admin"
    es_dueno = t.creado_por == token["sub"]
    estado_ok = t.estado in ("completada", "finalizada")
    if es_admin and estado_ok:
        pass  # admin puede eliminar cualquier tarea finalizada/completada
    elif es_dueno and t.privada and estado_ok:
        pass  # dueño puede eliminar sus privadas completadas/finalizadas
    else:
        raise HTTPException(403, "No tienes permiso para eliminar esta tarea")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/{id}/comentarios", status_code=201)
def comentar(id: int, data: schemas.TareaComentarioCreate,
             db: Session = Depends(get_db), token=Depends(verify_token)):
    data.usuario = token["sub"]
    result = crud.add_comentario(db, id, data)
    if not result:
        raise HTTPException(404, "Tarea no encontrada")
    return result
