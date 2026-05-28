"""Credenciales de portales — EPS, CCF, Aportes en Línea, Pago Simple, Asopagos."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import require_admin, require_admin_or_empleado
import models, schemas
from crud_helpers import _log
import os, hashlib, base64

PORTALES_VALIDOS = {"EPS", "CCF", "ARL", "Aportes en Línea", "Pago Simple", "Asopagos"}

router = APIRouter(prefix="/credenciales", tags=["credenciales"])


def _get_fernet():
    from cryptography.fernet import Fernet
    secret = os.getenv("SECRET_KEY", "dev-insecure-key-bbc-change-in-prod")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _encrypt(text: str) -> str:
    return _get_fernet().encrypt(text.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return "[error al descifrar]"


def _to_dict(c: models.CredencialPortal, include_clave: bool = False) -> dict:
    from models import COL_TZ
    from datetime import timezone
    def _fmt(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(COL_TZ).strftime("%d/%m/%Y")

    return {
        "id":             c.id,
        "tipo_doc":       c.tipo_doc,
        "numero_doc":     c.numero_doc,
        "titular":        c.titular,
        "portal":         c.portal,
        "entidad":        c.entidad,
        "usuario_portal": c.usuario_portal,
        "clave_portal":   _decrypt(c.clave_portal) if include_clave else None,
        "obs":            c.obs,
        "creado_por":     c.creado_por,
        "creado":         _fmt(c.creado),
        "actualizado":    _fmt(c.actualizado),
    }


@router.get("")
def listar(db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    rows = (db.query(models.CredencialPortal)
              .order_by(models.CredencialPortal.portal, models.CredencialPortal.entidad)
              .all())
    return [_to_dict(c) for c in rows]


@router.post("", status_code=201)
def crear(data: schemas.CredencialCreate, db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    if data.portal not in PORTALES_VALIDOS:
        raise HTTPException(400, f"Portal debe ser: {', '.join(sorted(PORTALES_VALIDOS))}")
    c = models.CredencialPortal(
        tipo_doc=data.tipo_doc,
        numero_doc=data.numero_doc,
        titular=data.titular,
        portal=data.portal,
        entidad=data.entidad,
        usuario_portal=data.usuario_portal,
        clave_portal=_encrypt(data.clave_portal),
        obs=data.obs,
        creado_por=token.get("sub", ""),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    _log(db, token.get("sub", ""), "registró credencial de portal", "Credenciales",
         f"{data.portal} — {data.entidad} ({data.titular})")
    return _to_dict(c)


@router.put("/{cred_id}")
def actualizar(cred_id: int, data: schemas.CredencialUpdate,
               db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    c = db.query(models.CredencialPortal).filter_by(id=cred_id).first()
    if not c:
        raise HTTPException(404, "Credencial no encontrada")
    if data.tipo_doc is not None:       c.tipo_doc       = data.tipo_doc
    if data.numero_doc is not None:     c.numero_doc     = data.numero_doc
    if data.titular is not None:        c.titular        = data.titular
    if data.portal is not None:
        if data.portal not in PORTALES_VALIDOS:
            raise HTTPException(400, "Portal inválido")
        c.portal = data.portal
    if data.entidad is not None:        c.entidad        = data.entidad
    if data.usuario_portal is not None: c.usuario_portal = data.usuario_portal
    if data.clave_portal is not None:   c.clave_portal   = _encrypt(data.clave_portal)
    if data.obs is not None:            c.obs            = data.obs
    db.commit()
    _log(db, token.get("sub", ""), "editó credencial de portal", "Credenciales",
         f"{c.portal} — {c.entidad}")
    return _to_dict(c)


@router.delete("/{cred_id}")
def eliminar(cred_id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    c = db.query(models.CredencialPortal).filter_by(id=cred_id).first()
    if not c:
        raise HTTPException(404, "Credencial no encontrada")
    desc = f"{c.portal} — {c.entidad} ({c.titular})"
    db.delete(c)
    db.commit()
    _log(db, token.get("sub", ""), "eliminó credencial de portal", "Credenciales", desc)
    return {"ok": True}


@router.get("/{cred_id}/clave")
def revelar_clave(cred_id: int, db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    c = db.query(models.CredencialPortal).filter_by(id=cred_id).first()
    if not c:
        raise HTTPException(404, "Credencial no encontrada")
    _log(db, token.get("sub", ""), "reveló clave de portal", "Credenciales",
         f"{c.portal} — {c.entidad}")
    return {"clave": _decrypt(c.clave_portal)}
