"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
from dotenv import load_dotenv
load_dotenv()  # carga .env si existe; no sobreescribe vars del entorno del sistema

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from datetime import datetime
from database import get_db, init_db
from sqlalchemy.orm import Session
import models, schemas, crud
from routers.deps import verify_token, require_admin

# ─── SLOWAPI RATE LIMITING ────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)


def _limpiar_notificaciones_diario():
    """Elimina todas las notificaciones del día anterior al iniciar un nuevo día."""
    from database import SessionLocal
    from datetime import date
    db = SessionLocal()
    try:
        hoy = datetime.combine(date.today(), datetime.min.time())
        db.query(models.Notificacion).filter(models.Notificacion.creado < hoy).delete()
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    # Backup automático diario a las 2:00 AM
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from backup import run_backup
        from logger import logger as _log
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(run_backup, "cron", hour=2, minute=0)
        _scheduler.add_job(_limpiar_notificaciones_diario, "cron", hour=0, minute=0)
        _scheduler.start()
    except Exception as e:
        from logger import logger as _log
        _log.error(f"APScheduler no pudo iniciar: {e}")
    yield


app = FastAPI(title="BBC File API", version="1.0.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# En producción: ALLOWED_ORIGINS=https://tu-app.netlify.app
# En desarrollo: dejar vacío → permite cualquier origen
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── INCLUDE ROUTERS ──────────────────────────────────────────────────────────
from routers import auth as auth_router
from routers import afiliados as afiliados_router
from routers import facturas as facturas_router
from routers import reportes as reportes_router
from routers import tareas as tareas_router
from routers import portal as portal_router

app.include_router(auth_router.router)
app.include_router(afiliados_router.router)
app.include_router(facturas_router.router)
app.include_router(reportes_router.router)
app.include_router(tareas_router.router)
app.include_router(portal_router.router)

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
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][datetime.now().month-1]
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


# ─── ACTIVIDAD (solo admin) ───────────────────────────────────────────────────
@app.get("/actividad")
def actividad(modulo: str = "", usuario: str = "",
              desde: str = "", hasta: str = "",
              db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_actividad(db, modulo=modulo, usuario=usuario, desde=desde, hasta=hasta)


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
