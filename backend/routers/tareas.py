"""Router de tareas y notificaciones."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import schemas, crud
from .deps import verify_token, require_admin

router = APIRouter(prefix="/tareas", tags=["tareas"])


@router.get("")
def list_tareas(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_tareas(db, token["sub"], token["rol"])


@router.post("", status_code=201)
def create_tarea(data: schemas.TareaCreate, db: Session = Depends(get_db), token=Depends(require_admin)):
    data.creado_por = token["sub"]
    return crud.create_tarea(db, data)


@router.put("/{id}/completar")
def completar(id: int, body: dict = {}, db: Session = Depends(get_db), token=Depends(verify_token)):
    t = crud.completar_tarea(db, id, token["sub"], body.get("nota", ""))
    if not t:
        raise HTTPException(404, "Tarea no encontrada")
    return t


@router.post("/{id}/comentarios", status_code=201)
def comentar(id: int, data: schemas.TareaComentarioCreate,
             db: Session = Depends(get_db), token=Depends(verify_token)):
    data.usuario = token["sub"]
    return crud.add_comentario(db, id, data)


@router.get("/notificaciones")
def notificaciones(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_notificaciones(db, token["sub"])


@router.put("/notificaciones/leer")
def leer_notificaciones(db: Session = Depends(get_db), token=Depends(verify_token)):
    crud.marcar_notificaciones_leidas(db, token["sub"])
    return {"ok": True}
