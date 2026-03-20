"""
BBC File — Backend FastAPI
Ejecutar: uvicorn main:app --reload
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import os, json, math
from datetime import datetime, timedelta
from typing import Optional
import jwt
from database import get_db, init_db
from sqlalchemy.orm import Session
import models, schemas, crud

_default_key = None if os.getenv("RAILWAY_ENVIRONMENT") else "dev-only-key-do-not-use-in-prod"
SECRET_KEY = os.getenv("SECRET_KEY", _default_key)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY env var is required in production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 12

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="BBC File API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ─── AUTH ─────────────────────────────────────────────────────────────────────
def create_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def require_admin(token=Depends(verify_token)):
    if token.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol administrador")
    return token

@app.post("/auth/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, data.username)
    if not user or not user.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    if not user.password or not crud.verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    # Migrar passwords en texto plano a bcrypt
    if user.password and not user.password.startswith("$2"):
        user.password = crud.hash_password(data.password)
        db.commit()
    token = create_token({"sub": user.username, "rol": user.rol, "nombre": user.nombre})
    return {"access_token": token, "token_type": "bearer",
            "rol": user.rol, "nombre": user.nombre, "username": user.username}

@app.get("/auth/me")
def me(token=Depends(verify_token)):
    return token

# ─── AFILIADOS ────────────────────────────────────────────────────────────────
@app.get("/afiliados")
def list_afiliados(
    q: str = "", estado: str = "", empresa: str = "",
    cliente: str = "", subtipo: str = "",
    skip: int = 0, limit: int = 0,
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    """Lista afiliados. Con skip/limit activa paginación.
    Sin limit devuelve todos (usado por exportaciones Excel).
    Respuesta: {"total": N, "items": [...]}
    """
    return crud.get_afiliados(db, q=q, estado=estado, empresa=empresa,
                               cliente=cliente, subtipo=subtipo,
                               skip=skip, limit=limit)

@app.get("/afiliados/{id}")
def get_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    a = crud.get_afiliado(db, id)
    if not a: raise HTTPException(404, "Afiliado no encontrado")
    return a

@app.post("/afiliados", status_code=201)
def create_afiliado(data: schemas.AfiliadoCreate,
                    db: Session = Depends(get_db), token=Depends(verify_token)):
    # Validar cédula duplicada
    existing = crud.get_afiliado_by_doc(db, data.doc)
    if existing:
        raise HTTPException(400, f"Ya existe un afiliado con documento {data.doc}: {existing.nombre}")
    data.registrado_por = token.get("sub","sistema")
    return crud.create_afiliado(db, data)

@app.put("/afiliados/{id}")
def update_afiliado(id: int, data: schemas.AfiliadoCreate,
                    db: Session = Depends(get_db), token=Depends(verify_token)):
    a = crud.get_afiliado(db, id)
    if not a: raise HTTPException(404, "Afiliado no encontrado")
    # Validar cédula duplicada (excluyendo el mismo)
    existing = crud.get_afiliado_by_doc(db, data.doc)
    if existing and existing.id != id:
        raise HTTPException(400, f"Otro afiliado ya tiene el documento {data.doc}")
    return crud.update_afiliado(db, id, data, editor=token.get("sub","sistema"))

@app.delete("/afiliados/{id}")
def delete_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    a = db.query(models.Afiliado).filter_by(id=id, activo=True).first()
    if not a: raise HTTPException(404, "Afiliado no encontrado")
    pendientes = crud.get_facturas_pendientes_by_doc(db, a.doc)
    crud.delete_afiliado(db, id, deleted_by=token.get("sub","sistema"))
    return {"ok": True, "facturas_pendientes": len(pendientes),
            "codigos": [f.codigo for f in pendientes]}

# ─── FACTURAS ─────────────────────────────────────────────────────────────────
@app.get("/facturas")
def list_facturas(
    anio: str = "", mes: str = "", cliente: str = "",
    estado: str = "", banco: str = "",
    skip: int = 0, limit: int = 0,
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    """Lista facturas con paginación opcional.
    Sin limit devuelve todas. Con limit retorna {"total": N, "items": [...]}
    """
    return crud.get_facturas(db, anio=anio, mes=mes, cliente=cliente,
                              estado=estado, banco=banco,
                              skip=skip, limit=limit)

@app.post("/facturas", status_code=201)
def create_factura(data: schemas.FacturaCreate,
                   db: Session = Depends(get_db), token=Depends(verify_token)):
    data.creado_por = token.get("sub","sistema")
    if not data.anio:
        data.anio = str(datetime.now().year)
    return crud.create_factura(db, data)

@app.put("/facturas/{id}")
def update_factura(id: int, data: schemas.FacturaUpdate,
                   db: Session = Depends(get_db), token=Depends(verify_token)):
    f = crud.get_factura(db, id)
    if not f: raise HTTPException(404, "Factura no encontrada")
    return crud.update_factura(db, id, data, editor=token.get("sub","sistema"))

@app.patch("/facturas/{id}/pagar")
def pagar_factura(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    f = crud.get_factura(db, id)
    if not f: raise HTTPException(404, "Factura no encontrada")
    return crud.pagar_factura(db, id, user=token.get("sub","sistema"))

@app.delete("/facturas/{id}")
def delete_factura(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    if not crud.get_factura(db, id): raise HTTPException(404, "Factura no encontrada")
    crud.delete_factura(db, id, user=token.get("sub","sistema"))
    return {"ok": True}

@app.get("/eliminados")
def list_eliminados(db: Session = Depends(get_db), token=Depends(verify_token)):
    rows = db.query(models.Eliminado).order_by(models.Eliminado.id.desc()).all()
    return [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
             "fecha_eliminacion":r.fecha_eliminacion,"mes":r.mes,
             "eliminado_por":r.eliminado_por} for r in rows]

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
    # Verificar facturas pendientes
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

# ─── CONFIGURACIÓN (IBC y porcentajes) ────────────────────────────────────────
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

# ─── MÓDULO DE COBRO ──────────────────────────────────────────────────────────
@app.get("/cobro")
def cobro(empresa: str = "", cliente: str = "", tipo: str = "",
          db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_cobro(db, empresa=empresa, cliente=cliente, tipo=tipo)

# ─── ACTIVIDAD ────────────────────────────────────────────────────────────────
@app.get("/actividad")
def actividad(modulo: str = "", usuario: str = "",
              db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_actividad(db, modulo=modulo, usuario=usuario)

# ─── LISTAS DE REFERENCIA ─────────────────────────────────────────────────────
@app.get("/listas")
def get_listas(db: Session = Depends(get_db), token=Depends(verify_token)):
    return crud.get_listas(db)

@app.put("/listas/{nombre}")
def update_lista(nombre: str, data: schemas.ListaUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.update_lista(db, nombre, data.items)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
