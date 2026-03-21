from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./bbcfile.db"   # SQLite para desarrollo local, PostgreSQL en Railway
)

# Railway provee postgres:// pero SQLAlchemy necesita postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    import models
    Base.metadata.create_all(bind=engine)
    # Migración: agregar columnas nuevas a tablas existentes
    with engine.connect() as conn:
        try:
            conn.execute(__import__('sqlalchemy').text("ALTER TABLE config ADD COLUMN plantilla_whatsapp TEXT"))
            conn.commit()
        except Exception:
            pass  # Columna ya existe
    # Seed data inicial si la DB está vacía
    from sqlalchemy.orm import Session
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()

def _seed(db):
    import models
    from datetime import datetime

    # Usuarios iniciales
    if db.query(models.Usuario).count() == 0:
        from crud import hash_password
        db.add_all([
            models.Usuario(nombre="Administrador Principal", username="admin",
                           rol="admin", activo=True, password=hash_password("admin1234")),
            models.Usuario(nombre="Empleado 1", username="empleado1",
                           rol="empleado", activo=True, password=hash_password("emp1234")),
        ])

    # Configuración inicial
    if db.query(models.Config).count() == 0:
        import json
        pcts = {"EPS":0.04,"AFP":0.16,"CCF":0.04,
                "ARL 1":0.00522,"ARL 2":0.01044,"ARL 3":0.02436,
                "ARL 4":0.04350,"ARL 5":0.06960,
                "FSP":0.0,"SENA":0.0,"ICBF":0.0}
        db.add(models.Config(
            ibc_global=1_950_905,
            porcentajes=json.dumps(pcts)
        ))

    # Listas de referencia
    default_listas = {
        "empresas": ["PROSECOOP","CARSECOOP","TECHNOVA","TECHPLANET"],
        "eps": ["Sin EPS","Sura EPS","Compensar","Sanitas","Nueva EPS","Coomeva",
                "Salud Total","Cafesalud","Famisanar","Coosalud","Medimas","Emssanar"],
        "arl": ["N/A","1","2","3","4","5"],
        "ccf": ["N/A","Compensar","Colsubsidio","Cafam","Comfandi","Comfamiliar Huila",
                "Combarranquilla","Comfenalco Antioquia","Comfenalco Valle"],
        "afp": ["N/A","Porvenir","Colpensiones","Colfondos","Skandia"],
        "bancos": ["Nequi","DaviPlata","Bancolombia","Banco de Bogotá","Efectivo","Otro"],
        "subtipos": ["0","3","4","20","22"],
        "estados_srv": ["ACTIVO","SUSPENDIDO","DOBLE AFILIACION","EN ESPERA DE ACTIVACION",
                        "RETIRADO","EN MORA","NO AFILIADO","PENDIENTE"],
        "motivos_retiro": ["Renuncia","Despido","Pension","Otro"],
    }
    if db.query(models.Lista).count() == 0:
        import json
        for nombre, items in default_listas.items():
            db.add(models.Lista(nombre=nombre, items=json.dumps(items)))

    db.commit()
