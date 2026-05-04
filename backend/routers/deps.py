"""Dependencias compartidas para los routers."""
import os
import time
import uuid
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
TOKEN_EXPIRE_MINUTES = 15          # access token de corta duración
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()

# Cache en memoria para verificación de usuario activo (TTL 5 min, máx 500 entradas)
_user_active_cache = {}  # {username: (is_active, timestamp)}
_USER_CACHE_TTL  = 300   # 5 minutos
_USER_CACHE_MAX  = 500   # entradas máximas


def _is_user_active(username: str) -> bool:
    """Verifica si el usuario está activo, usando cache en memoria."""
    now = time.time()
    cached = _user_active_cache.get(username)
    if cached and (now - cached[1]) < _USER_CACHE_TTL:
        return cached[0]
    # Cache miss o expirado — consultar DB
    from database import SessionLocal
    import models
    db = SessionLocal()
    try:
        user = db.query(models.Usuario.activo).filter_by(username=username).first()
        active = bool(user and user.activo)
    finally:
        db.close()
    if len(_user_active_cache) >= _USER_CACHE_MAX:
        _user_active_cache.clear()
    _user_active_cache[username] = (active, now)
    return active


def invalidate_user_cache(username: str = None):
    """Invalida el cache de usuario (llamar al desactivar/eliminar un usuario)."""
    if username:
        _user_active_cache.pop(username, None)
    else:
        _user_active_cache.clear()


def _decode_token(token: str) -> dict:
    """Decodifica y valida un JWT dado el string raw. Lanza excepción si inválido."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") == "refresh":
        raise jwt.InvalidTokenError("Token de refresco no válido como token de acceso")
    if not _is_user_active(payload.get("sub", "")):
        raise jwt.InvalidTokenError("Usuario desactivado o eliminado")
    return payload


def is_token_blacklisted(jti: str) -> bool:
    """Verifica si un jti está en la blacklist (solo para refresh tokens)."""
    if not jti:
        return False
    from database import SessionLocal
    import models
    db = SessionLocal()
    try:
        return db.query(models.TokenBlacklist).filter_by(jti=jti).first() is not None
    finally:
        db.close()


def create_token(data: dict, expires: timedelta = None):
    payload = data.copy()
    if expires is None:
        expires = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload["exp"] = datetime.now(timezone.utc) + expires
    payload["jti"] = str(uuid.uuid4())  # ID único por token
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Token de refresco no válido como token de acceso")
        # SEC2-A6: verificar blacklist de access tokens (post-logout)
        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token invalidado")
        # Verificar que el usuario siga activo (con cache de 5 min)
        if not _is_user_active(payload.get("sub", "")):
            raise HTTPException(status_code=401, detail="Usuario desactivado o eliminado")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def require_admin(token=Depends(verify_token)):
    if token.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol administrador")
    return token


def require_admin_or_empleado(token=Depends(verify_token)):
    if token.get("rol") not in ("admin", "empleado"):
        raise HTTPException(status_code=403, detail="Requiere rol administrador o empleado")
    return token
