"""Dependencias compartidas para los routers."""
import os
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
import jwt

_INSECURE_KEYS = {"dev-only-key-do-not-use-in-prod", "cambia-esta-clave-por-una-segura-antes-de-produccion"}
SECRET_KEY = os.getenv("SECRET_KEY", "")
_is_production = os.getenv("ENVIRONMENT", "development") == "production" or os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("DATABASE_URL", "").startswith("postgresql")
if _is_production and (not SECRET_KEY or SECRET_KEY in _INSECURE_KEYS):
    raise RuntimeError("SECRET_KEY env var segura es requerida en producción (detectado entorno de producción)")
if not SECRET_KEY:
    SECRET_KEY = "dev-only-key-do-not-use-in-prod"
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 12
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()


def create_token(data: dict, expires: timedelta = None):
    payload = data.copy()
    if expires is None:
        expires = timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload["exp"] = datetime.now(timezone.utc) + expires
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Token de refresco no válido como token de acceso")
        # Verificar que el usuario siga activo en DB
        from database import SessionLocal
        import models
        db = SessionLocal()
        try:
            user = db.query(models.Usuario).filter_by(username=payload.get("sub"), activo=True).first()
            if not user:
                raise HTTPException(status_code=401, detail="Usuario desactivado o eliminado")
        finally:
            db.close()
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def require_admin(token=Depends(verify_token)):
    if token.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol administrador")
    return token
