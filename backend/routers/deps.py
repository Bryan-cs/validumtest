"""Dependencias compartidas para los routers."""
import os
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
import jwt

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # En cualquier entorno sin SECRET_KEY configurada se usa clave de desarrollo
    # En producción (ENVIRONMENT=production) se bloquea el arranque
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise RuntimeError("SECRET_KEY env var is required in production")
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
        # Reject refresh tokens used as access tokens
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Token de refresco no válido como token de acceso")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def require_admin(token=Depends(verify_token)):
    if token.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol administrador")
    return token
