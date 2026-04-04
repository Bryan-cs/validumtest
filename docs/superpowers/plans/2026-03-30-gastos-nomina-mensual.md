# Gastos y Nómina Mensual — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir gastos y nómina de valores fijos a registros por mes/año, con soporte para copiar del mes anterior.

**Architecture:** Se agrega `mes` y `anio` a la tabla `gastos` (eliminando `activo`). Se crea tabla nueva `nomina_mensual` con `empleado_id, mes, anio, valor`. El dashboard lee de estas tablas filtrando por mes/año. El frontend agrega un selector de mes/año en la página Empleados.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/PostgreSQL, React 18, TanStack Query, `_ensure_columns` para migraciones.

---

## Archivos a modificar

| Archivo | Cambios |
|---------|---------|
| `backend/models.py` | Modificar `Gasto` (agregar `mes`, `anio`; quitar `activo`). Agregar `NominaMensual`. |
| `backend/database.py` | `_ensure_columns`: agregar `gastos.mes`, `gastos.anio`. `_ensure_indexes`: índice en `nomina_mensual`. |
| `backend/schemas.py` | Modificar `GastoCreate` (agregar `mes`, `anio`). Agregar `NominaItemUpdate`, `CopiarMesRequest`. |
| `backend/crud.py` | Reescribir `get_gastos`, `create_gasto`, `delete_gasto`. Eliminar `toggle_gasto`. Agregar `copiar_gastos_mes_anterior`, `get_nomina_mensual`, `upsert_nomina_mensual`, `copiar_nomina_mes_anterior`. Actualizar `get_dashboard`. |
| `backend/main.py` | Reemplazar endpoints de gastos. Agregar endpoints de nómina mensual. Quitar `PATCH /gastos/{id}/toggle` y `PATCH /empleados/{id}/nomina`. |
| `frontend/src/pages/Pages.jsx` | Reescribir componente `Empleados`: selector mes/año, tabla nómina editable, gastos del mes, botones copiar. |

---

## Task 1: Actualizar modelos (backend/models.py)

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Modificar `Gasto` y agregar `NominaMensual`**

Reemplazar el modelo `Gasto`:
```python
class Gasto(Base):
    __tablename__ = "gastos"
    id     = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120))
    valor  = Column(Float, default=0)
    mes    = Column(Integer)
    anio   = Column(Integer)
    creado = Column(DateTime, default=_utcnow)
```

Agregar después de `Gasto`:
```python
class NominaMensual(Base):
    __tablename__ = "nomina_mensual"
    id          = Column(Integer, primary_key=True, index=True)
    empleado_id = Column(Integer, index=True)
    mes         = Column(Integer)
    anio        = Column(Integer)
    valor       = Column(Float, default=0)
```

- [ ] **Step 2: Commit**
```bash
cd C:/Projects/bbcfile
git add backend/models.py
git commit -m "feat: gasto con mes/anio, nuevo modelo NominaMensual"
```

---

## Task 2: Migraciones automáticas (backend/database.py)

**Files:**
- Modify: `backend/database.py`

- [ ] **Step 1: Agregar columnas de migración en `_ensure_columns`**

En `_ensure_columns`, agregar al final de la lista de `_check`:
```python
_check("gastos", "mes",  "ALTER TABLE gastos ADD COLUMN mes INTEGER")
_check("gastos", "anio", "ALTER TABLE gastos ADD COLUMN anio INTEGER")
```

- [ ] **Step 2: Agregar índices en `_ensure_indexes`**

En la lista `indexes` de `_ensure_indexes`, agregar:
```python
("ix_gastos_mes_anio",       "gastos",          "mes, anio"),
("ix_nomina_mensual_emp_mes","nomina_mensual",   "empleado_id, mes, anio"),
```

- [ ] **Step 3: Registrar nueva tabla en `init_db`**

`init_db` llama `Base.metadata.create_all(bind=engine)` — esto crea `nomina_mensual` automáticamente al arrancar. No requiere cambio adicional.

- [ ] **Step 4: Commit**
```bash
git add backend/database.py
git commit -m "feat: migraciones automáticas gastos.mes/anio e índice nomina_mensual"
```

---

## Task 3: Schemas (backend/schemas.py)

**Files:**
- Modify: `backend/schemas.py`

- [ ] **Step 1: Modificar `GastoCreate` y agregar schemas nuevos**

Reemplazar `GastoCreate`:
```python
class GastoCreate(BaseModel):
    nombre: str
    valor: float
    mes: int
    anio: int
```

Agregar después de `GastoCreate`:
```python
class GastoUpdate(BaseModel):
    nombre: str
    valor: float

class NominaItemUpdate(BaseModel):
    valor: float

class CopiarMesRequest(BaseModel):
    mes_origen: int
    anio_origen: int
    mes_destino: int
    anio_destino: int
```

Eliminar `NominaUpdate` (ya no se usa).

- [ ] **Step 2: Commit**
```bash
git add backend/schemas.py
git commit -m "feat: schemas gastos/nomina mensual"
```

---

## Task 4: CRUD gastos mensuales (backend/crud.py)

**Files:**
- Modify: `backend/crud.py`

- [ ] **Step 1: Reemplazar funciones de gastos**

Localizar el bloque `# ─── GASTOS ───` (línea ~469) y reemplazar todas las funciones de gastos por:

```python
# ─── GASTOS MENSUALES ─────────────────────────────────────────────────────────
def get_gastos(db, mes: int, anio: int):
    return [{"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}
            for g in db.query(models.Gasto).filter_by(mes=mes, anio=anio).order_by(models.Gasto.nombre).all()]

def create_gasto(db, data: schemas.GastoCreate):
    g = models.Gasto(nombre=data.nombre, valor=data.valor, mes=data.mes, anio=data.anio)
    db.add(g); db.commit(); db.refresh(g)
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}

def update_gasto(db, id: int, data: schemas.GastoUpdate):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if not g: return None
    g.nombre = data.nombre; g.valor = data.valor
    db.commit()
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}

def delete_gasto(db, id, user=""):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if g:
        _log(db, user, "eliminó un gasto", "Gastos", g.nombre)
        db.delete(g)
        db.commit()

def copiar_gastos_mes_anterior(db, origen_mes: int, origen_anio: int, dest_mes: int, dest_anio: int, user: str = ""):
    # Elimina gastos existentes en destino antes de copiar
    db.query(models.Gasto).filter_by(mes=dest_mes, anio=dest_anio).delete()
    origen = db.query(models.Gasto).filter_by(mes=origen_mes, anio=origen_anio).all()
    for g in origen:
        db.add(models.Gasto(nombre=g.nombre, valor=g.valor, mes=dest_mes, anio=dest_anio))
    db.commit()
    _log(db, user, "copió gastos", "Gastos", f"{origen_mes}/{origen_anio} → {dest_mes}/{dest_anio}")
    return get_gastos(db, dest_mes, dest_anio)
```

- [ ] **Step 2: Commit**
```bash
git add backend/crud.py
git commit -m "feat: crud gastos mensuales con copiar mes anterior"
```

---

## Task 5: CRUD nómina mensual (backend/crud.py)

**Files:**
- Modify: `backend/crud.py`

- [ ] **Step 1: Agregar funciones de nómina mensual**

Agregar a continuación del bloque de gastos (antes de `# ─── DASHBOARD`):

```python
# ─── NÓMINA MENSUAL ───────────────────────────────────────────────────────────
def get_nomina_mensual(db, mes: int, anio: int):
    empleados = db.query(models.Empleado).filter_by(activo=True).order_by(models.Empleado.nombre).all()
    registros = {r.empleado_id: r.valor for r in
                 db.query(models.NominaMensual).filter_by(mes=mes, anio=anio).all()}
    return [{"empleado_id": e.id, "nombre": e.nombre, "cargo": e.cargo,
             "valor": registros.get(e.id, 0.0)} for e in empleados]

def upsert_nomina_mensual(db, empleado_id: int, mes: int, anio: int, valor: float, user: str = ""):
    r = db.query(models.NominaMensual).filter_by(empleado_id=empleado_id, mes=mes, anio=anio).first()
    if r:
        r.valor = valor
    else:
        db.add(models.NominaMensual(empleado_id=empleado_id, mes=mes, anio=anio, valor=valor))
    db.commit()
    e = db.query(models.Empleado).filter_by(id=empleado_id).first()
    nombre = e.nombre if e else str(empleado_id)
    _log(db, user, "actualizó nómina mensual", "Nómina", f"{nombre} {mes}/{anio}")
    return {"empleado_id": empleado_id, "mes": mes, "anio": anio, "valor": valor}

def copiar_nomina_mes_anterior(db, origen_mes: int, origen_anio: int, dest_mes: int, dest_anio: int, user: str = ""):
    # Obtener registros origen; si no existe para un empleado, usar nomina base del empleado
    empleados = db.query(models.Empleado).filter_by(activo=True).all()
    registros_origen = {r.empleado_id: r.valor for r in
                        db.query(models.NominaMensual).filter_by(mes=origen_mes, anio=origen_anio).all()}
    # Eliminar registros destino existentes
    db.query(models.NominaMensual).filter_by(mes=dest_mes, anio=dest_anio).delete()
    for e in empleados:
        valor = registros_origen.get(e.id, e.nomina)  # fallback al salario base del empleado
        db.add(models.NominaMensual(empleado_id=e.id, mes=dest_mes, anio=dest_anio, valor=valor))
    db.commit()
    _log(db, user, "copió nómina", "Nómina", f"{origen_mes}/{origen_anio} → {dest_mes}/{dest_anio}")
    return get_nomina_mensual(db, dest_mes, dest_anio)
```

- [ ] **Step 2: Commit**
```bash
git add backend/crud.py
git commit -m "feat: crud nomina mensual upsert y copiar mes anterior"
```

---

## Task 6: Actualizar dashboard en crud.py

**Files:**
- Modify: `backend/crud.py`

- [ ] **Step 1: Reemplazar lectura de nómina y gastos en `get_dashboard`**

Localizar en `get_dashboard` (líneas ~600-612) y reemplazar:

```python
    nominas = db.query(func.coalesce(func.sum(models.Empleado.nomina), 0)).filter_by(activo=True).scalar()
    gastos  = db.query(func.coalesce(func.sum(models.Gasto.valor),    0)).filter_by(activo=True).scalar()
```

Por:
```python
    # Determinar el mes/año a usar para nómina y gastos
    _mes_ref  = int(mes)  if mes  else datetime.now(COL_TZ).month
    _anio_ref = int(anio) if anio else datetime.now(COL_TZ).year
    nominas = db.query(func.coalesce(func.sum(models.NominaMensual.valor), 0)).filter_by(
        mes=_mes_ref, anio=_anio_ref).scalar()
    gastos  = db.query(func.coalesce(func.sum(models.Gasto.valor), 0)).filter_by(
        mes=_mes_ref, anio=_anio_ref).scalar()
```

También actualizar el comentario en esa sección:
```python
    # Nómina y gastos del mes/año de referencia (ya no son valores fijos).
```

Y ajustar `meses_factor`: cuando el dashboard filtra por año completo, ya NO se multiplica porque los datos mensuales no son fijos. Reemplazar:
```python
    if anio and not mes:
        meses_factor = 12
    elif mes:
        meses_factor = 1
    else:
        meses_factor = 1
```
Por:
```python
    meses_factor = 1  # gastos y nómina ya son del mes de referencia, no se multiplican
```

- [ ] **Step 2: Commit**
```bash
git add backend/crud.py
git commit -m "feat: dashboard lee nomina y gastos del mes de referencia"
```

---

## Task 7: Endpoints backend (backend/main.py)

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Reemplazar endpoints de gastos**

Localizar el bloque `# ─── GASTOS ───` y reemplazarlo completo por:

```python
# ─── GASTOS MENSUALES ─────────────────────────────────────────────────────────
@app.get("/gastos")
def list_gastos(mes: int, anio: int,
                db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_gastos(db, mes=mes, anio=anio)


@app.post("/gastos", status_code=201)
def create_gasto(data: schemas.GastoCreate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.create_gasto(db, data)


@app.put("/gastos/{id}")
def update_gasto(id: int, data: schemas.GastoUpdate,
                 db: Session = Depends(get_db), token=Depends(require_admin)):
    result = crud.update_gasto(db, id, data)
    if not result: raise HTTPException(404, "Gasto no encontrado")
    return result


@app.delete("/gastos/{id}")
def delete_gasto(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    crud.delete_gasto(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


@app.post("/gastos/copiar")
def copiar_gastos(data: schemas.CopiarMesRequest,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.copiar_gastos_mes_anterior(
        db, data.mes_origen, data.anio_origen, data.mes_destino, data.anio_destino,
        user=token.get("sub", "sistema"))
```

- [ ] **Step 2: Agregar endpoints de nómina mensual**

Eliminar el endpoint `PATCH /empleados/{id}/nomina` y agregar después del bloque de gastos:

```python
# ─── NÓMINA MENSUAL ───────────────────────────────────────────────────────────
@app.get("/nomina")
def get_nomina(mes: int, anio: int,
               db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.get_nomina_mensual(db, mes=mes, anio=anio)


@app.put("/nomina/{empleado_id}")
def update_nomina_mensual(empleado_id: int, mes: int, anio: int,
                          data: schemas.NominaItemUpdate,
                          db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.upsert_nomina_mensual(db, empleado_id, mes, anio, data.valor,
                                      user=token.get("sub", "sistema"))


@app.post("/nomina/copiar")
def copiar_nomina(data: schemas.CopiarMesRequest,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    return crud.copiar_nomina_mes_anterior(
        db, data.mes_origen, data.anio_origen, data.mes_destino, data.anio_destino,
        user=token.get("sub", "sistema"))
```

- [ ] **Step 3: Commit**
```bash
git add backend/main.py
git commit -m "feat: endpoints gastos y nomina mensuales"
```

---

## Task 8: Frontend — componente Empleados (frontend/src/pages/Pages.jsx)

**Files:**
- Modify: `frontend/src/pages/Pages.jsx`

- [ ] **Step 1: Agregar helper de mes/año actual al inicio del archivo**

Buscar al inicio del archivo donde se definen los helpers (cerca de `const UP = s => ...`) y agregar:

```js
const NOW = new Date();
const MES_ACTUAL = NOW.getMonth() + 1;
const ANIO_ACTUAL = NOW.getFullYear();
const MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
```

- [ ] **Step 2: Reemplazar el componente `Empleados` completo**

Localizar `export function Empleados()` y reemplazar todo el componente hasta su cierre `}` por:

```jsx
export function Empleados() {
  const qc = useQueryClient();
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const sf = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const [mes, setMes] = useState(MES_ACTUAL);
  const [anio, setAnio] = useState(ANIO_ACTUAL);

  const { data: emps = [] } = useQuery({ queryKey: ['empleados'], queryFn: () => api.get('/empleados').then(r => r.data) });
  const { data: usuarios = [] } = useQuery({ queryKey: ['usuarios'], queryFn: () => api.get('/usuarios').then(r => r.data) });
  const { data: gastos = [] } = useQuery({ queryKey: ['gastos', mes, anio], queryFn: () => api.get('/gastos', { params: { mes, anio } }).then(r => r.data) });
  const { data: nomina = [] } = useQuery({ queryKey: ['nomina', mes, anio], queryFn: () => api.get('/nomina', { params: { mes, anio } }).then(r => r.data) });

  const nomTotal = nomina.reduce((s, n) => s + n.valor, 0);
  const gasTotal = gastos.reduce((s, g) => s + g.valor, 0);

  // ── Empleados CRUD ──
  const guardarEmp = useMutation({
    mutationFn: () => modal === 'nuevo' ? api.post('/empleados', form) : api.put(`/empleados/${modal.id}`, form),
    onSuccess: (res) => {
      toast.success('Empleado guardado');
      if (modal === 'nuevo') {
        qc.setQueryData(['empleados'], prev => [...(prev || []), res.data]);
      } else {
        qc.setQueryData(['empleados'], prev => prev?.map(e => e.id === res.data.id ? res.data : e));
      }
      setModal(null);
    },
    onError: (e) => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const eliminarEmp = useMutation({
    mutationFn: (id) => api.delete(`/empleados/${id}`),
    onSuccess: (_, id) => { toast.success('Empleado eliminado'); qc.setQueryData(['empleados'], prev => prev?.filter(e => e.id !== id)); },
    onError: (e) => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  // ── Nómina mensual ──
  const updateNomina = useMutation({
    mutationFn: ({ empleado_id, valor }) => api.put(`/nomina/${empleado_id}`, { valor }, { params: { mes, anio } }),
    onSuccess: (res) => {
      qc.setQueryData(['nomina', mes, anio], prev =>
        prev?.map(n => n.empleado_id === res.data.empleado_id ? { ...n, valor: res.data.valor } : n));
    },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const copiarNomina = useMutation({
    mutationFn: () => {
      const om = mes === 1 ? 12 : mes - 1;
      const oa = mes === 1 ? anio - 1 : anio;
      return api.post('/nomina/copiar', { mes_origen: om, anio_origen: oa, mes_destino: mes, anio_destino: anio });
    },
    onSuccess: (res) => { toast.success('Nómina copiada del mes anterior'); qc.setQueryData(['nomina', mes, anio], res.data); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  // ── Gastos mensuales ──
  const [gnombre, setGnom] = useState('');
  const [gvalor, setGval] = useState(0);

  const addGasto = useMutation({
    mutationFn: () => api.post('/gastos', { nombre: gnombre, valor: +gvalor, mes, anio }),
    onSuccess: (res) => { toast.success('Gasto agregado'); qc.setQueryData(['gastos', mes, anio], prev => [...(prev || []), res.data]); setGnom(''); setGval(0); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const delGasto = useMutation({
    mutationFn: (id) => api.delete(`/gastos/${id}`),
    onSuccess: (_, id) => { toast.success('Gasto eliminado'); qc.setQueryData(['gastos', mes, anio], prev => prev?.filter(g => g.id !== id)); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const copiarGastos = useMutation({
    mutationFn: () => {
      const om = mes === 1 ? 12 : mes - 1;
      const oa = mes === 1 ? anio - 1 : anio;
      return api.post('/gastos/copiar', { mes_origen: om, anio_origen: oa, mes_destino: mes, anio_destino: anio });
    },
    onSuccess: (res) => { toast.success('Gastos copiados del mes anterior'); qc.setQueryData(['gastos', mes, anio], res.data); },
    onError: (e) => toast.error(e?.response?.data?.detail || 'Error'),
  });

  const anios = [ANIO_ACTUAL - 1, ANIO_ACTUAL, ANIO_ACTUAL + 1];

  return (
    <div>
      <PageHeader title="👔 Empleados y gastos" />

      {/* Selector mes/año */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <select style={sel} value={mes} onChange={e => setMes(+e.target.value)}>
          {MESES_ES.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
        </select>
        <select style={sel} value={anio} onChange={e => setAnio(+e.target.value)}>
          {anios.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <StatCard label="Nómina del mes"    value={fmt(nomTotal)} color={C.red} />
        <StatCard label="Gastos del mes"    value={fmt(gasTotal)} color={C.amber} />
        <StatCard label="Total egresos"     value={fmt(nomTotal + gasTotal)} color={C.red} />
        <StatCard label="Empleados activos" value={emps.filter(e => e.activo).length} color={C.primary} />
      </div>

      {/* Empleados */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h3 style={{ margin: 0, color: C.primary }}>Empleados</h3>
        <Btn variant="accent" onClick={() => { setForm({ activo: true, nomina: 0 }); setModal('nuevo'); }}>+ Nuevo empleado</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 24 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead><tr style={{ background: C.surface2 }}>
            {['Nombre', 'Cargo', 'Estado', 'Acciones'].map(h => (
              <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {emps.map(e => (
              <tr key={e.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={tdc}>{e.nombre}</td>
                <td style={tdc}>{e.cargo}</td>
                <td style={tdc}><span style={{ background: e.activo ? C.greenBg : C.redBg, color: e.activo ? C.green : C.red, borderRadius: 10, padding: '2px 10px', fontSize: 11, fontWeight: 600 }}>{e.activo ? 'Activo' : 'Inactivo'}</span></td>
                <td style={tdc}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Btn size="sm" variant="secondary" onClick={() => { setForm({ ...e }); setModal(e); }}>✏️ Editar</Btn>
                    <Btn size="sm" variant="danger" onClick={() => { if (window.confirm(`¿Eliminar a ${e.nombre}?`)) eliminarEmp.mutate(e.id); }}>🗑️ Eliminar</Btn>
                  </div>
                </td>
              </tr>
            ))}
            {emps.length === 0 && <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin empleados</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Nómina mensual */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h3 style={{ margin: 0, color: C.primary }}>Nómina — {MESES_ES[mes - 1]} {anio}</h3>
        <Btn variant="secondary" onClick={() => copiarNomina.mutate()} disabled={copiarNomina.isPending}>Copiar mes anterior</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}`, marginBottom: 24 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead><tr style={{ background: C.surface2 }}>
            {['Empleado', 'Cargo', 'Valor ($)'].map(h => (
              <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {nomina.map(n => (
              <tr key={n.empleado_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={tdc}>{n.nombre}</td>
                <td style={tdc}>{n.cargo}</td>
                <td style={tdc}>
                  <input type="number" style={{ ...inp, width: 140 }}
                    defaultValue={n.valor}
                    onBlur={e => updateNomina.mutate({ empleado_id: n.empleado_id, valor: +e.target.value })} />
                </td>
              </tr>
            ))}
            {nomina.length === 0 && <tr><td colSpan={3} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin empleados activos</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Gastos del mes */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <h3 style={{ margin: 0, color: C.primary }}>Gastos — {MESES_ES[mes - 1]} {anio}</h3>
        <Btn variant="secondary" onClick={() => copiarGastos.mutate()} disabled={copiarGastos.isPending}>Copiar mes anterior</Btn>
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <input style={{ ...sel, flex: 2, textTransform: 'uppercase' }} placeholder="NOMBRE DEL GASTO..." value={gnombre} onChange={e => setGnom(UP(e.target.value))} />
        <input type="number" style={sel} placeholder="Valor $" value={gvalor} onChange={e => setGval(e.target.value)} />
        <Btn onClick={() => addGasto.mutate()} disabled={!gnombre}>+ Agregar</Btn>
      </div>
      <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: C.surface }}>
          <thead><tr style={{ background: C.surface2 }}>
            {['Concepto', 'Valor', 'Acciones'].map(h => (
              <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: C.text2, borderBottom: `1px solid ${C.border}` }}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {gastos.map(g => (
              <tr key={g.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={tdc}>{g.nombre}</td>
                <td style={{ ...tdc, textAlign: 'right' }}>{fmt(g.valor)}</td>
                <td style={tdc}>
                  <Btn size="sm" variant="danger" onClick={() => { if (window.confirm('¿Eliminar gasto?')) delGasto.mutate(g.id); }}>Eliminar</Btn>
                </td>
              </tr>
            ))}
            {gastos.length === 0 && <tr><td colSpan={3} style={{ padding: 20, textAlign: 'center', color: C.text2 }}>Sin gastos este mes</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Modal empleado */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 460, boxShadow: '0 20px 60px rgba(0,0,0,.25)', maxHeight: '90vh', overflow: 'auto' }}>
            <h3 style={{ margin: '0 0 18px', color: C.primary }}>{modal === 'nuevo' ? 'Nuevo empleado' : 'Editar empleado'}</h3>
            {[['Nombre *', 'nombre', 'text', true], ['Documento', 'doc', 'text', false], ['Cargo', 'cargo', 'text', true], ['Teléfono', 'tel', 'tel', true], ['Email', 'email', 'email', false]].map(([l, k, t, ucase]) => (
              <div key={k} style={{ marginBottom: 10 }}>
                <label style={lbl}>{l}</label>
                <input type={t || 'text'} style={{ ...inp, textTransform: ucase ? 'uppercase' : 'none' }} value={form[k] || ''} onChange={e => sf(k, ucase ? UP(e.target.value) : e.target.value)} />
              </div>
            ))}
            <label style={lbl}>Usuario asignado</label>
            <select style={inp} value={form.usuario || ''} onChange={e => sf('usuario', e.target.value)}>
              <option value="">Sin asignar</option>
              {usuarios.filter(u => u.rol === 'empleado').map(u => <option key={u.id} value={u.username}>{u.username}</option>)}
            </select>
            <label style={lbl}>Salario base de referencia ($)</label>
            <input type="number" style={inp} value={form.nomina || 0} onChange={e => sf('nomina', +e.target.value)} />
            <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
              <Btn variant="secondary" onClick={() => setModal(null)}>Cancelar</Btn>
              <Btn onClick={() => guardarEmp.mutate()} disabled={guardarEmp.isPending || !form.nombre}>
                {guardarEmp.isPending ? 'Guardando...' : 'Guardar'}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**
```bash
git add frontend/src/pages/Pages.jsx
git commit -m "feat: componente Empleados con nómina y gastos mensuales"
```

---

## Task 9: Verificar y push

- [ ] **Step 1: Arrancar backend y verificar que no hay errores de importación**
```bash
cd C:/Projects/bbcfile/backend
uvicorn main:app --reload
# Verificar: no hay ImportError ni AttributeError en la consola
```

- [ ] **Step 2: Verificar endpoints con curl o en browser**
```bash
# Obtener token
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin1234"}'

# Gastos del mes actual (ej. mes=3&anio=2026)
curl "http://localhost:8000/gastos?mes=3&anio=2026" -H "Authorization: Bearer <TOKEN>"

# Nómina del mes actual
curl "http://localhost:8000/nomina?mes=3&anio=2026" -H "Authorization: Bearer <TOKEN>"
```

- [ ] **Step 3: Arrancar frontend y navegar a Empleados**
```bash
cd C:/Projects/bbcfile/frontend
npm start
# Ir a /empleados, verificar selector de mes, tabla nómina y sección gastos
```

- [ ] **Step 4: Push completo a producción**
```bash
cd C:/Projects/bbcfile
git checkout main
git merge dev
git push origin main
git checkout dev
git push origin dev
```
