"""
Script de datos de prueba — ejercita TODAS las funcionalidades nuevas.
Ejecutar: python seed_test.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
import models, crud, schemas

init_db()
db = SessionLocal()

# ── Limpiar afiliados de prueba anteriores ─────────────────────────────────
TEST_DOCS = ["11111111", "22222222", "33333333", "44444444", "55555555"]
for doc in TEST_DOCS:
    a = db.query(models.Afiliado).filter_by(doc=doc).first()
    if a:
        db.delete(a)
db.commit()

# ── 5 afiliados de prueba ──────────────────────────────────────────────────
afiliados = [
    {
        # 1 — Prueba ARL nivel 3, ciudad, detalle, todos los servicios
        "nombre": "CARLOS ANDRES MARTINEZ Lopez",
        "tipo_doc": "CC", "doc": "11111111",
        "empresa": "PROSECOOP", "cargo": "TÉCNICO",
        "cliente_txt": "CLIENTE DEMO",
        "eps": "Sura EPS", "arl": "3", "ccf": "Compensar", "afp": "Porvenir",
        "subtipo": "0", "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "servicios": ["EPS", "AFP", "CCF", "ARL 3"],
        "tel": "3001234567", "email": "carlos@demo.com",
        "dir": "CRA 15 # 80-25", "ciudad": "BOGOTÁ",
        "obs": "Afiliado de prueba 1", "novedades": "INCAPACIDAD PENDIENTE",
        "detalle": "Revisar estado de salud antes de renovar contrato",
        "ibc": 2500000, "fecha_ingreso": "2025-01-15",
        "fecha_afiliacion": "2025-01-15", "registrado_por": "admin",
    },
    {
        # 2 — ARL N/A, IBC global, sin novedades — prueba cobro mes siguiente
        "nombre": "DIANA PATRICIA RIOS CASTILLO",
        "tipo_doc": "CC", "doc": "22222222",
        "empresa": "CARSECOOP", "cargo": "AUXILIAR CONTABLE",
        "cliente_txt": "CLIENTE DEMO",
        "eps": "Nueva EPS", "arl": "N/A", "ccf": "Colsubsidio", "afp": "Colpensiones",
        "subtipo": "3", "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "servicios": ["EPS", "AFP", "CCF"],
        "tel": "3109876543", "email": "diana@demo.com",
        "dir": "CL 45 # 12-10 APTO 301", "ciudad": "MEDELLÍN",
        "obs": "", "novedades": "",
        "detalle": "",
        "ibc": None,  # usa IBC global
        "fecha_ingreso": "2026-03-01",
        "fecha_afiliacion": "2026-03-01",  # afiliada hoy → cobro empieza Abril
        "registrado_por": "admin",
    },
    {
        # 3 — ARL nivel 5, múltiples novedades, IBC alto — prueba modo oscuro
        "nombre": "JOHN FREDY GONZALEZ MUÑOZ",
        "tipo_doc": "CE", "doc": "33333333",
        "empresa": "TECHNOVA", "cargo": "INGENIERO SENIOR",
        "cliente_txt": "CLIENTE DEMO",
        "eps": "Compensar", "arl": "5", "ccf": "Cafam", "afp": "Colfondos",
        "subtipo": "4", "estado": "ACTIVO", "estado_srv": "DOBLE AFILIACION",
        "servicios": ["EPS", "AFP", "CCF", "ARL 5"],
        "tel": "3201112233", "email": "john.gonzalez@technova.co",
        "dir": "AV EL DORADO # 68D-35", "ciudad": "BOGOTÁ",
        "obs": "Verificar doble afiliación con empresa anterior",
        "novedades": "DOBLE AFILIACION - EN REVISIÓN",
        "detalle": "Empresa anterior: TechStar SAS — pendiente carta de retiro",
        "ibc": 8000000, "fecha_ingreso": "2024-06-01",
        "fecha_afiliacion": "2024-06-01",
        "registrado_por": "admin",
    },
    {
        # 4 — Solo EPS, subtipo 20, ciudad diferente — prueba fila expandible facturación
        "nombre": "MARIA FERNANDA SALCEDO PINTO",
        "tipo_doc": "CC", "doc": "44444444",
        "empresa": "TECHPLANET", "cargo": "COORDINADORA RRHH",
        "cliente_txt": "CLIENTE DEMO",
        "eps": "Sanitas", "arl": "2", "ccf": "N/A", "afp": "Skandia",
        "subtipo": "20", "estado": "ACTIVO", "estado_srv": "ACTIVO",
        "servicios": ["EPS", "AFP", "ARL 2"],
        "tel": "3154445566", "email": "mfsalcedo@techplanet.net",
        "dir": "CL 100 # 19-61 OF 502", "ciudad": "CALI",
        "obs": "", "novedades": "",
        "detalle": "Coordinadora — autorizada para gestionar solicitudes del equipo",
        "ibc": 4200000, "fecha_ingreso": "2023-11-20",
        "fecha_afiliacion": "2023-11-20",
        "registrado_por": "admin",
    },
    {
        # 5 — SUSPENDIDO, sin ARL, IBC mínimo — prueba filtros y estados
        "nombre": "PEDRO ANTONIO VARGAS HERRERA",
        "tipo_doc": "PA", "doc": "55555555",
        "empresa": "PROSECOOP", "cargo": "OPERARIO",
        "cliente_txt": "CLIENTE DEMO",
        "eps": "Coosalud", "arl": "1", "ccf": "Comfandi", "afp": "Porvenir",
        "subtipo": "22", "estado": "SUSPENDIDO", "estado_srv": "SUSPENDIDO",
        "servicios": ["EPS", "ARL 1"],
        "tel": "3007778899", "email": "",
        "dir": "VDA LAS PALMAS KM 3", "ciudad": "PEREIRA",
        "obs": "Suspendido por falta de pago en Enero 2026",
        "novedades": "SUSPENDIDO",
        "detalle": "",
        "ibc": 1300000, "fecha_ingreso": "2022-08-10",
        "fecha_afiliacion": "2022-08-10",
        "registrado_por": "admin",
    },
]

print("Insertando afiliados de prueba...")
for datos in afiliados:
    schema = schemas.AfiliadoCreate(**datos)
    try:
        resultado = crud.create_afiliado(db, schema)
        print(f"  ✅ {datos['nombre']} (doc: {datos['doc']}, ciudad: {datos['ciudad']}, arl: {datos['arl']})")
    except Exception as e:
        print(f"  ❌ {datos['nombre']}: {e}")

# ── Crear 2 facturas para Carlos (doc 11111111) para probar fila expandible ─
print("\nCreando facturas de prueba para Carlos Martinez...")
for mes, estado, banco in [("Enero", "pagado", "Bancolombia"), ("Febrero", "pendiente", None)]:
    try:
        f = schemas.FacturaCreate(
            nombre_afiliado="CARLOS ANDRES MARTINEZ LOPEZ",
            doc="11111111", cliente="CLIENTE DEMO",
            anio="2026", mes=mes, periodo="30",
            estado=estado, banco=banco,
            ingresos=350000, costos=280000,
            costo_adm=0, conceptos_extra=0, utilidad=70000,
            novedades="PAGO PLANILLA COMPLETA" if estado=="pagado" else "",
            creado_por="admin",
        )
        crud.create_factura(db, f)
        print(f"  ✅ Factura {mes} 2026 — {estado}")
    except Exception as e:
        print(f"  ❌ Factura {mes}: {e}")

# ── Crear tarea privada y una general ──────────────────────────────────────
print("\nCreando tareas de prueba...")
try:
    t1 = schemas.TareaCreate(
        titulo="Verificar doble afiliación de Gonzalez",
        descripcion="Contactar empresa anterior TechStar SAS para carta de retiro",
        asignado_a="admin", creado_por="admin",
        fecha_limite="2026-04-15", privada=False,
    )
    crud.create_tarea(db, t1)
    print("  ✅ Tarea general creada")
except Exception as e:
    print(f"  ❌ Tarea general: {e}")

try:
    t2 = schemas.TareaCreate(
        titulo="Revisar IBC de afiliados PROSECOOP",
        descripcion="Comparar IBC individuales vs global antes de generar planilla Abril",
        asignado_a="admin", creado_por="admin",
        fecha_limite="2026-04-01", privada=True,
    )
    crud.create_tarea(db, t2)
    print("  ✅ Tarea privada creada (solo visible para admin)")
except Exception as e:
    print(f"  ❌ Tarea privada: {e}")

db.close()
print("\n✅ Datos de prueba cargados. Reinicia el backend si ya está corriendo.")
print("\nQué probar:")
print("  1. Afiliados → pestaña Activos: busca 'DEMO', verifica ciudad y ARL radio buttons")
print("  2. Afiliados → editar cualquiera: campo Ciudad visible, ARL en radio buttons")
print("  3. Afiliados → pestaña Documentos: busca Carlos, sube un archivo")
print("  4. Afiliados → pestaña Historial de pagos: busca Carlos, verifica modo oscuro")
print("  5. Facturación → click en fila de Carlos: fila expandible con datos EPS/AFP/ARL/ciudad")
print("  6. Tareas → crea nueva tarea: checkbox 'privada', badge 🔒")
print("  7. Módulo Cobro → Carlos y Diana: Diana (afiliada Marzo) NO debe aparecer en Marzo")
