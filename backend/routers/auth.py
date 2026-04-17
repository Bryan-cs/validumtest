"""Router de autenticación."""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import timedelta, datetime, timezone
import jwt, time
from database import get_db
import schemas, crud, models
from .deps import (
    SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS,
    create_token, verify_token, security, is_token_blacklisted,
)
from fastapi.security import HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from logger import logger

_limiter = Limiter(key_func=get_remote_address)


def _blacklist_jti(db: Session, jti: str, expires_at) -> bool:
    """Inserta jti en token_blacklist de forma atómica (race-safe).

    Retorna True si se insertó, False si ya existía (otro request ganó la carrera).
    Usar IntegrityError en lugar de SELECT+INSERT evita el race condition TOCTOU.
    """
    try:
        db.add(models.TokenBlacklist(jti=jti, expires_at=expires_at))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Protección contra fuerza bruta (usando DB para funcionar con múltiples workers) ──
_MAX_ATTEMPTS = 5
_BLOCK_WINDOW = 300  # segundos (5 minutos)

def _get_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # Usar el último IP (el que agrega el proxy/Railway), no el primero (inyectable por cliente)
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        return parts[-1] if parts else (request.client.host if request.client else "unknown")
    return request.client.host if request.client else "unknown"

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

    _generic_error = "Credenciales inválidas"
    user = crud.get_user_by_username(db, data.username)
    if not user or not user.activo:
        _set_attempts(db, ip, rec["count"] + 1, now)
        raise HTTPException(status_code=401, detail=_generic_error)
    if not user.password or not crud.verify_password(data.password, user.password):
        _set_attempts(db, ip, rec["count"] + 1, now)
        logger.warning(f"Login fallido para '{data.username}' desde IP {ip} (intento {rec['count']+1})")
        raise HTTPException(status_code=401, detail=_generic_error)
    # Login exitoso — limpiar intentos fallidos y registros expirados
    _clear_attempts(db, ip)
    db.query(models.TokenBlacklist).filter(
        models.TokenBlacklist.expires_at < datetime.now(timezone.utc)
    ).delete()
    db.query(models.LoginAttempt).filter(
        models.LoginAttempt.last_attempt < now - _BLOCK_WINDOW
    ).delete()
    db.commit()

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
@_limiter.limit("10/minute")
def refresh_token(request: Request, body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    """Obtiene nuevos tokens usando el refresh token (con rotation obligatoria)."""
    ip = _get_ip(request)
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token no es de tipo refresh")
    except jwt.ExpiredSignatureError:
        logger.info(f"token_refresh_expired: ip={ip}")
        raise HTTPException(status_code=401, detail="Refresh token expirado")
    except jwt.InvalidTokenError:
        logger.warning(f"token_refresh_invalid: ip={ip}")
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    jti = payload.get("jti")
    sub = payload.get("sub", "")

    # Verificar que el refresh token no esté en la blacklist (logout o rotation anterior)
    if is_token_blacklisted(jti):
        logger.warning(f"token_refresh_blacklisted: usuario={sub} ip={ip} jti={str(jti)[:8]}...")
        raise HTTPException(status_code=401, detail="Token invalidado — inicia sesión nuevamente")

    # Verificar que el usuario siga activo
    user = crud.get_user_by_username(db, sub)
    if not user or not user.activo:
        logger.warning(f"token_refresh_inactive_user: usuario={sub} ip={ip}")
        raise HTTPException(status_code=401, detail="Usuario desactivado o eliminado")

    # Rotation: invalidar el refresh token usado antes de emitir uno nuevo.
    # _blacklist_jti usa INSERT directo + captura IntegrityError — atómico y race-safe.
    if jti:
        expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
        _blacklist_jti(db, jti, expires_at)

    claims = {"sub": user.username, "rol": user.rol, "nombre": user.nombre, "cliente_ref": user.cliente_ref or ""}
    new_access = create_token(claims)
    new_refresh = create_token(
        {**claims, "type": "refresh"},
        expires=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    logger.info(f"token_refresh_ok: usuario={sub} ip={ip}")
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout")
def logout(request: Request, body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    """Invalida el refresh token — impide renovar el access token tras cerrar sesión."""
    ip = _get_ip(request)
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        sub = payload.get("sub", "desconocido")
        if jti:
            expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
            _blacklist_jti(db, jti, expires_at)
        logger.info(f"logout_ok: usuario={sub} ip={ip}")
    except Exception as _e:
        logger.warning(f"logout_warn: no se pudo blacklistear token ip={ip}: {_e}")
    return {"ok": True}


@router.get("/me")
def me(token=Depends(verify_token)):
    return token
