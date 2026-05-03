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

# Pool por proceso distribuido según número de workers.
# Target: ≤ 15 conexiones totales (Railway PostgreSQL: 25 max, margen para Railway Cron + admin).
# 1 worker → pool=5 + overflow=10 = 15.  2 workers → pool=2 + overflow=5 = 7/worker = 14.
_workers = int(os.getenv("WEB_CONCURRENCY", "1"))
_max_per_worker = max(5, 15 // max(1, _workers))
_pool_size      = max(2, _max_per_worker // 3)
_max_overflow   = _max_per_worker - _pool_size

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    **({} if _is_sqlite else {
        "pool_size":    _pool_size,
        "max_overflow": _max_overflow,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    }),
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
    # Crear tablas que no existan — checkfirst=True es idempotente y seguro con múltiples workers.
    # NO se llama alembic upgrade head aquí: en startup multi-worker Alembic crea sus propias
    # conexiones fuera de cualquier advisory lock, provocando deadlocks entre workers.
    # Las columnas nuevas las cubre _ensure_columns().
    Base.metadata.create_all(bind=engine, checkfirst=True)
    # Safety net: agregar columnas nuevas si create_all no las creó
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
    _check("facturas", "monto_pagado", "ALTER TABLE facturas ADD COLUMN monto_pagado NUMERIC(15,2) DEFAULT 0")
    _check("gastos", "mes",  "ALTER TABLE gastos ADD COLUMN mes INTEGER")
    _check("gastos", "anio", "ALTER TABLE gastos ADD COLUMN anio INTEGER")
    _check("config", "mes_inicio_cobro",  "ALTER TABLE config ADD COLUMN mes_inicio_cobro INTEGER")
    _check("config", "anio_inicio_cobro", "ALTER TABLE config ADD COLUMN anio_inicio_cobro INTEGER")
    if _missing:
        with engine.begin() as conn:
            for table, col, ddl in _missing:
                try:
                    conn.execute(text(ddl))
                except Exception as e:
                    import logging
                    logging.getLogger("bbcfile").warning(f"_ensure_columns: no se pudo agregar {table}.{col}: {e}")
    # Ampliar columnas que quedaron cortas
    _ensure_column_types()
    # Crear índices nuevos si no existen
    _ensure_indexes()


def _ensure_column_types():
    """Amplía columnas cuyo VARCHAR quedó corto para los datos actuales."""
    from sqlalchemy import text
    alterations = [
        # subtipo era VARCHAR(10), necesita VARCHAR(50) para valores como 'SIN CONSULTAR'
        ("postgresql", "ALTER TABLE afiliados ALTER COLUMN subtipo TYPE VARCHAR(50)"),
        ("sqlite",     "SELECT 1"),  # SQLite ignora el límite de VARCHAR, no necesita migración
    ]
    with engine.begin() as conn:
        dialect = engine.dialect.name
        for db_type, ddl in alterations:
            if dialect == db_type:
                try:
                    conn.execute(text(ddl))
                except Exception:
                    pass  # ya tiene el tamaño correcto o no aplica


def _ensure_indexes():
    """Crea índices definidos en models.py que no existan aún en la DB."""
    from sqlalchemy import text
    indexes = [
        ("ix_retiro_anio_mes", "retiros", "anio, mes"),
        ("ix_actividad_usuario_modulo", "actividad", "usuario, modulo"),
        ("ix_actividad_fecha", "actividad", "fecha"),
        ("ix_documento_contexto_id", "documentos", "contexto, contexto_id"),
        ("ix_eliminados_doc", "eliminados", "doc"),
        ("ix_facturas_banco", "facturas", "banco"),
        ("ix_solicitudes_novedad_estado", "solicitudes_novedad", "estado"),
        ("ix_novedades_pago_estado", "novedades_pago", "estado"),
        ("ix_solicitudes_retiro_estado", "solicitudes_retiro", "estado"),
        ("ix_tareas_creado_por", "tareas", "creado_por"),
        ("ix_notificaciones_leida", "notificaciones", "leida"),
        # Compuestos para consultas pesadas
        ("ix_factura_doc_mes_anio", "facturas", "doc, mes, anio"),
        ("ix_afiliado_cliente_activo", "afiliados", "cliente_txt, activo"),
        ("ix_planilla_cliente_mes", "planillas_pago", "cliente_ref, mes, anio"),
        ("ix_gastos_mes_anio",        "gastos",         "mes, anio"),
        ("ix_nomina_mensual_emp_mes", "nomina_mensual",  "empleado_id, mes, anio"),
        # Dashboard: filtra (estado, anio, mes) — evita Seq Scan en facturas
        ("ix_factura_estado_periodo", "facturas",        "estado, anio, mes"),
        ("ix_token_blacklist_expires_at", "token_blacklist", "expires_at"),
    ]
    with engine.begin() as conn:
        for idx_name, table, cols in indexes:
            try:
                conn.execute(text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ({cols})'))
            except Exception:
                pass  # índice ya existe o DB no soporta IF NOT EXISTS
        # Índices parciales (solo PostgreSQL soporta WHERE en índice)
        if engine.dialect.name == "postgresql":
            partial_indexes = [
                ("ix_afiliado_cobro_cobertura",
                 "afiliados", "activo, estado_srv, empresa, cliente_txt", "activo = TRUE"),
                ("ix_factura_pendiente",
                 "facturas", "anio, mes, cliente", "estado = 'pendiente'"),
                ("ix_actividad_fecha_desc",
                 "actividad", "fecha DESC", None),
            ]
            for idx_name, table, cols, where in partial_indexes:
                where_clause = f" WHERE {where}" if where else ""
                try:
                    conn.execute(text(
                        f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ({cols}){where_clause}'
                    ))
                except Exception:
                    pass


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
                "ARL 4":0.04350,"ARL 5":0.06960}
        db.add(models.Config(
            ibc_global=1_750_905,
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
        "bancos": [
            "Nequi / Daviplata - 3170296773",
            "Davivienda (Ahorros) - 0550108900642357",
            "Banco de Bogotá (Ahorros) - 462547688",
            "Llave Banco Bogotá - @BBJMF23103",
            "Bancolombia (Ahorros) - 91270274485",
        ],
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
