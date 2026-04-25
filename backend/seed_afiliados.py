"""Genera 500 afiliados de prueba en la base de datos."""
import random, json
from datetime import date, timedelta
from database import SessionLocal
import models

# ── Datos de referencia ───────────────────────────────────────────────────────
EMPRESAS = [
    'EMPRESA XYZ', 'NUEVA EMPRESA SAS', 'PROSECOOP',
    'CARSECOOP', 'TECHNOVA PLANET SAS', 'TECH PLANET ESAL COOP',
    'FUNDACION HERENCIA DE GRACIAS',
]
CLIENTES = ['Cliente A', 'Cliente B', 'Cliente C', 'Cliente D', 'Cliente E']
EPS      = ['Sanitas', 'Compensar', 'Sura', 'Nueva EPS']
AFP      = ['Porvenir', 'Colpensiones', 'Colfondos', 'Skandia']
ARL      = ['1', '2', '3', '4']
CCF      = ['Compensar', 'Colsubsidio', 'Cafam', 'Comfandi']
SUBTIPOS = ['0', '3', '4', '20', '22']
SERVICIOS_BASE = [
    ['EPS', 'AFP', 'CCF'],
    ['EPS', 'AFP'],
    ['EPS', 'AFP', 'CCF', 'ARL 1'],
    ['EPS'],
    ['EPS', 'AFP', 'CCF', 'ARL 2'],
]
NOMBRES = [
    'ANDRES', 'CARLOS', 'JUAN', 'PEDRO', 'LUIS', 'JORGE', 'MIGUEL', 'DAVID',
    'SERGIO', 'DANIEL', 'FELIPE', 'OSCAR', 'CAMILO', 'MARIO', 'PABLO',
    'LAURA', 'MARIA', 'ANA', 'PAULA', 'SOFIA', 'DIANA', 'CLAUDIA',
    'JESSICA', 'VALENTINA', 'NATALIA', 'CAROLINA', 'ANDREA', 'MONICA',
    'ALEJANDRA', 'ISABELLA',
]
APELLIDOS = [
    'GARCIA', 'RODRIGUEZ', 'MARTINEZ', 'LOPEZ', 'GONZALEZ', 'PEREZ',
    'SANCHEZ', 'RAMIREZ', 'TORRES', 'FLORES', 'RIVERA', 'GOMEZ',
    'DIAZ', 'REYES', 'MORALES', 'CRUZ', 'ORTIZ', 'GUTIERREZ',
    'VARGAS', 'CASTILLO', 'RAMOS', 'HERRERA', 'MEDINA', 'JIMENEZ',
    'RUIZ', 'ALVAREZ', 'MENDOZA', 'SILVA', 'ROJAS', 'VEGA',
]

def rand_fecha(inicio='2020-01-01', fin='2025-12-31'):
    d0 = date.fromisoformat(inicio)
    d1 = date.fromisoformat(fin)
    return str(d0 + timedelta(days=random.randint(0, (d1 - d0).days)))

def rand_doc():
    return str(random.randint(10_000_000, 1_999_999_999))

# ── Inserción ─────────────────────────────────────────────────────────────────
db = SessionLocal()
existentes = {a.doc for a in db.query(models.Afiliado.doc).all()}
insertados  = 0
intentos    = 0

while insertados < 500 and intentos < 5000:
    intentos += 1
    doc = rand_doc()
    if doc in existentes:
        continue
    existentes.add(doc)

    nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"
    srvs   = random.choice(SERVICIOS_BASE)
    arl    = random.choice(ARL) if any('ARL' in s for s in srvs) else 'N/A'

    a = models.Afiliado(
        nombre         = nombre,
        tipo_doc       = 'CC',
        doc            = doc,
        empresa        = random.choice(EMPRESAS),
        estado         = 'ACTIVO',
        estado_srv     = 'ACTIVO',
        activo         = True,
        eps            = random.choice(EPS),
        afp            = random.choice(AFP),
        arl            = arl,
        ccf            = random.choice(CCF),
        subtipo        = random.choice(SUBTIPOS),
        cliente_txt    = random.choice(CLIENTES),
        servicios      = json.dumps(srvs),
        ibc            = random.choice([1_750_905, 2_000_000, 2_500_000, 3_000_000, None]),
        fecha_afiliacion = rand_fecha(),
        fecha_ingreso    = rand_fecha(),
        tel            = f"3{random.randint(100_000_000, 299_999_999)}",
        cargo          = random.choice(['Asesor', 'Coordinador', 'Auxiliar', 'Analista', 'Operario']),
        registrado_por = 'seed',
        novedades      = random.choice(['', '', '', 'Pendiente documentos', 'IBC especial', '']),
    )
    db.add(a)
    insertados += 1

    if insertados % 100 == 0:
        db.commit()
        print(f"  {insertados} afiliados insertados...")

db.commit()
db.close()
print(f"\nListo: {insertados} afiliados de prueba creados.")
