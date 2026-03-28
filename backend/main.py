"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
APP_VERSION = "1.2.0"
from dotenv import load_dotenv
load_dotenv()  # carga .env si existe; no sobreescribe vars del entorno del sistema

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
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
    """Exporta todas las tablas como JSON y lo sube a Cloudflare R2."""
    from logger import logger as _log
    import json
    try:
        from routers.documentos import _get_s3, _R2_BUCKET
        s3 = _get_s3()
        if not s3:
            _log.warning("Backup: R2 no disponible, saltando backup")
            return
        from database import SessionLocal
        from sqlalchemy import inspect, text
        db = SessionLocal()
        try:
            inspector = inspect(db.bind)
            tables = inspector.get_table_names()
            backup_data = {}
            for table in tables:
                if table in ('alembic_version',):
                    continue
                rows = db.execute(text(f'SELECT * FROM "{table}"')).fetchall()
                keys = db.execute(text(f'SELECT * FROM "{table}" LIMIT 0')).keys()
                col_names = list(keys)
                backup_data[table] = {
                    "columns": col_names,
                    "rows": [
                        {col: (str(val) if val is not None and not isinstance(val, (int, float, bool)) else val)
                         for col, val in zip(col_names, row)}
                        for row in rows
                    ],
                    "count": len(rows),
                }
            dump = json.dumps(backup_data, ensure_ascii=False, indent=1).encode("utf-8")
        finally:
            db.close()
        # Nombre: backups/2026-03-28_14-00.json
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        key = f"backups/{ts}.json"
        s3.put_object(Bucket=_R2_BUCKET, Key=key, Body=dump)
        size_mb = len(dump) / (1024 * 1024)
        _log.info(f"Backup: {key} ({size_mb:.1f} MB) subido a R2")
        # Limpiar backups con más de 30 días
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            resp = s3.list_objects_v2(Bucket=_R2_BUCKET, Prefix="backups/")
            for obj in resp.get("Contents", []):
                if obj["LastModified"].replace(tzinfo=timezone.utc) < cutoff:
                    s3.delete_object(Bucket=_R2_BUCKET, Key=obj["Key"])
                    _log.info(f"Backup: eliminado backup antiguo {obj['Key']}")
        except Exception as e:
            _log.warning(f"Backup: error limpiando backups antiguos: {e}")
    except Exception as e:
        _log.error(f"Backup: error general: {e}")


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
            # Backups DB → R2: 2 AM, 12 PM, 9 PM hora Colombia (UTC-5 = 7, 17, 2 UTC)
            _scheduler.add_job(_backup_db_to_r2, "cron", hour=7, minute=0, id="backup_2am")
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
    from logger import logger as _cors_log
    _cors_log.warning("⚠️  SEGURIDAD: ALLOWED_ORIGINS no configurado — CORS permite cualquier origen en producción")

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

app.include_router(auth_router.router)
app.include_router(afiliados_router.router)
app.include_router(facturas_router.router)
app.include_router(reportes_router.router)
app.include_router(tareas_router.router)
app.include_router(portal_router.router)
app.include_router(documentos_router)

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
    db.delete(e)
    crud._log(db, token.get("sub","sistema"), "eliminó permanentemente un afiliado", "Afiliados", nombre)
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
def list_retiros(anio: str = "", mes: str = "",
                 db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_retiros(db, anio=anio, mes=mes)


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


@app.patch("/empleados/{id}/nomina")
def update_nomina(id: int, data: schemas.NominaUpdate,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_nomina(db, id, data.nomina)
    if not result: raise HTTPException(404, "Empleado no encontrado")
    return result


@app.delete("/empleados/{id}")
def delete_empleado(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "Empleado no encontrado")
    crud.delete_empleado(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


# ─── GASTOS ───────────────────────────────────────────────────────────────────
@app.get("/gastos")
def list_gastos(db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_gastos(db)


@app.post("/gastos", status_code=201)
def create_gasto(data: schemas.GastoCreate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_gasto(db, data)


@app.patch("/gastos/{id}/toggle")
def toggle_gasto(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.toggle_gasto(db, id)
    if not result: raise HTTPException(404, "Gasto no encontrado")
    return result


@app.delete("/gastos/{id}")
def delete_gasto(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.delete_gasto(db, id, user=token.get("sub","sistema"))
    return {"ok": True}


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
def dashboard_meses(db: Session = Depends(get_db), token=Depends(verify_token)):
    """Retorna ingresos de los últimos 6 meses para la gráfica."""
    return crud.get_dashboard_meses(db)


# ─── MÓDULO DE COBRO ──────────────────────────────────────────────────────────
@app.get("/cobro")
def cobro(empresa: str = "", cliente: str = "", tipo: str = "",
          mes: str = "", anio: str = "", doc: str = "",
          db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_cobro(db, empresa=empresa, cliente=cliente, tipo=tipo,
                          mes=mes, anio=anio, doc=doc)


# ─── PLANILLAS DE PAGO SS (admin) ─────────────────────────────────────────────

@app.get("/planillas")
def listar_planillas(cliente: str = "", mes: str = "", anio: str = "",
                     db: Session = Depends(get_db), token=Depends(require_admin)):
    q = db.query(models.PlanillaPago).order_by(models.PlanillaPago.id.desc())
    if cliente: q = q.filter(models.PlanillaPago.cliente_ref == cliente)
    if mes:     q = q.filter(models.PlanillaPago.mes == mes)
    if anio:    q = q.filter(models.PlanillaPago.anio == anio)
    rows = q.all()
    result = []
    for p in rows:
        docs = db.query(models.Documento).filter_by(contexto="planilla_pago", contexto_id=p.id).all()
        result.append({
            "id": p.id, "cliente_ref": p.cliente_ref, "mes": p.mes, "anio": p.anio,
            "observaciones": p.observaciones, "subido_por": p.subido_por,
            "creado": p.creado.isoformat() if p.creado else None,
            "archivos": [{"id": d.id, "nombre": d.nombre, "tamano": d.tamano} for d in docs],
        })
    return result


@app.post("/planillas")
async def crear_planilla(
    cliente_ref: str = Form(...),
    mes: str = Form(...),
    anio: str = Form(...),
    observaciones: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    token=Depends(require_admin),
):
    planilla = models.PlanillaPago(
        cliente_ref=cliente_ref, mes=mes, anio=anio,
        observaciones=observaciones, subido_por=token.get("sub", ""),
    )
    db.add(planilla)
    db.commit()
    db.refresh(planilla)

    # Subir archivos usando el sistema de documentos existente
    from routers.documentos import _get_s3, _R2_BUCKET, ALLOWED_EXT, MAX_SIZE
    import uuid, os, re
    s3 = _get_s3()
    subidos = []
    for file in files:
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        if ext not in ALLOWED_EXT:
            continue
        content = await file.read()
        if len(content) > MAX_SIZE:
            continue
        safe_name = re.sub(r'[^\w.\-]', '_', file.filename or 'archivo')
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        if s3:
            key = f"planillas/{unique_name}"
            s3.put_object(Bucket=_R2_BUCKET, Key=key, Body=content, ContentType=file.content_type or "application/octet-stream")
            ruta = key
        else:
            os.makedirs("uploads/planillas", exist_ok=True)
            ruta = f"uploads/planillas/{unique_name}"
            with open(ruta, "wb") as f:
                f.write(content)
        doc = models.Documento(
            afiliado_doc="", nombre=file.filename, tipo=ext, ruta=ruta,
            tamano=len(content), subido_por=token.get("sub", ""),
            contexto="planilla_pago", contexto_id=planilla.id,
        )
        db.add(doc)
        subidos.append(file.filename)
    db.commit()
    crud.log(db, token.get("sub", ""), "Subió planilla SS", "Facturación",
             f"{cliente_ref} - {mes} {anio} ({len(subidos)} archivos)")
    return {"ok": True, "id": planilla.id, "archivos": subidos}


@app.delete("/planillas/{planilla_id}")
def eliminar_planilla(planilla_id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    planilla = db.query(models.PlanillaPago).filter_by(id=planilla_id).first()
    if not planilla:
        raise HTTPException(404, "Planilla no encontrada")
    # Eliminar archivos asociados
    docs = db.query(models.Documento).filter_by(contexto="planilla_pago", contexto_id=planilla.id).all()
    from routers.documentos import _get_s3, _R2_BUCKET
    s3 = _get_s3()
    for d in docs:
        if s3 and not d.ruta.startswith("uploads/"):
            try: s3.delete_object(Bucket=_R2_BUCKET, Key=d.ruta)
            except Exception: pass
        db.delete(d)
    cliente = planilla.cliente_ref
    mes_anio = f"{planilla.mes} {planilla.anio}"
    db.delete(planilla)
    db.commit()
    crud.log(db, token.get("sub", ""), "Eliminó planilla SS", "Facturación", f"{cliente} - {mes_anio}")
    return {"ok": True}


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
    result = {"status": status, "version": APP_VERSION, "db": "ok" if db_ok else "error"}
    if redis_ok is not None:
        result["redis"] = "ok" if redis_ok else "error"
    result["storage"] = "r2" if storage_ok else "local"
    if storage_err:
        result["_storage_err"] = storage_err
    if _start_time:
        uptime = (datetime.now(timezone.utc) - _start_time).total_seconds()
        result["uptime_seconds"] = int(uptime)
    if code != 200:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=code, content=result)
    return result


# ─── BACKUPS (solo admin) ─────────────────────────────────────────────────────
@app.get("/backups")
def listar_backups(token=Depends(require_admin)):
    """Lista los backups disponibles en R2."""
    try:
        from routers.documentos import _get_s3, _R2_BUCKET
        s3 = _get_s3()
        if not s3:
            raise HTTPException(503, "R2 no disponible")
        resp = s3.list_objects_v2(Bucket=_R2_BUCKET, Prefix="backups/")
        backups = []
        for obj in sorted(resp.get("Contents", []), key=lambda o: o["LastModified"], reverse=True):
            backups.append({
                "archivo": obj["Key"].replace("backups/", ""),
                "fecha": obj["LastModified"].isoformat(),
                "tamano_mb": round(obj["Size"] / (1024 * 1024), 2),
            })
        return {"total": len(backups), "backups": backups}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error listando backups: {e}")


@app.get("/backups/{nombre}/descargar")
def descargar_backup(nombre: str, token=Depends(require_admin)):
    """Descarga un backup específico desde R2."""
    import io
    from fastapi.responses import StreamingResponse
    if "/" in nombre or "\\" in nombre:
        raise HTTPException(400, "Nombre inválido")
    try:
        from routers.documentos import _get_s3, _R2_BUCKET
        s3 = _get_s3()
        if not s3:
            raise HTTPException(503, "R2 no disponible")
        key = f"backups/{nombre}"
        resp = s3.get_object(Bucket=_R2_BUCKET, Key=key)
        content = resp["Body"].read()
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/json" if nombre.endswith(".json") else "application/sql",
            headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
        )
    except s3.exceptions.NoSuchKey:
        raise HTTPException(404, "Backup no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error descargando backup: {e}")


@app.post("/backups/crear")
def crear_backup_manual(token=Depends(require_admin)):
    """Crea un backup manual inmediato."""
    _backup_db_to_r2()
    # Verificar que se creó
    try:
        from routers.documentos import _get_s3, _R2_BUCKET
        s3 = _get_s3()
        if s3:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
            key = f"backups/{ts}.json"
            s3.head_object(Bucket=_R2_BUCKET, Key=key)
            return {"ok": True, "archivo": f"{ts}.json"}
    except Exception:
        pass
    return {"ok": True, "mensaje": "Backup ejecutado, revisa la lista de backups"}


@app.post("/backups/restaurar")
async def restaurar_backup(
    file: UploadFile = File(...),
    token=Depends(require_admin),
):
    """Restaura la base de datos desde un archivo JSON de backup."""
    import json
    from database import SessionLocal
    from sqlalchemy import text, inspect

    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Solo se aceptan archivos .json")

    content = await file.read()
    try:
        backup_data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(400, "Archivo JSON inválido")

    if not isinstance(backup_data, dict):
        raise HTTPException(400, "Formato de backup no reconocido")

    db = SessionLocal()
    restored = []
    errors = []
    try:
        inspector = inspect(db.bind)
        existing_tables = set(inspector.get_table_names())

        # Primero crear backup de seguridad antes de restaurar
        _backup_db_to_r2()

        # Desactivar foreign keys temporalmente para poder truncar en cualquier orden
        db.execute(text("SET session_replication_role = 'replica'"))

        for table_name, table_data in backup_data.items():
            if table_name not in existing_tables:
                errors.append(f"Tabla '{table_name}' no existe, saltada")
                continue
            rows = table_data.get("rows", [])
            columns = table_data.get("columns", [])
            if not rows or not columns:
                continue
            try:
                # Limpiar tabla
                db.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
                # Insertar filas
                count = 0
                for row in rows:
                    cols = ", ".join(f'"{c}"' for c in columns)
                    placeholders = ", ".join(f":v{i}" for i in range(len(columns)))
                    params = {f"v{i}": row.get(c) for i, c in enumerate(columns)}
                    db.execute(text(f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders})'), params)
                    count += 1
                restored.append({"tabla": table_name, "filas": count})
            except Exception as e:
                errors.append(f"Error en '{table_name}': {str(e)[:200]}")
                db.rollback()
                db.execute(text("SET session_replication_role = 'replica'"))
                continue

        # Reactivar foreign keys
        db.execute(text("SET session_replication_role = 'origin'"))

        # Limpiar duplicados: si un doc existe en afiliados Y en eliminados, quitarlo de eliminados
        db.execute(text("""
            DELETE FROM eliminados
            WHERE doc IN (SELECT doc FROM afiliados)
        """))

        db.commit()
    except Exception as e:
        db.rollback()
        try:
            db.execute(text("SET session_replication_role = 'origin'"))
            db.commit()
        except Exception:
            pass
        raise HTTPException(500, f"Error restaurando: {e}")
    finally:
        db.close()

    return {
        "ok": True,
        "restaurado": restored,
        "errores": errors,
        "mensaje": "Se creó un backup de seguridad antes de restaurar",
    }


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
