"""Router de autenticación."""
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import timedelta, datetime, timezone
import jwt, time, os, hashlib
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

def _is_prod() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("ENVIRONMENT") == "production")

def _set_refresh_cookie(response: Response, token: str, remember: bool = True) -> None:
    prod = _is_prod()
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600 if remember else None,
        path="/auth",
        samesite="none" if prod else "lax",
        secure=prod,
    )

def _delete_refresh_cookie(response: Response) -> None:
    prod = _is_prod()
    response.delete_cookie(
        key="refresh_token",
        path="/auth",
        samesite="none" if prod else "lax",
        secure=prod,
    )

_limiter = Limiter(key_func=get_remote_address)


def _blacklist_jti(db: Session, jti: str, expires_at) -> bool:
    """Inserta jti en token_blacklist de forma atómica (race-safe).

    Usa ON CONFLICT DO NOTHING para evitar error logs en PostgreSQL cuando
    requests concurrentes intentan blacklistear el mismo token simultáneamente.
    Retorna True si se insertó, False si ya existía.

    synchronous_commit=off: no espera fsync del WAL antes de confirmar.
    El WAL writer persiste igual en ~200ms. Trade-off aceptable: si el server
    crashea en esa ventana, el refresh token revocado podría reutilizarse
    brevemente — el access token (15 min) sigue siendo la barrera real.
    Elimina los spikes de 15s observados en pg_stat_statements.
    """
    from sqlalchemy import text as _text
    try:
        db.execute(_text("SET LOCAL synchronous_commit = off"))
        stmt = pg_insert(models.TokenBlacklist).values(
            jti=jti,
            expires_at=expires_at,
            creado=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["jti"])
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0
    except Exception:
        db.rollback()
        return False

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Protección contra fuerza bruta (usando DB para funcionar con múltiples workers) ──
_MAX_ATTEMPTS       = 5   # por IP
_MAX_ATTEMPTS_COMBO = 20  # por (ip, username) — bloquea NAT/proxy sin afectar otras cuentas
_BLOCK_WINDOW       = 300  # segundos (5 minutos)

def _combo_key(ip: str, username: str) -> str:
    """Key hash para contador (ip, username) — siempre ≤ 45 chars."""
    return "c:" + hashlib.sha1(f"{ip}:{username}".encode()).hexdigest()[:40]

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
def login(request: Request, response: Response, data: schemas.LoginRequest, db: Session = Depends(get_db)):
    ip    = _get_ip(request)
    now   = time.time()
    rec   = _get_attempts(db, ip)
    ckey  = _combo_key(ip, data.username)
    crec  = _get_attempts(db, ckey)

    # Bloqueo por IP (5 intentos)
    if rec["count"] >= _MAX_ATTEMPTS and now - rec["last"] < _BLOCK_WINDOW:
        secs_left = int(_BLOCK_WINDOW - (now - rec["last"]))
        logger.warning(f"Login bloqueado para IP {ip} — {rec['count']} intentos fallidos")
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {secs_left // 60}m {secs_left % 60}s"
        )
    if rec["count"] >= _MAX_ATTEMPTS and now - rec["last"] >= _BLOCK_WINDOW:
        rec = {"count": 0, "last": 0.0}

    # Bloqueo por (ip, username) — 20 intentos, bloquea NAT/proxy por cuenta específica
    if crec["count"] >= _MAX_ATTEMPTS_COMBO and now - crec["last"] < _BLOCK_WINDOW:
        secs_left = int(_BLOCK_WINDOW - (now - crec["last"]))
        logger.warning(f"Login bloqueado para combo ip={ip} user={data.username} — {crec['count']} intentos")
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Espera {secs_left // 60}m {secs_left % 60}s"
        )
    if crec["count"] >= _MAX_ATTEMPTS_COMBO and now - crec["last"] >= _BLOCK_WINDOW:
        crec = {"count": 0, "last": 0.0}

    _generic_error = "Credenciales inválidas"
    user = crud.get_user_by_username(db, data.username)
    if not user or not user.activo:
        _set_attempts(db, ip, rec["count"] + 1, now)
        _set_attempts(db, ckey, crec["count"] + 1, now)
        raise HTTPException(status_code=401, detail=_generic_error)
    if not user.password or not crud.verify_password(data.password, user.password):
        _set_attempts(db, ip, rec["count"] + 1, now)
        _set_attempts(db, ckey, crec["count"] + 1, now)
        logger.warning(f"Login fallido para '{data.username}' desde IP {ip} (intento ip={rec['count']+1} combo={crec['count']+1})")
        raise HTTPException(status_code=401, detail=_generic_error)
    # Login exitoso — limpiar ambos contadores
    _clear_attempts(db, ip)
    _clear_attempts(db, ckey)
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

    token_data = {"sub": user.username, "rol": user.rol, "nombre": user.nombre,
                  "cliente_ref": user.cliente_ref or "", "ver_detalle": bool(user.ver_detalle)}
    access_token = create_token(token_data)
    rt = create_token(
        {**token_data, "type": "refresh"},
        expires=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    _set_refresh_cookie(response, rt, remember=data.remember_me)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "rol": user.rol,
        "nombre": user.nombre,
        "username": user.username,
        "cliente_ref": user.cliente_ref or "",
        "ver_detalle": bool(user.ver_detalle),
    }


@router.post("/refresh")
@_limiter.limit("10/minute")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """Obtiene nuevos tokens usando el refresh token (con rotation obligatoria).
    El refresh token se lee de la cookie httpOnly — no del body.
    """
    ip = _get_ip(request)
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No hay refresh token")
    try:
        payload = jwt.decode(rt, SECRET_KEY, algorithms=[ALGORITHM])
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

    claims = {"sub": user.username, "rol": user.rol, "nombre": user.nombre,
              "cliente_ref": user.cliente_ref or "", "ver_detalle": bool(user.ver_detalle)}
    new_access = create_token(claims)
    new_refresh = create_token(
        {**claims, "type": "refresh"},
        expires=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    _set_refresh_cookie(response, new_refresh)
    logger.info(f"token_refresh_ok: usuario={sub} ip={ip}")
    return {"access_token": new_access, "token_type": "bearer"}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Invalida el refresh token y el access token activo.
    RT: leído de cookie httpOnly.
    AT: leído del header Authorization — blacklisteado si presente y válido.
    """
    ip = _get_ip(request)
    sub = "desconocido"

    # Blacklistear refresh token
    rt = request.cookies.get("refresh_token")
    if rt:
        try:
            payload = jwt.decode(rt, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            sub = payload.get("sub", sub)
            if jti:
                expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
                _blacklist_jti(db, jti, expires_at)
        except Exception as _e:
            logger.warning(f"logout_warn: RT no blacklisteado ip={ip}: {_e}")

    # Blacklistear access token (si viene en Authorization header)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        at = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(at, SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            if jti:
                expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
                _blacklist_jti(db, jti, expires_at)
                sub = payload.get("sub", sub)
        except Exception:
            pass  # AT expirado o inválido — no importa, igual se va a logout

    logger.info(f"logout_ok: usuario={sub} ip={ip}")
    _delete_refresh_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(token=Depends(verify_token)):
    return token


@router.post("/verify-password")
def verify_password_endpoint(
    data: dict,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    """Verifica contraseña del usuario autenticado sin registrar intentos fallidos.
    Usado por modales internos (ej. finalizar-lote en Tareas) para no bloquear la IP."""
    password = data.get("password", "")
    username = token.get("sub", "")
    u = crud.get_user_by_username(db, username)
    if not u or not crud.verify_password(password, u.password):
        raise HTTPException(401, "Contraseña incorrecta")
    return {"ok": True}
