"""Router de autenticación."""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import timedelta
import jwt, time
from database import get_db
import schemas, crud
from .deps import (
    SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS,
    create_token, verify_token, security,
)
from fastapi.security import HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from logger import logger

_limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Protección contra fuerza bruta ────────────────────────────────────────────
_login_attempts: dict = {}   # { ip: {"count": int, "last": float} }
_MAX_ATTEMPTS  = 5
_BLOCK_WINDOW  = 300         # segundos (5 minutos)

def _get_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")


@router.post("/login")
@_limiter.limit("20/minute")
def login(request: Request, data: schemas.LoginRequest, db: Session = Depends(get_db)):
    ip  = _get_ip(request)
    now = time.time()
    rec = _login_attempts.get(ip, {"count": 0, "last": 0.0})

    if rec["count"] >= _MAX_ATTEMPTS and now - rec["last"] < _BLOCK_WINDOW:
        secs_left = int(_BLOCK_WINDOW - (now - rec["last"]))
        logger.warning(f"Login bloqueado para IP {ip} — {rec['count']} intentos fallidos")
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {secs_left // 60}m {secs_left % 60}s"
        )

    user = crud.get_user_by_username(db, data.username)
    if not user or not user.activo:
        rec = {"count": rec["count"] + 1, "last": now}
        _login_attempts[ip] = rec
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    if not user.password or not crud.verify_password(data.password, user.password):
        rec = {"count": rec["count"] + 1, "last": now}
        _login_attempts[ip] = rec
        logger.warning(f"Contraseña incorrecta para usuario '{data.username}' desde IP {ip} (intento {rec['count']})")
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    # Login exitoso — limpiar intentos fallidos
    _login_attempts.pop(ip, None)

    # Migrar passwords en texto plano a bcrypt
    if user.password and not user.password.startswith("$2"):
        user.password = crud.hash_password(data.password)
        db.commit()

    token_data = {"sub": user.username, "rol": user.rol, "nombre": user.nombre}
    access_token = create_token(token_data)
    refresh_token = create_token(
        {**token_data, "type": "refresh"},
        expires=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "rol": user.rol,
        "nombre": user.nombre,
        "username": user.username,
    }


@router.post("/refresh")
def refresh_token(body: dict):
    """Obtiene un nuevo access token usando el refresh token."""
    rt = body.get("refresh_token", "")
    if not rt:
        raise HTTPException(status_code=401, detail="refresh_token requerido")
    try:
        payload = jwt.decode(rt, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token no es de tipo refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    new_access = create_token({"sub": payload["sub"], "rol": payload["rol"], "nombre": payload.get("nombre", "")})
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me")
def me(token=Depends(verify_token)):
    return token
