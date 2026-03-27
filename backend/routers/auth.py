"""Router de autenticación."""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import timedelta
import jwt, time
from database import get_db
import schemas, crud, models
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

# ── Protección contra fuerza bruta (usando DB para funcionar con múltiples workers) ──
import threading
_MAX_ATTEMPTS  = 5
_BLOCK_WINDOW  = 300         # segundos (5 minutos)
_attempts_lock = threading.Lock()

def _get_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")

def _get_attempts(db: Session, ip: str):
    """Obtiene intentos de login desde la tabla login_attempts."""
    row = db.query(models.LoginAttempt).filter_by(ip=ip).first()
    if not row:
        return {"count": 0, "last": 0.0}
    return {"count": row.count, "last": row.last_attempt}

def _set_attempts(db: Session, ip: str, count: int, last: float):
    """Guarda intentos de login en la tabla login_attempts."""
    row = db.query(models.LoginAttempt).filter_by(ip=ip).first()
    if row:
        row.count = count
        row.last_attempt = last
    else:
        db.add(models.LoginAttempt(ip=ip, count=count, last_attempt=last))
    db.commit()

def _clear_attempts(db: Session, ip: str):
    db.query(models.LoginAttempt).filter_by(ip=ip).delete()
    db.commit()


@router.post("/login")
@_limiter.limit("20/minute")
def login(request: Request, data: schemas.LoginRequest, db: Session = Depends(get_db)):
    ip  = _get_ip(request)
    now = time.time()
    rec = _get_attempts(db, ip)

    if rec["count"] >= _MAX_ATTEMPTS and now - rec["last"] < _BLOCK_WINDOW:
        secs_left = int(_BLOCK_WINDOW - (now - rec["last"]))
        logger.warning(f"Login bloqueado para IP {ip} — {rec['count']} intentos fallidos")
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {secs_left // 60}m {secs_left % 60}s"
        )
    # Si la ventana expiró, resetear contador
    if rec["count"] >= _MAX_ATTEMPTS and now - rec["last"] >= _BLOCK_WINDOW:
        rec = {"count": 0, "last": 0.0}

    user = crud.get_user_by_username(db, data.username)
    if not user or not user.activo:
        _set_attempts(db, ip, rec["count"] + 1, now)
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    if not user.password or not crud.verify_password(data.password, user.password):
        _set_attempts(db, ip, rec["count"] + 1, now)
        logger.warning(f"Contraseña incorrecta para usuario '{data.username}' desde IP {ip} (intento {rec['count']+1})")
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    # Login exitoso — limpiar intentos fallidos
    _clear_attempts(db, ip)

    # Migrar passwords en texto plano a bcrypt
    if user.password and not user.password.startswith("$2"):
        user.password = crud.hash_password(data.password)
        db.commit()

    token_data = {"sub": user.username, "rol": user.rol, "nombre": user.nombre, "cliente_ref": user.cliente_ref or ""}
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
        "cliente_ref": user.cliente_ref or "",
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

    new_access = create_token({"sub": payload["sub"], "rol": payload["rol"], "nombre": payload.get("nombre", ""), "cliente_ref": payload.get("cliente_ref", "")})
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me")
def me(token=Depends(verify_token)):
    return token
