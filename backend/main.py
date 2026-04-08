"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
APP_VERSION = "1.2.0"
from dotenv import load_dotenv
load_dotenv()  # carga .env si existe; no sobreescribe vars del entorno del sistema

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
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


def _limpiar_notificaciones_diario():
    """Elimina todas las notificaciones del día anterior al iniciar un nuevo día."""
    from database import SessionLocal
    from logger import logger as _log
    db = SessionLocal()
    try:
        hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = db.query(models.Notificacion).filter(models.Notificacion.creado < hoy).delete()
        db.commit()
        if count: _log.info(f"Limpieza: {count} notificaciones antiguas eliminadas")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza notificaciones: {e}")
    finally:
        db.close()


def _limpiar_actividad_antigua():
    """Elimina registros de actividad con más de 90 días."""
    from database import SessionLocal
    from datetime import timedelta
    from logger import logger as _log
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=90)
        count = db.query(models.Actividad).filter(models.Actividad.fecha < limite).delete()
        db.commit()
        if count: _log.info(f"Limpieza: {count} registros de actividad antiguos eliminados")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza actividad: {e}")
    finally:
        db.close()


def _limpiar_novedades_antiguas():
    """Elimina novedades/solicitudes de portal con más de 30 días y sus documentos."""
    from database import SessionLocal
    from datetime import timedelta
    from logger import logger as _log
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=30)
        total = 0
        for Model, ctx in [
            (models.NovedadPago, ['novedad_pago', 'resp_pago']),
            (models.SolicitudRetiro, ['novedad_retiro', 'resp_retiro']),
            (models.SolicitudNovedad, ['novedad_afil', 'resp_afil']),
        ]:
            viejos = db.query(Model).filter(Model.creado < limite).all()
            for item in viejos:
                from routers.documentos import _delete_file
                docs = db.query(models.Documento).filter(
                    models.Documento.contexto.in_(ctx),
                    models.Documento.contexto_id == item.id,
                ).all()
                for d in docs:
                    _delete_file(d.ruta)
                    db.delete(d)
                db.delete(item)
                total += 1
        db.commit()
        if total: _log.info(f"Limpieza: {total} novedades/solicitudes antiguas eliminadas (+docs)")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza novedades: {e}")
    finally:
        db.close()


def _backup_db_to_r2():
    """Wrapper para compatibilidad con scheduler."""
    from routers.backups import backup_db_to_r2
    backup_db_to_r2()


def _limpiar_tareas_mensuales():
    """Elimina tareas finalizadas con más de 30 días para liberar espacio."""
    from database import SessionLocal
    from datetime import timedelta
    from logger import logger as _log
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=30)
        count = db.query(models.Tarea).filter(
            models.Tarea.estado == "finalizada",
            models.Tarea.finalizado_en < limite,
        ).delete()
        db.commit()
        if count: _log.info(f"Limpieza: {count} tareas finalizadas antiguas eliminadas")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza tareas: {e}")
    finally:
        db.close()


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
    # Tareas programadas de limpieza — solo iniciar en un worker
    # Usa un lock en DB para evitar que múltiples workers ejecuten el scheduler
    _should_schedule = True
    if not _is_sqlite:
        try:
            from database import SessionLocal
            from sqlalchemy import text
            _sdb = SessionLocal()
            # Intentar advisory lock de PostgreSQL (no bloqueante)
            _got_lock = _sdb.execute(text("SELECT pg_try_advisory_lock(1)")).scalar()
            _sdb.close()
            _should_schedule = bool(_got_lock)
        except Exception:
            _should_schedule = True  # si falla, dejar que corra
    if _should_schedule:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            _scheduler = BackgroundScheduler()
            _scheduler.add_job(_limpiar_notificaciones_diario, "cron", hour=0, minute=0)
            _scheduler.add_job(_limpiar_actividad_antigua, "cron", hour=3, minute=0)
            _scheduler.add_job(_limpiar_tareas_mensuales, "cron", day=1, hour=4, minute=0)
            _scheduler.add_job(_limpiar_novedades_antiguas, "cron", day=1, hour=5, minute=0)
            # Backups DB → R2: 5 PM, 12 PM, 9 PM hora Colombia (UTC-5 = 22, 17, 2 UTC)
            _scheduler.add_job(_backup_db_to_r2, "cron", hour=22, minute=0, id="backup_5pm")
            _scheduler.add_job(_backup_db_to_r2, "cron", hour=17, minute=0, id="backup_12pm")
            _scheduler.add_job(_backup_db_to_r2, "cron", hour=2, minute=0, id="backup_9pm")
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
    allow_methods=["*"],
    allow_headers=["*"],
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
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ─── INCLUDE ROUTERS ──────────────────────────────────────────────────────────
from routers import auth as auth_router
from routers import afiliados as afiliados_router
from routers import facturas as facturas_router
from routers import reportes as reportes_router
from routers import tareas as tareas_router
from routers import portal as portal_router
from routers.documentos import router as documentos_router
from routers import backups as backups_router
from routers import planillas as planillas_router

app.include_router(auth_router.router)
app.include_router(afiliados_router.router)
app.include_router(facturas_router.router)
app.include_router(reportes_router.router)
app.include_router(tareas_router.router)
app.include_router(portal_router.router)
app.include_router(documentos_router)
app.include_router(backups_router.router)
app.include_router(planillas_router.router)


# ─── ELIMINADOS ───────────────────────────────────────────────────────────────
@app.get("/eliminados")
def list_eliminados(db: Session = Depends(get_db), token=Depends(require_admin)):
    rows = db.query(models.Eliminado).order_by(models.Eliminado.id.desc()).all()
    return [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
             "fecha_eliminacion":r.fecha_eliminacion,"mes":r.mes,
             "eliminado_por":r.eliminado_por} for r in rows]


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
        a.obs = datos.get("obs", "")
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
            email=datos.get("email",""), obs=datos.get("obs",""),
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


@app.get("/dashboard/meses")
def dashboard_meses(anio: str = "", db: Session = Depends(get_db), token=Depends(verify_token)):
    """Retorna los 12 meses del año indicado con ingresos, facturas y pendiente."""
    return crud.get_dashboard_meses(db, anio=anio)


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
    # Check Redis
    redis_ok = None
    try:
        from crud import _redis_client
        if _redis_client:
            redis_ok = _redis_client.ping()
    except Exception:
        redis_ok = False
    # Check R2 storage
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
    status = "ok" if db_ok else "degraded"
    code = 200 if db_ok else 503
    result = {"status": status, "db": "ok" if db_ok else "error"}
    if redis_ok is not None:
        result["redis"] = "ok" if redis_ok else "error"
    result["storage"] = "r2" if storage_ok else "local"
    if _start_time:
        uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
        result["uptime_seconds"] = int(uptime)
    if code != 200:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=code, content=result)
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
