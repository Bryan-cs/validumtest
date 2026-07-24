"""Panel del superadmin: gestión de organizaciones (tenants) y sus usuarios.

Todas las rutas requieren rol superadmin. No usa tenant_scope: el superadmin opera a través de
todas las organizaciones, por lo que el ContextVar queda en None y las consultas no se auto-filtran.
"""
import re
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, provision_organizacion
import models, schemas, crud
from .deps import require_superadmin

router = APIRouter(prefix="/organizaciones", tags=["organizaciones"])


def _slugify(texto: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-')
    return s or "org"


def _slug_unico(db: Session, base: str) -> str:
    slug = base
    i = 2
    while db.query(models.Organizacion).filter_by(slug=slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


def _org_out(db: Session, org: models.Organizacion) -> dict:
    total_u = db.query(func.count(models.Usuario.id)).filter_by(organizacion_id=org.id).scalar()
    total_a = db.query(func.count(models.Afiliado.id)).filter(
        models.Afiliado.organizacion_id == org.id).scalar()
    return {"id": org.id, "nombre": org.nombre, "slug": org.slug, "activo": bool(org.activo),
            "total_usuarios": total_u or 0, "total_afiliados": total_a or 0}


@router.get("")
def list_organizaciones(db: Session = Depends(get_db), token=Depends(require_superadmin)):
    orgs = db.query(models.Organizacion).order_by(models.Organizacion.creado.desc()).all()
    return [_org_out(db, o) for o in orgs]


@router.post("", status_code=201)
def create_organizacion(data: schemas.OrganizacionCreate,
                        db: Session = Depends(get_db), token=Depends(require_superadmin)):
    # username admin único global (login sin selector de organización)
    if crud.get_user_by_username(db, data.admin_username):
        raise HTTPException(400, f"El usuario '{data.admin_username}' ya existe")
    slug = _slug_unico(db, _slugify(data.slug or data.nombre))
    org = provision_organizacion(
        db, nombre=data.nombre, slug=slug,
        admin_username=data.admin_username.lower(),
        admin_password=data.admin_password,
        admin_nombre=data.admin_nombre,
    )
    return _org_out(db, org)


@router.patch("/{org_id}")
def update_organizacion(org_id: int, data: schemas.OrganizacionUpdate,
                        db: Session = Depends(get_db), token=Depends(require_superadmin)):
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    if data.nombre is not None:
        org.nombre = data.nombre
    if data.slug is not None:
        org.slug = _slug_unico(db, _slugify(data.slug))
    if data.activo is not None:
        org.activo = data.activo
    db.commit()
    return _org_out(db, org)


@router.delete("/{org_id}")
def delete_organizacion(org_id: int, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    # Borrado en cascada de los datos de la organización (FK ondelete=CASCADE en Postgres).
    # En SQLite, borramos usuarios explícitamente para no dejar cuentas huérfanas.
    db.query(models.Usuario).filter_by(organizacion_id=org_id).delete()
    db.delete(org)
    db.commit()
    return {"ok": True}


@router.get("/{org_id}/usuarios")
def list_org_usuarios(org_id: int, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    us = db.query(models.Usuario).filter_by(organizacion_id=org_id).all()
    return [{"id": u.id, "nombre": u.nombre, "username": u.username, "rol": u.rol,
             "activo": u.activo, "cliente_ref": u.cliente_ref, "ver_detalle": bool(u.ver_detalle)}
            for u in us]


@router.post("/{org_id}/usuarios", status_code=201)
def create_org_usuario(org_id: int, data: schemas.UsuarioCreate,
                       db: Session = Depends(get_db), token=Depends(require_superadmin)):
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    if crud.get_user_by_username(db, data.username):
        raise HTTPException(400, f"El usuario '{data.username}' ya existe")
    u = models.Usuario(
        nombre=data.nombre, username=data.username.lower(),
        password=crud.hash_password(data.password), rol=data.rol,
        organizacion_id=org_id, cliente_ref=data.cliente_ref,
    )
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id, "nombre": u.nombre, "username": u.username, "rol": u.rol}
