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

_is_sqlite = "sqlite" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    **({} if _is_sqlite else {"pool_size": 10, "max_overflow": 5, "pool_timeout": 30}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    import models
    # Crear tablas que no existan (primera ejecución)
    Base.metadata.create_all(bind=engine)
    # Ejecutar migraciones Alembic pendientes
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command
        alembic_cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        import logging
        logging.getLogger("bbcfile").warning(f"Alembic upgrade falló (create_all ya creó las tablas): {e}")
    # Safety net: agregar columnas nuevas si Alembic no las creó
    _ensure_columns()
    # Seed data inicial si la DB está vacía
    db = SessionLocal()
    try:
        _seed(db)
    finally:
        db.close()

def _ensure_columns():
    """Agrega columnas nuevas si no existen (safety net para cuando Alembic falla)."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    _missing = []
    def _check(table, column, ddl):
        if not insp.has_table(table):
            return
        cols = [c["name"] for c in insp.get_columns(table)]
        if column not in cols:
            _missing.append((table, column, ddl))
    _check("afiliados", "ciudad", "ALTER TABLE afiliados ADD COLUMN ciudad VARCHAR(100)")
    _check("afiliados", "detalle", "ALTER TABLE afiliados ADD COLUMN detalle TEXT")
    _check("tareas", "privada", "ALTER TABLE tareas ADD COLUMN privada BOOLEAN DEFAULT 0")
    _check("tareas", "completado_en", "ALTER TABLE tareas ADD COLUMN completado_en TIMESTAMP")
    _check("tareas", "finalizado_en", "ALTER TABLE tareas ADD COLUMN finalizado_en TIMESTAMP")
    _check("tareas", "finalizado_por", "ALTER TABLE tareas ADD COLUMN finalizado_por VARCHAR(60)")
    _check("config", "plantilla_whatsapp", "ALTER TABLE config ADD COLUMN plantilla_whatsapp TEXT")
    _check("config", "cargo_adicional", "ALTER TABLE config ADD COLUMN cargo_adicional FLOAT")
    _check("facturas", "afiliado_eliminado", "ALTER TABLE facturas ADD COLUMN afiliado_eliminado BOOLEAN DEFAULT 0")
    if _missing:
        with engine.begin() as conn:
            for table, col, ddl in _missing:
                try:
                    conn.execute(text(ddl))
                except Exception as e:
                    import logging
                    logging.getLogger("bbcfile").warning(f"_ensure_columns: no se pudo agregar {table}.{col}: {e}")


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
        "clientes": [],
    }
    import json
    for nombre, items in default_listas.items():
        if not db.query(models.Lista).filter_by(nombre=nombre).first():
            db.add(models.Lista(nombre=nombre, items=json.dumps(items)))

    db.commit()
