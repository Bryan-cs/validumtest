"""CRUD de usuarios."""
from sqlalchemy import func
import models, schemas
from crud_helpers import hash_password, _log
from crud_cache import cache_invalidar


def get_user_by_username(db, username):
    return db.query(models.Usuario).filter(func.lower(models.Usuario.username) == username.lower()).first()

def get_usuario(db, id):
    return db.query(models.Usuario).filter_by(id=id).first()

def get_usuarios(db):
    return [{"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"activo":u.activo,"cliente_ref":u.cliente_ref,"ver_detalle":bool(u.ver_detalle)} for u in db.query(models.Usuario).all()]

def set_ver_detalle(db, id: int, valor: bool, user: str = ""):
    u = db.query(models.Usuario).filter_by(id=id).first()
    if not u:
        return None
    u.ver_detalle = bool(valor)
    _log(db, user, ("habilitó" if valor else "deshabilitó") + " ver detalle en portal", "Usuarios", u.username)
    from routers.deps import invalidate_user_cache
    invalidate_user_cache(u.username)
    db.commit(); db.refresh(u)
    return u

def create_usuario(db, data: schemas.UsuarioCreate):
    u = models.Usuario(nombre=data.nombre, username=data.username.lower(), password=hash_password(data.password), rol=data.rol, cliente_ref=data.cliente_ref)
    db.add(u); db.commit(); db.refresh(u)
    return {"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"cliente_ref":u.cliente_ref}

def update_usuario_password(db, id: int, new_password: str, user: str = ""):
    u = db.query(models.Usuario).filter_by(id=id).first()
    if not u:
        return None
    u.password = hash_password(new_password)
    _log(db, user, "cambió contraseña de usuario", "Usuarios", u.username)
    db.commit()
    return u

def delete_usuario(db, id, user=""):
    u = db.query(models.Usuario).filter_by(id=id).first()
    if u:
        _log(db, user, "eliminó un usuario", "Usuarios", u.username)
        from routers.deps import invalidate_user_cache
        invalidate_user_cache(u.username)
        cache_invalidar(f"usuario_rol:{u.username}")
    db.query(models.Usuario).filter_by(id=id).delete()
    db.commit()
