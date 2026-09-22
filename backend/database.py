from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
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

# Registrar el listener de aislamiento multi-tenant (do_orm_execute).
# Import con efecto secundario: define el ContextVar y engancha el filtro automático por organización.
import tenant  # noqa: E402,F401

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
        _sembrar_catalogos_pila(db)
    finally:
        db.close()


def _sembrar_catalogos_pila(db):
    """Siembra los códigos normativos de PILA si el catálogo está vacío o quedó viejo.

    Solo escribe cuando hace falta: compara contra el total esperado antes de
    tocar nada, para no pagar ~1.350 upserts en cada arranque.
    """
    try:
        import models
        from services.pila import catalogos
        esperados = sum(len(v) for v in catalogos.CATALOGOS.values())
        vigentes = db.query(models.PilaCodigo).filter(models.PilaCodigo.vigente == True).count()  # noqa: E712
        if vigentes != esperados:
            resumen = catalogos.sembrar(db)
            import logging
            logging.getLogger("bbcfile").info(f"catálogos PILA sembrados: {resumen}")
    except Exception as e:
        # Un catálogo sin sembrar no debe impedir que arranque la aplicación:
        # solo deja los selectores de PILA vacíos hasta que se corrija.
        import logging
        logging.getLogger("bbcfile").warning(f"no se pudieron sembrar los catálogos PILA: {e}")

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
    _check("afiliados", "fecha_expedicion", "ALTER TABLE afiliados ADD COLUMN fecha_expedicion VARCHAR(10)")
    _check("afiliados", "actividad_economica", "ALTER TABLE afiliados ADD COLUMN actividad_economica VARCHAR(7)")
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
    _check("seguimiento_arl", "entidad_arl", "ALTER TABLE seguimiento_arl ADD COLUMN entidad_arl VARCHAR(20) DEFAULT 'SURA'")
    _check("seguimiento_arl", "tipo_afiliado", "ALTER TABLE seguimiento_arl ADD COLUMN tipo_afiliado VARCHAR(15) DEFAULT 'dependiente'")
    _check("usuarios", "ver_detalle", "ALTER TABLE usuarios ADD COLUMN ver_detalle BOOLEAN DEFAULT FALSE")
    _check("credenciales_portales", "clave_api", "ALTER TABLE credenciales_portales ADD COLUMN clave_api TEXT")

    # Columnas PILA de afiliados (ver migración u5v6w7x8y9z0). Van en bucle y no
    # como 24 _check sueltos porque entran todas juntas y con el mismo motivo.
    # BOOLEAN DEFAULT FALSE y no DEFAULT 0: Postgres rechaza el 0 en un boolean.
    for _col, _tipo in [
        ("primer_apellido", "VARCHAR(20)"), ("segundo_apellido", "VARCHAR(30)"),
        ("primer_nombre", "VARCHAR(20)"), ("segundo_nombre", "VARCHAR(30)"),
        ("fecha_nacimiento", "VARCHAR(10)"), ("sexo", "VARCHAR(1)"),
        ("tipo_cotizante", "VARCHAR(2)"), ("subtipo_cotizante", "VARCHAR(2)"),
        ("extranjero_no_pension", "BOOLEAN DEFAULT FALSE"),
        ("colombiano_exterior", "BOOLEAN DEFAULT FALSE"),
        ("cod_depto_labor", "VARCHAR(2)"), ("cod_municipio_labor", "VARCHAR(3)"),
        ("cod_eps", "VARCHAR(6)"), ("cod_afp", "VARCHAR(6)"),
        ("cod_ccf", "VARCHAR(6)"), ("cod_arl", "VARCHAR(6)"),
        ("clase_riesgo", "VARCHAR(1)"), ("tarifa_arl", "NUMERIC(7,5)"),
        ("tipo_salario", "VARCHAR(1)"), ("salario_basico", "NUMERIC(15,2)"),
        ("centro_trabajo", "VARCHAR(9)"),
        ("cotizante_principal_tipo_doc", "VARCHAR(2)"),
        ("cotizante_principal_doc", "VARCHAR(16)"),
        ("horas_laboradas", "INTEGER"),
    ]:
        _check("afiliados", _col, f"ALTER TABLE afiliados ADD COLUMN {_col} {_tipo}")

    # La planilla PILA es por afiliado (ver migración w7x8y9z0a1b2).
    _check("planillas_liquidacion", "afiliado_id",
           "ALTER TABLE planillas_liquidacion ADD COLUMN afiliado_id INTEGER")
    _check("planillas_liquidacion", "afiliado_doc",
           "ALTER TABLE planillas_liquidacion ADD COLUMN afiliado_doc VARCHAR(20)")
    _check("planillas_liquidacion", "afiliado_nombre",
           "ALTER TABLE planillas_liquidacion ADD COLUMN afiliado_nombre VARCHAR(150)")

    ver_detalle_recien_agregada = any(t == "usuarios" and c == "ver_detalle" for t, c, _ in _missing)

    if _missing:
        with engine.begin() as conn:
            for table, col, ddl in _missing:
                try:
                    conn.execute(text(ddl))
                except Exception as e:
                    import logging
                    logging.getLogger("bbcfile").warning(f"_ensure_columns: no se pudo agregar {table}.{col}: {e}")

    # Al crear la columna por primera vez, habilitar "ver_detalle" para el usuario
    # de portal solicitado (una sola vez; luego el admin lo gestiona desde Usuarios).
    if ver_detalle_recien_agregada:
        try:
            with engine.begin() as conn:
                conn.execute(text("UPDATE usuarios SET ver_detalle = TRUE WHERE username = '79360051'"))
        except Exception as e:
            import logging
            logging.getLogger("bbcfile").warning(f"No se pudo habilitar ver_detalle inicial: {e}")
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
        # mensaje era VARCHAR(300); notas del admin en novedades de pago lo desbordan
        ("postgresql", "ALTER TABLE notificaciones ALTER COLUMN mensaje TYPE TEXT"),
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


def _default_porcentajes():
    return {"EPS":0.04,"AFP":0.16,"CCF":0.04,
            "ARL 1":0.00522,"ARL 2":0.01044,"ARL 3":0.02436,
            "ARL 4":0.04350,"ARL 5":0.06960}


def _default_listas():
    """Listas de referencia base que recibe cada organización nueva."""
    return {
        "empresas": [],
        "eps": ["Sin EPS","Sura EPS","Compensar","Sanitas","Nueva EPS","Coomeva",
                "Salud Total","Cafesalud","Famisanar","Coosalud","Medimas","Emssanar"],
        "arl": ["N/A","1","2","3","4","5"],
        "ccf": ["N/A","Compensar","Colsubsidio","Cafam","Comfandi","Comfamiliar Huila",
                "Combarranquilla","Comfenalco Antioquia","Comfenalco Valle"],
        "afp": ["N/A","Porvenir","Colpensiones","Colfondos","Skandia"],
        "bancos": [],
        "subtipos": ["0","3","4","20","22"],
        "estados_srv": ["ACTIVO","SUSPENDIDO","DOBLE AFILIACION","EN ESPERA DE ACTIVACION",
                        "RETIRADO","EN MORA","NO AFILIADO","PENDIENTE"],
        "motivos_retiro": ["Renuncia","Despido","Pension","Otro"],
        "clientes": [],
    }


def provision_organizacion(db, nombre, slug, admin_username, admin_password, admin_nombre=None):
    """Crea una organización nueva con su Config, sus Listas base y su usuario admin inicial.
    Todo queda scopeado al organizacion_id recién creado. Devuelve la Organizacion.
    Usado por el router de superadmin y por el seed inicial de dev.
    """
    import models, json
    from crud import hash_password

    org = models.Organizacion(nombre=nombre, slug=slug, activo=True)
    db.add(org)
    db.flush()   # obtener org.id sin cerrar la transacción

    db.add(models.Config(
        organizacion_id=org.id,
        ibc_global=1_750_905,
        porcentajes=json.dumps(_default_porcentajes()),
    ))
    for lst_nombre, items in _default_listas().items():
        db.add(models.Lista(organizacion_id=org.id, nombre=lst_nombre, items=json.dumps(items)))

    db.add(models.Usuario(
        nombre=admin_nombre or f"Administrador {nombre}",
        username=admin_username,
        rol="admin",
        organizacion_id=org.id,
        activo=True,
        password=hash_password(admin_password),
    ))
    db.commit()
    db.refresh(org)
    return org


def _seed(db):
    """Seed mínimo: solo el superadmin del SaaS. Las organizaciones se crean desde el panel
    de superadmin (o vía provision_organizacion). Ya NO se siembran admin/empleado/Config/Listas
    globales — todo eso vive dentro de cada organización."""
    import models

    if db.query(models.Usuario).filter_by(rol="superadmin").count() == 0:
        from crud import hash_password
        su_user = os.getenv("SUPERADMIN_USER", "superadmin")
        su_pass = os.getenv("SUPERADMIN_PASS")
        if not su_pass:
            if _is_sqlite:
                su_pass = "superadmin1234"   # solo dev/SQLite
            else:
                import logging
                logging.getLogger("bbcfile").warning(
                    "SUPERADMIN_PASS no definido en producción — no se crea el superadmin inicial")
                return
        db.add(models.Usuario(
            nombre="Super Administrador",
            username=su_user,
            rol="superadmin",
            organizacion_id=None,
            activo=True,
            password=hash_password(su_pass),
        ))
        db.commit()
