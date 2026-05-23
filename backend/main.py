"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
APP_VERSION = "1.2.0"  # Sincronizado con FastAPI(version=...)
from dotenv import load_dotenv
load_dotenv()  # carga .env si existe; no sobreescribe vars del entorno del sistema

# ─── SENTRY ───────────────────────────────────────────────────────────────────
import os as _os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

_sentry_dsn = _os.getenv("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,   # 20% de requests para performance
        send_default_pii=False,   # no enviar datos personales
        environment=_os.getenv("RAILWAY_ENVIRONMENT", "development"),
    )

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone
from database import get_db, init_db
from sqlalchemy.orm import Session
import models, crud
from routers.deps import verify_token

# ─── SLOWAPI RATE LIMITING ────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)


# ─── PER-USER RATE LIMITING ───────────────────────────────────────────────────
import time as _rl_time
import threading as _rl_threading

_rl_mem: dict = {}
_rl_lock = _rl_threading.Lock()

# (path_prefix, max_requests, window_segundos)
# Orden importa — se usa el primer match
_RL_RULES: list[tuple[str, int, int]] = [
    ("/reportes/",  10,  60),   # Excel/PDF — CPU+DB pesado, 10/min es generoso
    ("/cobro",      20,  60),   # recalcula SS para todos los afiliados
    ("/dashboard",  30,  60),   # queries agregadas con GROUP BY
    ("/afiliados",  60,  60),   # listados paginados
    ("/facturas",   60,  60),
    ("/retiros",    60,  60),
    ("/portal/",    60,  60),   # portal cliente — incluye reportes portal
    ("/",          120,  60),   # catch-all para el resto
]

# Paths que se saltan (auth.py ya los limita por IP; health no tiene datos)
_RL_SKIP = {"/health", "/auth/login", "/auth/refresh", "/auth/logout",
            "/auth/verify-password"}


def _rl_get_rule(path: str) -> tuple[int, int]:
    for prefix, limit, window in _RL_RULES:
        if path.startswith(prefix):
            return limit, window
    return 120, 60


def _rl_get_subject(request) -> str:
    """Extrae 'sub' del JWT (solo tokens válidos y vigentes). Fallback a IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt as _jwt_mod
            from routers.deps import SECRET_KEY, ALGORITHM
            payload = _jwt_mod.decode(
                auth[7:], SECRET_KEY, algorithms=[ALGORITHM],
            )  # token válido y vigente → usar sub
            sub = payload.get("sub")
            if sub:
                return f"u:{sub}"
        except _jwt_mod.ExpiredSignatureError:
            pass  # token expirado → usar IP
        except _jwt_mod.InvalidTokenError:
            pass  # token inválido → usar IP
        except Exception:
            pass
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        ip = parts[-1] if parts else (request.client.host if request.client else "unknown")
    else:
        ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


def _rl_check(subject: str, path: str) -> tuple[int, bool]:
    """Incrementa contador y retorna (count, exceeded). Usa Redis si disponible."""
    limit, window = _rl_get_rule(path)
    key = f"rl:{subject}:{path.split('/')[1]}:{window}"

    try:
        from crud import _redis_client, _redis_disponible
        if _redis_disponible():
            count = _redis_client.incr(key)
            if count == 1:
                _redis_client.expire(key, window)
            return count, count > limit
    except Exception:
        pass

    # Fallback memoria (dev sin Redis)
    now = _rl_time.time()
    with _rl_lock:
        entry = _rl_mem.get(key)
        if entry and (now - entry["ts"]) < window:
            entry["count"] += 1
            return entry["count"], entry["count"] > limit
        _rl_mem[key] = {"count": 1, "ts": now}
        if len(_rl_mem) > 2000:
            # Limpiar expirados si el dict crece mucho
            expired = [k for k, v in list(_rl_mem.items()) if now - v["ts"] >= window]
            for k in expired:
                _rl_mem.pop(k, None)
        return 1, False


from scheduler_jobs import (
    limpiar_token_blacklist       as _limpiar_token_blacklist,
    limpiar_notificaciones_diario as _limpiar_notificaciones_diario,
    limpiar_actividad_antigua     as _limpiar_actividad_antigua,
    limpiar_tareas_mensuales      as _limpiar_tareas_mensuales,
    limpiar_novedades_antiguas    as _limpiar_novedades_antiguas,
    limpiar_planillas_antiguas    as _limpiar_planillas_antiguas,
    limpiar_login_attempts        as _limpiar_login_attempts,
)


_start_time = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = datetime.now(timezone.utc)
    init_db()
    # Advertencia si las credenciales por defecto no han sido cambiadas
    try:
        from database import SessionLocal
        _db = SessionLocal()
        _admin = _db.query(models.Usuario).filter_by(username="admin").first()
        if _admin and crud.verify_password("admin1234", _admin.password or ""):
            from logger import logger as _log
            _log.warning("⚠️  SEGURIDAD: El usuario 'admin' tiene la contraseña por defecto 'admin1234'. Cámbiela inmediatamente.")
        _db.close()
    except Exception:
        pass
    # Tareas programadas de limpieza — solo iniciar si ENABLE_SCHEDULER=true
    # En Railway configurar esa variable en el servicio principal únicamente
    _should_schedule = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
    if _should_schedule:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            _scheduler = BackgroundScheduler()
            _scheduler.add_job(_limpiar_token_blacklist, "cron", hour=1, minute=0)
            _scheduler.add_job(_limpiar_notificaciones_diario, "cron", hour=0, minute=0)
            _scheduler.add_job(_limpiar_actividad_antigua, "cron", hour=3, minute=0)
            _scheduler.add_job(_limpiar_login_attempts, "cron", hour=2, minute=0)
            _scheduler.add_job(_limpiar_tareas_mensuales,   "cron", day=1, hour=4, minute=0)
            _scheduler.add_job(_limpiar_novedades_antiguas, "cron", day=1, hour=5, minute=0)
            _scheduler.add_job(_limpiar_planillas_antiguas, "cron", day=1, hour=6, minute=0)
            _scheduler.start()
        except Exception as e:
            from logger import logger as _log
            _log.error(f"APScheduler no pudo iniciar: {e}")
    yield


_is_prod = os.getenv("DATABASE_URL", "").startswith("postgresql")
app = FastAPI(
    title="BBC File API",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# En producción: ALLOWED_ORIGINS=https://tu-app.vercel.app
# En desarrollo: dejar vacío → usa localhost:5173 y localhost:3000
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
if not _allowed_origins:
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError(
            "SEGURIDAD: ALLOWED_ORIGINS no está configurado. "
            "Define la variable de entorno con los orígenes permitidos (ej: https://tu-app.vercel.app)."
        )
    # Dev: orígenes locales (allow_credentials=True requiere orígenes explícitos, no '*')
    _allowed_origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── HEADERS DE SEGURIDAD ────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        return response

class PerUserRateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting por usuario autenticado (sub del JWT) o por IP si no hay token.
    Límites distintos según el costo de cada categoría de endpoint.
    Usa Redis en producción; dict en memoria como fallback en dev.
    """
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in _RL_SKIP or request.method == "OPTIONS":
            return await call_next(request)

        subject = _rl_get_subject(request)
        count, exceeded = _rl_check(subject, path)

        if exceeded:
            limit, window = _rl_get_rule(path)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": f"Demasiadas peticiones. Límite: {limit}/min."},
                headers={"Retry-After": str(window)},
            )
        return await call_next(request)


app.add_middleware(PerUserRateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ─── REQUEST LOGGING ──────────────────────────────────────────────────────────
import time as _time
from logger import logger as _req_logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = _time.monotonic()
        response = await call_next(request)
        ms = int((_time.monotonic() - start) * 1000)
        # Omitir health check para no saturar los logs
        if request.url.path != "/health":
            _req_logger.info(
                f"{request.method} {request.url.path} "
                f"→ {response.status_code} ({ms}ms)"
            )
        return response

app.add_middleware(RequestLoggingMiddleware)

# ─── INCLUDE ROUTERS ──────────────────────────────────────────────────────────
from routers import auth as auth_router
from routers import afiliados as afiliados_router
from routers import facturas as facturas_router
from routers import reportes as reportes_router
from routers import tareas as tareas_router
from routers import portal as portal_router
from routers.documentos import router as documentos_router
from routers import planillas as planillas_router
from routers import seguimiento_arl as seguimiento_arl_router
from routers import eliminados as eliminados_router
from routers import retiros as retiros_router
from routers import empleados as empleados_router
from routers import nomina as nomina_router
from routers import gastos as gastos_router
from routers import usuarios as usuarios_router
from routers import config as config_router
from routers import dashboard as dashboard_router
from routers import cobro as cobro_router
from routers import actividad as actividad_router

app.include_router(auth_router.router)
app.include_router(afiliados_router.router)
app.include_router(facturas_router.router)
app.include_router(reportes_router.router)
app.include_router(tareas_router.router)
app.include_router(portal_router.router)
app.include_router(documentos_router)
app.include_router(planillas_router.router)
app.include_router(seguimiento_arl_router.router)
app.include_router(eliminados_router.router)
app.include_router(retiros_router.router)
app.include_router(empleados_router.router)
app.include_router(nomina_router.router)
app.include_router(gastos_router.router)
app.include_router(usuarios_router.router)
app.include_router(config_router.router)
app.include_router(dashboard_router.router)
app.include_router(cobro_router.router)
app.include_router(actividad_router.router)


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Railway usa este endpoint para monitorear el estado del servicio."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "degraded"})
    return {"status": "ok"}


@app.get("/health/detail")
def health_detail(db: Session = Depends(get_db), token=Depends(verify_token)):
    """Diagnóstico interno — requiere autenticación."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = None
    try:
        from crud import _redis_client
        if _redis_client:
            redis_ok = _redis_client.ping()
    except Exception:
        redis_ok = False
    storage_ok = None
    storage_err = None
    try:
        from routers.documentos import _get_s3, _R2_BUCKET, _s3_error
        s3 = _get_s3()
        if s3:
            s3.head_bucket(Bucket=_R2_BUCKET)
            storage_ok = True
        else:
            storage_ok = False
            storage_err = _s3_error or "storage_unavailable"
    except Exception as ex:
        storage_ok = False
        storage_err = str(ex)
    result = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "error"}
    if redis_ok is not None:
        result["redis"] = "ok" if redis_ok else "error"
    result["storage"] = "r2" if storage_ok else "local"
    if storage_err:
        result["storage_error"] = True
    if _start_time:
        uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
        result["uptime_seconds"] = int(uptime)
    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=result)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
