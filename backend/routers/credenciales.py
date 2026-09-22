"""Credenciales de portales — EPS, CCF, Aportes en Línea, Pago Simple, Asopagos.

Las de Pago Simple / SuAporte alimentan el envío PILA: usuario, contraseña y
clave de API por NIT de empresa. Si esa empresa no tiene ficha, se usa la
clave global del entorno.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import require_admin, require_admin_or_empleado
import models, schemas
from crud_helpers import _log
import os, hashlib, base64

PORTALES_VALIDOS = {"EPS", "CCF", "ARL", "Aportes en Línea", "Pago Simple",
                    "Asopagos", "SuAporte"}
PORTALES_OPERADOR = ("Pago Simple", "SuAporte", "Asopagos")

router = APIRouter(prefix="/credenciales", tags=["credenciales"])


def _get_fernet():
    # FERNET_KEY independiente de SECRET_KEY: rotar JWT no destruye credenciales cifradas.
    # Fallback a SECRET_KEY para retrocompatibilidad con datos existentes.
    from cryptography.fernet import Fernet
    secret = os.getenv("FERNET_KEY") or os.getenv("SECRET_KEY", "dev-insecure-key-bbc-change-in-prod")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _encrypt(text: str) -> str:
    return _get_fernet().encrypt(text.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return "[error al descifrar]"


def _norm_doc(s: str) -> str:
    return "".join(c for c in str(s or "") if c.isalnum()).upper()


def credenciales_de_aportante(db: Session, num_doc: str):
    """Usuario, contraseña y clave de API de esa empresa en el operador.

    Devuelve None si no hay ficha para ese NIT: el llamador cae a las variables
    de entorno. El NIT se compara sin puntos ni guiones.
    """
    doc = _norm_doc(num_doc)
    if not doc:
        return None
    filas = (db.query(models.CredencialPortal)
               .filter(models.CredencialPortal.portal.in_(PORTALES_OPERADOR))
               .all())
    candidatas = [c for c in filas if _norm_doc(c.numero_doc) == doc]
    if not candidatas:
        return None
    from services.pila.operador import operador_nombre
    preferido = "Pago Simple" if operador_nombre() == "pagosimple" else "SuAporte"
    candidatas.sort(key=lambda c: (0 if c.portal == preferido else 1, c.id))
    c = candidatas[0]
    usuario = (c.usuario_portal or "").strip()
    clave = _decrypt(c.clave_portal) if c.clave_portal else ""
    api = _decrypt(c.clave_api) if c.clave_api else ""
    if clave == "[error al descifrar]" or api == "[error al descifrar]":
        return None
    if not (usuario and clave):
        return None
    if not api:
        from services.pila.operador import credenciales as _env
        api = _env()[2]
    return usuario, clave, api


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
        "tiene_clave_api": bool(c.clave_api),
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
        clave_api=_encrypt(data.clave_api) if data.clave_api else None,
        obs=data.obs,
        creado_por=token.get("sub", ""),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    _log(db, token.get("sub", ""), "registró credencial de portal", "Credenciales",
         f"{data.portal} — {data.entidad} ({data.titular})")
    db.commit()
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
    if data.clave_api is not None:
        c.clave_api = _encrypt(data.clave_api) if data.clave_api else None
    if data.obs is not None:            c.obs            = data.obs
    db.commit()
    _log(db, token.get("sub", ""), "editó credencial de portal", "Credenciales",
         f"{c.portal} — {c.entidad}")
    db.commit()
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
    db.commit()
    return {"ok": True}


@router.get("/{cred_id}/clave")
def revelar_clave(cred_id: int, db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    c = db.query(models.CredencialPortal).filter_by(id=cred_id).first()
    if not c:
        raise HTTPException(404, "Credencial no encontrada")
    _log(db, token.get("sub", ""), "reveló clave de portal", "Credenciales",
         f"{c.portal} — {c.entidad}")
    db.commit()
    return {
        "clave": _decrypt(c.clave_portal),
        "clave_api": _decrypt(c.clave_api) if c.clave_api else None,
    }
