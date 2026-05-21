from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, crud
from .deps import require_admin

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("")
def list_usuarios(db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_usuarios(db)


@router.post("", status_code=201)
def create_usuario(data: schemas.UsuarioCreate,
                   db: Session = Depends(get_db), token=Depends(require_admin)):
    existing = crud.get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(400, f"El usuario '{data.username}' ya existe")
    return crud.create_usuario(db, data)


@router.put("/{id}/password")
def change_usuario_password(id: int, data: schemas.UsuarioPasswordUpdate,
                            db: Session = Depends(get_db), token=Depends(require_admin)):
    u = crud.update_usuario_password(db, id, data.password, user=token.get("sub", "admin"))
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    return {"ok": True}


@router.delete("/{id}")
def delete_usuario(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    u = crud.get_usuario(db, id)
    if not u: raise HTTPException(404, "Usuario no encontrado")
    if u.username == "admin":
        raise HTTPException(400, "No puedes eliminar el administrador principal")
    if u.rol == "admin":
        admins_activos = db.query(models.Usuario).filter_by(rol="admin", activo=True).count()
        if admins_activos <= 1:
            raise HTTPException(400, "No puedes eliminar el único admin activo del sistema")
    crud.delete_usuario(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}
