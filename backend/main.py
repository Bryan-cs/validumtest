"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import os, json, math, io
from datetime import datetime, timedelta
from typing import Optional
import jwt
from database import get_db, init_db
from sqlalchemy.orm import Session
import models, schemas, crud

# ─── SLOWAPI RATE LIMITING ────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# ─── EMAIL / SCHEDULER ────────────────────────────────────────────────────────
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler

SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", SMTP_USER)


def send_vencidos_email():
    if not SMTP_USER or not SMTP_PASS:
        return
    from database import SessionLocal
    db = SessionLocal()
    try:
        cobro_rows = crud.get_cobro(db)
        vencidos = [r for r in cobro_rows if r.get('estado') == 'VENCIDO']
        hoy      = [r for r in cobro_rows if r.get('estado') == 'HOY']
        if not vencidos and not hoy:
            return
        html  = "<h2>BBC File — Resumen de cobros</h2>"
        html += f"<p><strong>Cobrar hoy:</strong> {len(hoy)} afiliados</p>"
        html += f"<p><strong>Vencidos:</strong> {len(vencidos)} afiliados</p>"
        if hoy:
            html += "<h3>Cobrar hoy:</h3><ul>"
            for r in hoy[:20]:
                html += f"<li>{r.get('nombre')} — {r.get('empresa')} — ${r.get('planilla',0):,.0f}</li>"
            html += "</ul>"
        if vencidos:
            html += "<h3>Vencidos:</h3><ul>"
            for r in vencidos[:20]:
                html += f"<li>{r.get('nombre')} — {r.get('mes')} {r.get('anio')} — ${r.get('planilla',0):,.0f}</li>"
            html += "</ul>"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"BBC File — {len(hoy)} para cobrar hoy, {len(vencidos)} vencidos"
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_EMAIL
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
    except Exception as e:
        print(f"Error enviando email de notificación: {e}")
    finally:
        db.close()


scheduler = BackgroundScheduler()
scheduler.add_job(send_vencidos_email, 'cron', hour=8, minute=0)

# ─── AUTH CONFIG ──────────────────────────────────────────────────────────────
_default_key = None if os.getenv("RAILWAY_ENVIRONMENT") else "dev-only-key-do-not-use-in-prod"
SECRET_KEY = os.getenv("SECRET_KEY", _default_key)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY env var is required in production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS       = 12
REFRESH_TOKEN_EXPIRE_DAYS = 7


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="BBC File API", version="1.0.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ─── AUTH HELPERS ─────────────────────────────────────────────────────────────
def create_token(data: dict, expires: timedelta = None):
    payload = data.copy()
    if expires is None:
        expires = timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload["exp"] = datetime.utcnow() + expires
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

# ─── INCLUDE ROUTERS ──────────────────────────────────────────────────────────
from routers import auth as auth_router
from routers import afiliados as afiliados_router
from routers import facturas as facturas_router
from routers import reportes as reportes_router

app.include_router(auth_router.router)
app.include_router(afiliados_router.router)
app.include_router(facturas_router.router)
app.include_router(reportes_router.router)

# ─── ELIMINADOS ───────────────────────────────────────────────────────────────
@app.get("/eliminados")
def list_eliminados(db: Session = Depends(get_db), token=Depends(verify_token)):
    rows = db.query(models.Eliminado).order_by(models.Eliminado.id.desc()).all()
    return [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
             "fecha_eliminacion":r.fecha_eliminacion,"mes":r.mes,
             "eliminado_por":r.eliminado_por} for r in rows]


@app.delete("/eliminados/{id}")
def delete_eliminado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "No encontrado")
    nombre = e.nombre
    db.delete(e)
    crud._log(db, token.get("sub","sistema"), "eliminó permanentemente un afiliado", "Afiliados", nombre)
    db.commit()
    return {"ok": True}


@app.post("/eliminados/{id}/restaurar")
def restaurar_eliminado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    import json as _json
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "No encontrado")
    existing = db.query(models.Afiliado).filter_by(doc=e.doc, activo=True).first()
    if existing: raise HTTPException(400, f"Ya existe un afiliado activo con documento {e.doc}")
    datos = _json.loads(e.datos_completos or "{}")
    srvs = datos.get("servicios", [])
    srvs_str = _json.dumps(srvs) if isinstance(srvs, list) else (srvs or "[]")
    a = db.query(models.Afiliado).filter_by(doc=e.doc).first()
    if a:
        a.activo = True; a.estado = "ACTIVO"; a.estado_srv = "ACTIVO"
    else:
        a = models.Afiliado(
            nombre=e.nombre, doc=e.doc, empresa=e.empresa,
            estado="ACTIVO", estado_srv="ACTIVO", activo=True,
            servicios=srvs_str,
            eps=datos.get("eps",""), arl=datos.get("arl",""),
            ccf=datos.get("ccf",""), afp=datos.get("afp",""),
            subtipo=datos.get("subtipo","0"),
            cliente_txt=datos.get("cliente_txt",""),
            cargo=datos.get("cargo",""), tel=datos.get("tel",""),
            email=datos.get("email",""), obs=datos.get("obs",""),
            ibc=datos.get("ibc"), fecha_ingreso=datos.get("fecha_ingreso",""),
            fecha_afiliacion=datos.get("fecha_afiliacion",""),
            registrado_por=token.get("sub","sistema"),
        )
        db.add(a)
    db.delete(e)
    crud._log(db, token.get("sub","sistema"), "restauró un afiliado eliminado", "Afiliados", e.nombre)
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
    return crud.update_config(db, data)


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
          db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_cobro(db, empresa=empresa, cliente=cliente, tipo=tipo)


# ─── ACTIVIDAD ────────────────────────────────────────────────────────────────
@app.get("/actividad")
def actividad(modulo: str = "", usuario: str = "",
              dia: str = "", mes: str = "", anio: str = "",
              db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_actividad(db, modulo=modulo, usuario=usuario, dia=dia, mes=mes, anio=anio)


@app.delete("/actividad")
def clear_actividad(db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.clear_actividad(db, user=token.get("sub", "sistema"))
    return {"ok": True}


# ─── LISTAS DE REFERENCIA ─────────────────────────────────────────────────────
@app.get("/listas")
def get_listas(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_listas(db)


@app.put("/listas/{nombre}")
def update_lista(nombre: str, data: schemas.ListaUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_lista(db, nombre, data.items)


# ─── NOTIFICACIONES ───────────────────────────────────────────────────────────
@app.post("/notificaciones/test")
def test_notificacion(token=Depends(require_admin)):
    """Envía email de notificación de cobros manualmente (para pruebas)."""
    if not SMTP_USER:
        raise HTTPException(400, "SMTP no configurado. Configure SMTP_USER y SMTP_PASS en variables de entorno.")
    import threading
    threading.Thread(target=send_vencidos_email, daemon=True).start()
    return {"ok": True, "message": "Notificación enviada en segundo plano"}


# ─── REPORTES EXCEL (streaming responses, kept in main for backward compat) ───
from fastapi.responses import StreamingResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
