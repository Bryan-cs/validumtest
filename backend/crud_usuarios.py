"""CRUD de usuarios.

NOTA multi-tenant: el modelo Usuario está EXCLUIDO del auto-filtro por organización (el superadmin,
sin organización, debe poder gestionar usuarios de cualquier org). Por eso aquí el scoping por
organización es EXPLÍCITO usando la organización activa de la petición (tenant.current_org_id).
`get_user_by_username` es la excepción: se usa en el login ANTES de fijar la organización, así que
busca en todas las organizaciones (username es único global)."""
from sqlalchemy import func
import models, schemas
from crud_helpers import hash_password, _log
from crud_cache import cache_invalidar
from tenant import current_org_id


def _org():
    return current_org_id.get()


def get_user_by_username(db, username):
    # Global a propósito (login): username es único en todo el sistema.
    return db.query(models.Usuario).filter(func.lower(models.Usuario.username) == username.lower()).first()

def get_usuario(db, id):
    q = db.query(models.Usuario).filter_by(id=id)
    org = _org()
    if org is not None:
        q = q.filter(models.Usuario.organizacion_id == org)
    return q.first()

def get_usuarios(db):
    q = db.query(models.Usuario)
    org = _org()
    if org is not None:
        q = q.filter(models.Usuario.organizacion_id == org)
    return [{"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"activo":u.activo,"cliente_ref":u.cliente_ref,"ver_detalle":bool(u.ver_detalle)} for u in q.all()]

def set_ver_detalle(db, id: int, valor: bool, user: str = ""):
    u = get_usuario(db, id)
    if not u:
        return None
    u.ver_detalle = bool(valor)
    _log(db, user, ("habilitó" if valor else "deshabilitó") + " ver detalle en portal", "Usuarios", u.username)
    from routers.deps import invalidate_user_cache
    invalidate_user_cache(u.username)
    db.commit(); db.refresh(u)
    return u

def create_usuario(db, data: schemas.UsuarioCreate):
    # Usuario está excluido del auto-stamp: fijamos organizacion_id explícitamente desde la org activa.
    u = models.Usuario(nombre=data.nombre, username=data.username.lower(), password=hash_password(data.password),
                       rol=data.rol, cliente_ref=data.cliente_ref, organizacion_id=_org())
    db.add(u); db.commit(); db.refresh(u)
    return {"id":u.id,"nombre":u.nombre,"username":u.username,"rol":u.rol,"cliente_ref":u.cliente_ref}

def update_usuario_password(db, id: int, new_password: str, user: str = ""):
    u = get_usuario(db, id)
    if not u:
        return None
    u.password = hash_password(new_password)
    _log(db, user, "cambió contraseña de usuario", "Usuarios", u.username)
    db.commit()
    return u

def delete_usuario(db, id, user=""):
    u = get_usuario(db, id)   # scopeado por organización
    if u:
        _log(db, user, "eliminó un usuario", "Usuarios", u.username)
        from routers.deps import invalidate_user_cache
        invalidate_user_cache(u.username)
        cache_invalidar(f"usuario_rol:{u.username}")
        db.delete(u)
        db.commit()
