"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
APP_VERSION = "1.2.0"
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

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone
from database import get_db, init_db, _is_sqlite
from sqlalchemy.orm import Session
import models, schemas, crud
from models import COL_TZ
from routers.deps import verify_token, require_admin

# ─── SLOWAPI RATE LIMITING ────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)


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


app = FastAPI(title="BBC File API", version="1.0.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# En producción: ALLOWED_ORIGINS=https://tu-app.vercel.app
# En desarrollo: dejar vacío → permite cualquier origen
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]
if _allowed_origins == ["*"] and (os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("ENVIRONMENT") == "production"):
    raise RuntimeError(
        "SEGURIDAD: ALLOWED_ORIGINS no está configurado. "
        "Define la variable de entorno con los orígenes permitidos (ej: https://tu-app.vercel.app)."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
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

app.include_router(auth_router.router)
app.include_router(afiliados_router.router)
app.include_router(facturas_router.router)
app.include_router(reportes_router.router)
app.include_router(tareas_router.router)
app.include_router(portal_router.router)
app.include_router(documentos_router)
app.include_router(planillas_router.router)
app.include_router(seguimiento_arl_router.router)


# ─── ELIMINADOS ───────────────────────────────────────────────────────────────
@app.get("/eliminados")
def list_eliminados(db: Session = Depends(get_db), token=Depends(require_admin)):
    rows = db.query(models.Eliminado).order_by(models.Eliminado.id.desc()).all()
    return [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
             "fecha_eliminacion":r.fecha_eliminacion,"mes":r.mes,
             "eliminado_por":r.eliminado_por} for r in rows]


@app.get("/eliminados/{id}/preview")
def preview_eliminado(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    """Retorna cuántos registros serán borrados junto con el eliminado."""
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e:
        raise HTTPException(404, "No encontrado")
    n_facturas    = db.query(models.Factura).filter_by(doc=e.doc).count()
    n_documentos  = db.query(models.Documento).filter_by(afiliado_doc=e.doc).count()
    n_solicitudes = (
        db.query(models.SolicitudNovedad).filter_by(afiliado_doc=e.doc).count() +
        db.query(models.SolicitudRetiro).filter_by(afiliado_doc=e.doc).count()
    )
    return {
        "nombre": e.nombre,
        "doc": e.doc,
        "facturas": n_facturas,
        "documentos": n_documentos,
        "solicitudes": n_solicitudes,
    }


@app.delete("/eliminados/{id}")
def delete_eliminado(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "No encontrado")
    nombre = e.nombre
    doc = e.doc
    # Borrar cualquier registro del afiliado (activo o no)
    db.query(models.Afiliado).filter_by(doc=doc).delete()
    # Borrar facturas del afiliado
    db.query(models.Factura).filter_by(doc=doc).delete()
    # Borrar documentos del afiliado
    db.query(models.Documento).filter_by(afiliado_doc=doc).delete()
    # Borrar solicitudes de novedad y retiro del portal
    db.query(models.SolicitudNovedad).filter_by(afiliado_doc=doc).delete()
    db.query(models.SolicitudRetiro).filter_by(afiliado_doc=doc).delete()
    # Borrar el registro de eliminado
    db.delete(e)
    crud._log(db, token.get("sub","sistema"), "eliminó permanentemente un afiliado y todos sus registros", "Afiliados", nombre)
    db.commit()
    return {"ok": True}


@app.post("/eliminados/{id}/restaurar")
def restaurar_eliminado(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    import json as _json
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "No encontrado")
    existing = db.query(models.Afiliado).filter_by(doc=e.doc, activo=True).first()
    if existing: raise HTTPException(400, f"Ya existe un afiliado activo con documento {e.doc}")

    # Validar integridad del snapshot JSON
    try:
        datos = _json.loads(e.datos_completos or "{}")
        if not datos or not datos.get("nombre") or not datos.get("doc"):
            raise ValueError("Datos incompletos")
    except (ValueError, _json.JSONDecodeError):
        raise HTTPException(400, "Los datos del afiliado eliminado están corruptos y no se puede restaurar")

    srvs = datos.get("servicios", [])
    srvs_str = _json.dumps(srvs) if isinstance(srvs, list) else (srvs or "[]")
    registrado_original = datos.get("registrado_por", token.get("sub", "sistema"))

    # Buscar afiliado inactivo con mismo doc
    a = db.query(models.Afiliado).filter_by(doc=e.doc).first()
    if a:
        # Restaurar todos los campos desde el snapshot, no solo activo/estado
        a.activo = True
        a.estado = "ACTIVO"
        a.estado_srv = "ACTIVO"
        a.nombre = datos.get("nombre", a.nombre)
        a.empresa = datos.get("empresa", a.empresa)
        a.servicios = srvs_str
        a.eps = datos.get("eps", "")
        a.arl = datos.get("arl", "")
        a.ccf = datos.get("ccf", "")
        a.afp = datos.get("afp", "")
        a.subtipo = datos.get("subtipo", "0")
        a.cliente_txt = datos.get("cliente_txt", "")
        a.cargo = datos.get("cargo", "")
        a.tel = datos.get("tel", "")
        a.email = datos.get("email", "")
        a.novedades = datos.get("novedades", "")
        a.ibc = datos.get("ibc")
        a.fecha_ingreso = datos.get("fecha_ingreso", "")
        a.fecha_afiliacion = datos.get("fecha_afiliacion", "")
        a.registrado_por = registrado_original
    else:
        a = models.Afiliado(
            nombre=datos.get("nombre", e.nombre), doc=e.doc,
            empresa=datos.get("empresa", e.empresa),
            estado="ACTIVO", estado_srv="ACTIVO", activo=True,
            servicios=srvs_str,
            eps=datos.get("eps",""), arl=datos.get("arl",""),
            ccf=datos.get("ccf",""), afp=datos.get("afp",""),
            subtipo=datos.get("subtipo","0"),
            cliente_txt=datos.get("cliente_txt",""),
            cargo=datos.get("cargo",""), tel=datos.get("tel",""),
            email=datos.get("email",""),
            novedades=datos.get("novedades",""),
            ibc=datos.get("ibc"), fecha_ingreso=datos.get("fecha_ingreso",""),
            fecha_afiliacion=datos.get("fecha_afiliacion",""),
            registrado_por=registrado_original,
        )
        db.add(a)

    # Reactivar facturas que fueron marcadas como huérfanas
    db.query(models.Factura).filter_by(doc=e.doc, afiliado_eliminado=True).update(
        {"afiliado_eliminado": False})

    db.delete(e)
    crud._log(db, token.get("sub","sistema"), "restauró un afiliado eliminado", "Afiliados", e.nombre)
    crud.cache_invalidar("cobro:")
    crud.cache_invalidar("afiliados:")
    crud.cache_invalidar("dashboard:")
    db.commit()
    return {"ok": True, "nombre": e.nombre}


# ─── RETIROS ──────────────────────────────────────────────────────────────────
@app.get("/retiros")
def list_retiros(anio: str = "", mes: str = "", doc: str = "",
                 skip: int = 0, limit: int = 500,
                 db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_retiros(db, anio=anio, mes=mes, doc=doc, skip=skip, limit=limit)


@app.post("/retiros", status_code=201)
def create_retiro(data: schemas.RetiroCreate,
                  db: Session = Depends(get_db), token=Depends(verify_token)):
    afil = crud.get_afiliado_by_doc(db, data.doc)
    if not afil: raise HTTPException(404, "Afiliado no encontrado")
    mes_actual = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][datetime.now(COL_TZ).month-1]
    pendientes = crud.get_facturas_pendientes_by_doc(db, data.doc, mes=mes_actual)
    data.registrado_por = token.get("sub","sistema")
    retiro = crud.create_retiro(db, data)
    return {"retiro": retiro, "facturas_pendientes": len(pendientes),
            "codigos_pendientes": [f.codigo for f in pendientes]}


@app.delete("/retiros/{id}")
def delete_retiro(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    crud.delete_retiro(db, id, user=token.get("sub","sistema"))
    return {"ok": True}


@app.post("/eliminados/{id}/a-retiros", status_code=201)
def eliminado_a_retiros(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.eliminado_a_retiro(db, id, user=token.get("sub","sistema"))


# ─── EMPLEADOS ────────────────────────────────────────────────────────────────
@app.get("/empleados")
def list_empleados(db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_empleados(db)


@app.post("/empleados", status_code=201)
def create_empleado(data: schemas.EmpleadoCreate,
                    db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_empleado(db, data)


@app.put("/empleados/{id}")
def update_empleado(id: int, data: schemas.EmpleadoCreate,
                    db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_empleado(db, id, data)
    if not result: raise HTTPException(404, "Empleado no encontrado")
    return result


@app.delete("/empleados/{id}")
def delete_empleado(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "Empleado no encontrado")
    crud.delete_empleado(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


# ─── GASTOS MENSUALES ─────────────────────────────────────────────────────────
@app.get("/gastos")
def list_gastos(mes: int, anio: int,
                db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_gastos(db, mes=mes, anio=anio)


@app.post("/gastos", status_code=201)
def create_gasto(data: schemas.GastoCreate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_gasto(db, data)


@app.post("/gastos/copiar")
def copiar_gastos(data: schemas.CopiarMesRequest,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.copiar_gastos_mes_anterior(
        db, data.mes_origen, data.anio_origen, data.mes_destino, data.anio_destino,
        user=token.get("sub", "sistema"))


@app.put("/gastos/{id}")
def update_gasto(id: int, data: schemas.GastoUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_gasto(db, id, data)
    if not result: raise HTTPException(404, "Gasto no encontrado")
    return result


@app.delete("/gastos/{id}")
def delete_gasto(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.delete_gasto(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


# ─── INGRESOS ADICIONALES ────────────────────────────────────────────────────

@app.get("/ingresos-adicionales")
def list_ingresos_adicionales(mes: int = None, anio: int = None,
                               db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_ingresos_adicionales(db, mes=mes, anio=anio)


@app.post("/ingresos-adicionales", status_code=201)
def create_ingreso_adicional(data: schemas.IngresoAdicionalCreate,
                              db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_ingreso_adicional(db, data, user=token.get("sub", "sistema"))


@app.put("/ingresos-adicionales/{id}")
def update_ingreso_adicional(id: int, data: schemas.IngresoAdicionalCreate,
                              db: Session = Depends(get_db), token=Depends(require_admin)):
    i = db.query(models.IngresoAdicional).filter_by(id=id).first()
    if not i: raise HTTPException(404, "Ingreso adicional no encontrado")
    from crud import cache_invalidar
    cache_invalidar("dashboard:")
    i.concepto = data.concepto; i.descripcion = data.descripcion
    i.valor = data.valor; i.mes = data.mes; i.anio = data.anio
    db.commit(); db.refresh(i)
    return {"id": i.id, "concepto": i.concepto, "descripcion": i.descripcion,
            "valor": i.valor, "mes": i.mes, "anio": i.anio, "creado_por": i.creado_por,
            "creado": i.creado.isoformat() if i.creado else None}


@app.delete("/ingresos-adicionales/{id}")
def delete_ingreso_adicional(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    ok = crud.delete_ingreso_adicional(db, id, user=token.get("sub", "sistema"))
    if not ok: raise HTTPException(404, "Ingreso adicional no encontrado")
    return {"ok": True}


# ─── NÓMINA MENSUAL ───────────────────────────────────────────────────────────
@app.get("/nomina")
def get_nomina(mes: int, anio: int,
               db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_nomina_mensual(db, mes=mes, anio=anio)


@app.post("/nomina/copiar")
def copiar_nomina(data: schemas.CopiarMesRequest,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.copiar_nomina_mes_anterior(
        db, data.mes_origen, data.anio_origen, data.mes_destino, data.anio_destino,
        user=token.get("sub", "sistema"))


@app.put("/nomina/{empleado_id}")
def update_nomina_mensual(empleado_id: int, mes: int, anio: int,
                          data: schemas.NominaItemUpdate,
                          db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.upsert_nomina_mensual(db, empleado_id, mes, anio, data.valor,
                                      user=token.get("sub", "sistema"))


# ─── USUARIOS ─────────────────────────────────────────────────────────────────
@app.get("/usuarios")
def list_usuarios(db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_usuarios(db)


@app.post("/usuarios", status_code=201)
def create_usuario(data: schemas.UsuarioCreate,
                   db: Session = Depends(get_db), token=Depends(require_admin)):
    existing = crud.get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(400, f"El usuario '{data.username}' ya existe")
    return crud.create_usuario(db, data)


@app.put("/usuarios/{id}/password")
def change_usuario_password(id: int, data: schemas.UsuarioPasswordUpdate,
                            db: Session = Depends(get_db), token=Depends(require_admin)):
    u = crud.update_usuario_password(db, id, data.password, user=token.get("sub", "admin"))
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    return {"ok": True}


@app.delete("/usuarios/{id}")
def delete_usuario(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    u = crud.get_usuario(db, id)
    if not u: raise HTTPException(404, "Usuario no encontrado")
    if u.username == "admin":
        raise HTTPException(400, "No puedes eliminar el administrador principal")
    if u.rol == "admin":
        admins_activos = db.query(models.Usuario).filter_by(rol="admin", activo=True).count()
        if admins_activos <= 1:
            raise HTTPException(400, "No puedes eliminar el único admin activo del sistema")
    crud.delete_usuario(db, id, user=token.get("sub","sistema"))
    return {"ok": True}


# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
@app.get("/config")
def get_config(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_config(db)


@app.put("/config")
def update_config(data: schemas.ConfigUpdate,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_config(db, data, user=token.get("sub", "sistema"))


# ─── DASHBOARD ────────────────────────────────────────────────────────────────
@app.get("/dashboard")
def dashboard(anio: str = "", mes: str = "",
              db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_dashboard(db, anio=anio, mes=mes)


# ─── MÓDULO DE COBRO ──────────────────────────────────────────────────────────
@app.get("/cobro")
def cobro(empresa: str = "", cliente: str = "", tipo: str = "",
          mes: str = "", anio: str = "", doc: str = "",
          db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_cobro(db, empresa=empresa, cliente=cliente, tipo=tipo,
                          mes=mes, anio=anio, doc=doc)


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
            storage_err = _s3_error or "s3 client is False/None"
    except Exception as e:
        storage_ok = False
        storage_err = str(e)
    result = {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "error"}
    if redis_ok is not None:
        result["redis"] = "ok" if redis_ok else "error"
    result["storage"] = "r2" if storage_ok else "local"
    if storage_err:
        result["storage_err"] = storage_err
    if _start_time:
        uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
        result["uptime_seconds"] = int(uptime)
    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=result)
    return result


# ─── ACTIVIDAD (solo admin) ───────────────────────────────────────────────────
@app.get("/actividad")
def actividad(modulo: str = "", usuario: str = "",
              desde: str = "", hasta: str = "",
              skip: int = 0, limit: int = 200,
              db: Session = Depends(get_db), token=Depends(require_admin)):
    limit = min(limit, 1000) if limit > 0 else 200
    return crud.get_actividad(db, modulo=modulo, usuario=usuario, desde=desde, hasta=hasta,
                              skip=skip, limit=limit)


@app.delete("/actividad")
def clear_actividad(db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.clear_actividad(db, user=token.get("sub", "sistema"))
    return {"ok": True}


# ─── CLIENTES ÚNICOS ──────────────────────────────────────────────────────────
@app.get("/clientes")
def list_clientes(db: Session = Depends(get_db), token=Depends(verify_token)):
    """Retorna la lista de clientes únicos (cliente_txt) de afiliados activos."""
    rows = (db.query(models.Afiliado.cliente_txt)
              .filter(models.Afiliado.activo == True, models.Afiliado.cliente_txt != None, models.Afiliado.cliente_txt != "")
              .distinct()
              .order_by(models.Afiliado.cliente_txt)
              .all())
    return [r[0] for r in rows]


# ─── LISTAS DE REFERENCIA ─────────────────────────────────────────────────────
@app.get("/listas")
def get_listas(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_listas(db)


@app.put("/listas/{nombre}")
def update_lista(nombre: str, data: schemas.ListaUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_lista(db, nombre, data.items, user=token.get("sub", "sistema"))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
