# Auditoría de Producción BBC File — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auditar sistemáticamente el codebase de BBC File en 9 áreas críticas, documentar hallazgos y corregir todos los bugs CRÍTICO/ALTO encontrados.

**Architecture:** Audit de solo lectura por área → findings doc centralizado → fase de fixes → tests verdes. Sin tocar producción live. El audit produce un reporte en `docs/superpowers/audit-findings-2026-04-24.md` con todos los hallazgos clasificados por severidad.

**Tech Stack:** Python/FastAPI backend, React 18/TanStack Query 5 frontend, PostgreSQL, Redis, Cloudflare R2, Railway, Vercel.

---

## Archivos involucrados

**Lectura (audit):**
- `backend/crud.py` (1503 líneas) — lógica negocio, caché, queries SQL
- `backend/main.py` (647 líneas) — middlewares, CORS, scheduler flag
- `backend/routers/auth.py` (218 líneas) — JWT, blacklist, brute force
- `backend/routers/deps.py` (114 líneas) — guards por rol
- `backend/routers/portal.py` (1003 líneas) — aislamiento datos cliente
- `backend/routers/facturas.py` (383 líneas) — estados factura, utilidad
- `backend/routers/reportes.py` — endpoints reportes/Excel
- `backend/routers/afiliados.py` — endpoints afiliados
- `backend/scheduler_jobs.py` (196 líneas) — jobs cleanup
- `backend/run_daily.py` (27 líneas) — cron diario
- `backend/run_monthly.py` (25 líneas) — cron mensual
- `backend/models.py` — modelos DB
- `backend/schemas.py` — validación estados
- `backend/database.py` — pool conexiones, índices
- `backend/const.py` — constantes
- `backend/services/pila.py` — generador PILA (comentado en prod)
- `frontend/src/pages/Facturacion.jsx` (1207 líneas) — mutations, invalidación
- `frontend/src/pages/Finanzas.jsx` (673 líneas) — módulo nuevo sesión 17
- `frontend/src/pages/Afiliados.jsx` (1705 líneas) — filtros, validaciones
- `frontend/src/pages/App.jsx` (180 líneas) — rutas, adminOnly
- `frontend/src/pages/Dashboard.jsx` — query dashboard
- `frontend/src/pages/Cobro.jsx` — lógica cobro frontend
- `frontend/src/pages/PortalCliente.jsx` — portal cliente
- `frontend/src/utils/api.js` (87 líneas) — interceptor Axios
- `frontend/src/pages/Layout.jsx` — nav items por rol
- `docs/business-rules.md` — fuente de verdad reglas negocio

**Creados durante audit:**
- `docs/superpowers/audit-findings-2026-04-24.md` — hallazgos clasificados

---

## Task 0: Crear documento de hallazgos

**Files:**
- Create: `docs/superpowers/audit-findings-2026-04-24.md`

- [ ] **Step 1: Crear findings doc con estructura vacía**

```markdown
# Audit Findings — BBC File — 2026-04-24

## Resumen ejecutivo
<!-- Completar al final -->

## Hallazgos

### CRÍTICO

<!-- formato: **[Área] Archivo:línea** — descripción — fix recomendado -->

### ALTO

### MEDIO

### BAJO

### OK (verificado sin issues)
```

- [ ] **Step 2: Commit doc vacío**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: create audit findings template 2026-04-24"
```

---

## Task 1: Audit Auth & Seguridad

**Files:**
- Read: `backend/routers/auth.py`
- Read: `backend/routers/deps.py`
- Read: `backend/main.py` (sección CORS y middlewares)
- Read: `frontend/src/utils/api.js`

- [ ] **Step 1: Verificar JWT rotation y blacklist**

Leer `backend/routers/auth.py` completo. Verificar:

```
CHECKPOINTS:
[ ] /auth/refresh: llama cache_invalidar o inserta en token_blacklist el jti ANTES de emitir nuevos tokens
[ ] /auth/refresh: guarda nuevo refresh_token en respuesta (frontend necesita ambos)
[ ] _blacklist_jti(): usa INSERT ... ON CONFLICT DO NOTHING (no SELECT→INSERT)
[ ] /auth/logout: invalida refresh_token recibido en blacklist
[ ] access_token duration = 15 min (timedelta(minutes=15))
[ ] refresh_token duration = 7 días (timedelta(days=7))
```

- [ ] **Step 2: Verificar guards por rol en deps.py**

Leer `backend/routers/deps.py` completo. Verificar:

```
CHECKPOINTS:
[ ] Existe función/dependencia require_admin que valida rol == "admin"
[ ] Existe función/dependencia require_cliente que valida rol == "cliente"
[ ] get_current_user lee token del header Authorization: Bearer
[ ] Usuario inactivo es rechazado (activo == False → 401/403)
```

- [ ] **Step 3: Verificar CORS y SecurityHeadersMiddleware**

Leer `backend/main.py`, secciones middleware y CORS. Verificar:

```
CHECKPOINTS:
[ ] allow_methods incluye "PATCH" (fix sesión 6)
[ ] allow_methods lista cerrada: GET, POST, PUT, DELETE, OPTIONS, PATCH
[ ] allow_headers lista cerrada: Authorization, Content-Type
[ ] SecurityHeadersMiddleware NO tiene try/except que trague excepciones (fix sesión 13)
[ ] /health retorna solo {"status":"ok"} sin datos sensibles
[ ] /health/detail requiere token
[ ] ENABLE_SCHEDULER default "false"
```

- [ ] **Step 4: Verificar interceptor Axios**

Leer `frontend/src/utils/api.js` completo. Verificar:

```
CHECKPOINTS:
[ ] Interceptor 401 verifica esLoginRequest ANTES del bloque de refresh
[ ] Tras refresh exitoso: guarda TANTO nuevo access_token COMO nuevo refresh_token en localStorage
[ ] Si refresh falla: limpia localStorage y redirige a /login
[ ] No hay infinite retry loop si /auth/refresh también devuelve 401
```

- [ ] **Step 5: Verificar brute force**

En `backend/routers/auth.py` o `backend/crud.py`. Verificar:

```
CHECKPOINTS:
[ ] Tabla login_attempts trackea por IP
[ ] Tras 5 intentos fallidos: bloqueo 5 min
[ ] Login exitoso limpia login_attempts expirados
[ ] Modal verify-password usa /auth/verify-password, no /auth/login (fix sesión 7)
```

- [ ] **Step 6: Registrar hallazgos en findings doc**

Para cada checkpoint fallido, agregar entrada en `audit-findings-2026-04-24.md` con severidad, archivo:línea y fix recomendado. Para checkpoints OK, agregar a sección "OK (verificado sin issues)".

- [ ] **Step 7: Commit findings auth**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - auth & security"
```

---

## Task 2: Audit Invalidación de Caché

**Files:**
- Read: `backend/crud.py` (secciones create_*, update_*, delete_*, pagar_*)

- [ ] **Step 1: Mapear todos los prefijos de caché existentes**

Buscar en `backend/crud.py`:
```bash
grep -n "cache_invalidar\|cache_get\|cache_set" backend/crud.py
```

Construir tabla mental: qué prefijos existen (afiliados:, dashboard:, dashboard_clientes:, cobro:, etc.).

- [ ] **Step 2: Verificar invalidación en mutations de afiliados**

En `crud.py` buscar `create_afiliado`, `update_afiliado`, `delete_afiliado`, `restaurar_eliminado`. Verificar que cada uno llama:

```
CHECKPOINTS por función:
create_afiliado:
  [ ] cache_invalidar("afiliados:")
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")  ← fix sesión 17
  [ ] cache_invalidar("filter_options:") o equivalente

update_afiliado:
  [ ] cache_invalidar("afiliados:")
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")

delete_afiliado:
  [ ] cache_invalidar("afiliados:")
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")

restaurar_eliminado:
  [ ] cache_invalidar("afiliados:")  ← fix sesión 7
  [ ] cache_invalidar("dashboard:")  ← fix sesión 7
  [ ] cache_invalidar("dashboard_clientes:")
```

- [ ] **Step 3: Verificar invalidación en mutations de facturas**

En `crud.py` buscar `create_factura`, `update_factura`, `delete_factura`, `pagar_factura`, `marcar_planilla_pagada`. Verificar:

```
CHECKPOINTS:
create_factura:
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")  ← fix sesión 17
  [ ] cache_invalidar("cobro:")

update_factura:
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")

delete_factura:
  [ ] cache_invalidar("dashboard:")  y se llama ANTES de db.commit() ← fix sesión 15
  [ ] cache_invalidar("dashboard_clientes:")

pagar_factura:
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")  ← fix sesión 17
  [ ] cache_invalidar("cobro:")

marcar_planilla_pagada:
  [ ] cache_invalidar("dashboard:")
  [ ] cache_invalidar("dashboard_clientes:")  ← fix sesión 17
```

- [ ] **Step 4: Verificar que cache multi-worker no cae a dict en memoria cuando Redis está caído**

En `crud.py` buscar circuit breaker de Redis. Verificar:

```
CHECKPOINTS:
[ ] Cuando Redis está configurado pero circuit breaker abierto → NO usa dict en memoria
[ ] Dev sin Redis → dict en memoria funciona normalmente
```

- [ ] **Step 5: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - cache invalidation"
```

---

## Task 3: Audit Lógica Negocio SS Colombiana

**Files:**
- Read: `backend/crud.py` (funciones de cálculo SS)
- Read: `docs/business-rules.md`
- Read: `backend/const.py`

- [ ] **Step 1: Leer business-rules.md para tener la fuente de verdad**

Leer `docs/business-rules.md` completo. Anotar porcentajes oficiales:
- EPS: empleado 4%, empleador 8.5%
- AFP: empleado 4%, empleador 12%
- ARL: según nivel riesgo I(0.522%), II(1.044%), III(2.436%), IV(4.350%), V(6.960%)
- CCF: 4% empleador
- SENA: 2% empleador
- ICBF: 3% empleador
- IBC mínimo: 1 SMMLV

- [ ] **Step 2: Verificar cálculos SS en crud.py**

Buscar las funciones que calculan aportes/planilla. Verificar cada porcentaje contra business-rules.md:

```bash
grep -n "eps\|afp\|arl\|ccf\|sena\|icbf\|ibc\|0\.04\|0\.085\|0\.12\|0\.522\|1\.044\|2\.436\|4\.35\|6\.96" backend/crud.py | head -60
```

```
CHECKPOINTS:
[ ] EPS empleado: 4% del IBC
[ ] EPS empleador: 8.5% del IBC
[ ] AFP empleado: 4% del IBC
[ ] AFP empleador: 12% del IBC
[ ] ARL: porcentaje según nivel de riesgo del cargo (no fijo)
[ ] IBC: no puede ser menor a 1 SMMLV
[ ] Cálculos usan Numeric/Decimal, no float (fix sesión 14 — columnas Float→Numeric)
```

- [ ] **Step 3: Verificar estados ciclo afiliado**

En `crud.py` buscar `create_afiliado`, lógica de reingreso. En `routers/afiliados.py` buscar restaurar. Verificar:

```
CHECKPOINTS:
[ ] create_afiliado: si doc ya existe en eliminados → limpia TODO rastro anterior (Afiliado, Facturas, Documentos, SolicitudNovedad, SolicitudRetiro) antes de crear desde cero
[ ] Retiro → afiliado pasa a activo=False + registro en Retiro
[ ] Eliminación permanente: conserva solo registro Retiro (historial)
[ ] Restaurar eliminado: posible volver a activo=True
```

- [ ] **Step 4: Verificar lógica cobro HOY/VENCIDO/PROXIMO/COBRADO**

En `crud.py` buscar `get_cobro` o función equivalente. Verificar:

```
CHECKPOINTS:
[ ] COBRADO: factura existe para ese mes/año en estado pagado/planilla_pagada
[ ] HOY: vence hoy (fecha cobro == today)
[ ] VENCIDO: fecha cobro < today y no cobrado
[ ] PROXIMO: fecha cobro en próximos 5 días y no cobrado
[ ] Par (anio, mes) validado juntos, no anio IN (...) AND mes IN (...) por separado ← fix sesión 7
```

- [ ] **Step 5: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - SS business logic"
```

---

## Task 4: Audit Integridad Contable

**Files:**
- Read: `backend/routers/facturas.py`
- Read: `backend/crud.py` (get_dashboard, funciones financieras)
- Read: `backend/routers/reportes.py`
- Read: `backend/schemas.py`

- [ ] **Step 1: Verificar utilidad calculada server-side**

En `routers/facturas.py` o `crud.py` buscar `create_factura`, `update_factura`. Verificar:

```
CHECKPOINTS:
[ ] utilidad = ingresos - costos + conceptos_extra calculado en backend ← fix sesión 13
[ ] El valor de utilidad enviado por frontend se IGNORA (override server-side)
[ ] update_factura: rechaza cambio mes/anio si estado == 'pagado' o 'planilla_pagada' ← fix sesión 13
```

- [ ] **Step 2: Verificar estados válidos en schemas.py**

Leer `backend/schemas.py`. Verificar:

```
CHECKPOINTS:
[ ] FacturaCreate y FacturaUpdate permiten: 'pendiente', 'pagado', 'planilla_pagada'
[ ] NO permite estados inválidos (fix sesión 7 — planilla_pagada estaba bloqueado)
[ ] Flujo: pendiente → pagado → planilla_pagada (solo en ese orden)
```

- [ ] **Step 3: Verificar dashboard financiero**

En `crud.py` buscar `get_dashboard`. Verificar:

```
CHECKPOINTS:
[ ] ingresos: SUM solo facturas estado IN ('pagado', 'planilla_pagada') del período
[ ] pend_total: SUM facturas pendientes SIN filtro de período (all-time)
[ ] ingresos_adicionales: sumado una sola vez (no duplicado)
[ ] utilidad_neta: ingresos - nóminas - gastos_fijos (cargo_adicional ya descontado vía costos)
[ ] get_dashboard usa UNA sola query para facturas con CASE expressions (fix Sentry sesión 4)
[ ] dashboard_clientes: GROUP BY cliente con ingresos, costos, pendiente, n_afiliados, margen_pct
```

- [ ] **Step 4: Verificar reportes Excel == dashboard**

En `routers/reportes.py` buscar función que genera Excel financiero. Verificar:

```
CHECKPOINTS:
[ ] TOTAL PAGADAS fila: solo facturas pagado/planilla_pagada
[ ] TOTAL INGRESOS = pagadas + adicionales (debe coincidir con dashboard)
[ ] TOTAL PENDIENTE: facturas aún pendientes
[ ] Columna "Tipo Doc" presente antes de "Documento" en todos los Excels ← sesión 8
[ ] Columna "Fecha pago" presente en Excel facturación ← sesión 4
[ ] portal_resumen usa f.ingresos no f.costos ← fix sesión 6
```

- [ ] **Step 5: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - contabilidad integrity"
```

---

## Task 5: Audit Queries SQL & N+1s

**Files:**
- Read: `backend/crud.py` (get_cobro, get_dashboard, get_afiliados, get_afiliados_filter_options)
- Read: `backend/routers/portal.py` (portal_reporte)
- Read: `backend/database.py`

- [ ] **Step 1: Verificar get_cobro — filtros en SQL**

En `crud.py` buscar `get_cobro`. Verificar:

```
CHECKPOINTS:
[ ] Filtros empresa/cliente/doc/estado_srv aplicados en SQL (no Python post-fetch)
[ ] load_only() con columnas específicas (no SELECT *)
[ ] notin_ en lugar de ilike para estado (permite B-tree index)
[ ] Par (anio, mes) validado juntos en Python: (anio, mes) in _pares_validos ← fix sesión 7
```

- [ ] **Step 2: Verificar get_afiliados_filter_options — 1 query**

En `crud.py` buscar `get_afiliados_filter_options`. Verificar:

```
CHECKPOINTS:
[ ] Una sola query con set comprehensions (no 6 queries DISTINCT separadas) ← fix sesión 14
[ ] Resultado cacheado (TTL definido)
```

- [ ] **Step 3: Verificar N+1 en portal reportes**

En `routers/portal.py` buscar endpoint de reporte (Excel/PDF). Verificar:

```
CHECKPOINTS:
[ ] Facturas cargadas en batch: WHERE doc IN (lista_docs) ← fix Sentry sesión 9
[ ] facturas_by_doc dict construido fuera del loop de afiliados
[ ] Loop afiliados usa facturas_by_doc.get(a.doc, []) — sin query por afiliado
```

- [ ] **Step 4: Verificar pool de conexiones**

En `database.py` buscar `pool_size`, `max_overflow`, `WEB_CONCURRENCY`. Verificar:

```
CHECKPOINTS:
[ ] pool_size + max_overflow ≤ 25 (límite Railway)
[ ] Fórmula dinámica según WEB_CONCURRENCY
[ ] Con 1 worker (Procfile actual): pool=5, overflow=10 → 15 total ≤ 25 ✓
```

- [ ] **Step 5: Verificar índices declarados**

En `database.py` o `models.py` buscar `_ensure_indexes` o `__table_args__`. Verificar:

```
CHECKPOINTS:
[ ] ix_factura_estado_periodo: (estado, anio, mes) en facturas ← sesión 15
[ ] ix_afiliado_cobro_cobertura: parcial activo=TRUE ← sesión 14
[ ] ix_actividad_fecha_desc ← sesión 14
[ ] ix_token_blacklist_expires_at ← sesión 5
```

- [ ] **Step 6: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - SQL queries and N+1"
```

---

## Task 6: Audit Permisos & Aislamiento de Datos

**Files:**
- Read: `backend/routers/portal.py`
- Read: `backend/routers/deps.py`
- Read: `frontend/src/pages/App.jsx`
- Read: `frontend/src/pages/Layout.jsx`
- Read: `backend/main.py` (delete_usuario)

- [ ] **Step 1: Verificar aislamiento datos portal cliente**

En `routers/portal.py` buscar todos los endpoints. Verificar:

```
CHECKPOINTS:
[ ] Cada endpoint obtiene el cliente del JWT token (no de query param externo)
[ ] GET /portal/afiliados filtra WHERE cliente_txt == token.cliente
[ ] GET /portal/reportes filtra por el mismo cliente del token
[ ] Cliente no puede pasar otro nombre de cliente como parámetro para ver datos ajenos
[ ] Respuesta nunca incluye datos de otros clientes
```

- [ ] **Step 2: Verificar rutas adminOnly en App.jsx**

Leer `frontend/src/pages/App.jsx`. Verificar:

```
CHECKPOINTS:
[ ] /finanzas: lazy-loaded y adminOnly ← sesión 17
[ ] /usuarios: adminOnly
[ ] /empleados: adminOnly
[ ] /listas: adminOnly
[ ] /actividad: adminOnly o empleado puede verlo (revisar intención)
[ ] PortalCliente tiene ruta separada con guard cliente
```

- [ ] **Step 3: Verificar nav items por rol en Layout.jsx**

Leer `frontend/src/pages/Layout.jsx`. Verificar:

```
CHECKPOINTS:
[ ] Empleado NO ve "Reportes Financieros" en sidebar
[ ] Empleado NO ve "Usuarios", "Empleados" en sidebar
[ ] Cliente accede a portal en URL separada (no mismo Layout)
[ ] "Reportes Financieros" posición: debajo de Facturación ← sesión 17
```

- [ ] **Step 4: Verificar guard delete_usuario**

En `main.py` buscar `delete_usuario`. Verificar:

```
CHECKPOINTS:
[ ] Guard: cuenta admins activos en DB antes de eliminar ← fix sesión 15
[ ] Si único admin → HTTP 400 (no puede borrarse a sí mismo)
[ ] No solo bloquea username "admin" hardcodeado (fix sesión 15)
```

- [ ] **Step 5: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - permissions and data isolation"
```

---

## Task 7: Audit Scheduler Jobs

**Files:**
- Read: `backend/run_daily.py`
- Read: `backend/run_monthly.py`
- Read: `backend/scheduler_jobs.py`
- Read: `backend/main.py` (lifespan, ENABLE_SCHEDULER)

- [ ] **Step 1: Verificar run_daily.py**

Leer `backend/run_daily.py` completo (27 líneas). Verificar:

```
CHECKPOINTS:
[ ] Llama: notificaciones pendientes
[ ] Llama: limpiar token_blacklist expirados
[ ] Llama: limpiar actividad >7 días ← sesión 10 (reducido de 90 a 7)
[ ] Llama: limpiar_login_attempts() ← sesión 15
[ ] Crea su propia sesión DB (no depende del process web)
[ ] Maneja excepciones sin crashear (continúa con siguiente job si uno falla)
```

- [ ] **Step 2: Verificar run_monthly.py**

Leer `backend/run_monthly.py` completo (25 líneas). Verificar:

```
CHECKPOINTS:
[ ] Llama: limpiar tareas completadas >30 días
[ ] Llama: limpiar novedades >30 días
[ ] Llama: limpiar planillas antiguas (R2 + DB)
[ ] Crea su propia sesión DB
```

- [ ] **Step 3: Verificar scheduler_jobs.py**

Leer `backend/scheduler_jobs.py`. Verificar:

```
CHECKPOINTS:
[ ] limpiar_login_attempts(): borra WHERE creado < (now - 24h), NO borra activos
[ ] _cleanup_old_planillas(): limpia R2 + DB correctamente
[ ] Todas las funciones son llamables desde run_daily/run_monthly sin contexto web
[ ] No hay referencia a APScheduler (fue migrado a Railway Cron)
```

- [ ] **Step 4: Verificar que APScheduler no corre en proceso web**

En `main.py` buscar `APScheduler`, `BackgroundScheduler`, `lifespan`. Verificar:

```
CHECKPOINTS:
[ ] ENABLE_SCHEDULER default "false" en main.py
[ ] Si ENABLE_SCHEDULER está activo en prod → sería duplicación con Railway Cron → BUG
[ ] Lifespan no inicia scheduler a menos que ENABLE_SCHEDULER == "true"
```

- [ ] **Step 5: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - scheduler jobs"
```

---

## Task 8: Audit Frontend — TanStack Query

**Files:**
- Read: `frontend/src/pages/Facturacion.jsx`
- Read: `frontend/src/pages/Afiliados.jsx`
- Read: `frontend/src/pages/Dashboard.jsx`
- Read: `frontend/src/pages/Cobro.jsx`

- [ ] **Step 1: Verificar mutations Facturacion.jsx**

Buscar todos los `useMutation` en `Facturacion.jsx`:

```bash
grep -n "onSuccess\|invalidateQueries\|setQueryData\|queryKey" frontend/src/pages/Facturacion.jsx
```

Verificar:

```
CHECKPOINTS:
[ ] Crear factura onSuccess: invalidateQueries(['facturas', ...])
[ ] Crear factura onSuccess: invalidateQueries(['finanzas-clientes']) ← sesión 17
[ ] Crear factura onSuccess: invalidateQueries(['finanzas-cliente']) ← fix sesión 17 (key individual)
[ ] Eliminar factura onSuccess: mismas invalidaciones
[ ] pagar onSuccess: mismas invalidaciones
[ ] planillaPagada onSuccess: mismas invalidaciones
[ ] pagarBulk onSuccess: mismas invalidaciones
[ ] planillaBulk onSuccess: mismas invalidaciones
[ ] NO hay setQueryData con queryKey incompleta (faltando 'busqueda') ← fix sesión 13
[ ] Búsqueda activa fuerza limit: 0 (trae todos del año) ← fix sesión 7
```

- [ ] **Step 2: Verificar mutations Afiliados.jsx**

```bash
grep -n "onSuccess\|invalidateQueries\|setQueryData" frontend/src/pages/Afiliados.jsx | head -40
```

Verificar:

```
CHECKPOINTS:
[ ] Crear afiliado: invalida ['afiliados', ...] y ['afiliados-filter-options'] ← fix sesión 4
[ ] Eliminar afiliado: invalida ['afiliados', ...] y ['afiliados-filter-options']
[ ] Upload documentos en onSuccess (no en flujo principal) ← fix sesión 1
[ ] Validaciones nombre/doc/tel/cargo/empresa activas ← sesión 16
[ ] Campos doc e tel con inputMode="numeric" ← sesión 16
[ ] Botón Guardar deshabilitado sin empresa/nombre/doc ← sesión 16
```

- [ ] **Step 3: Verificar query keys consistentes**

Buscar todos los queryKey en páginas principales:

```bash
grep -rn "queryKey" frontend/src/pages/ | grep -v "node_modules" | grep -v ".bak"
```

Verificar que no hay typos en keys ('finanzas-clientes' vs 'finanzas-cliente', etc.).

- [ ] **Step 4: Verificar staleTime y refetchInterval en Finanzas.jsx**

```bash
grep -n "staleTime\|refetchInterval\|queryKey" frontend/src/pages/Finanzas.jsx
```

```
CHECKPOINTS:
[ ] staleTime: 0 en TODAS las queries de Finanzas ← sesión 17
[ ] refetchInterval: 300000 (300s, alineado con TTL backend) ← sesión 17 (antes era 120000)
[ ] NO hay refetchInterval de 120000 ms en ninguna query de Finanzas
```

- [ ] **Step 5: Verificar vite:preloadError listener**

```bash
grep -n "preloadError\|vite:preloadError" frontend/src/pages/App.jsx frontend/src/main.jsx 2>/dev/null || grep -rn "preloadError" frontend/src/
```

```
CHECKPOINTS:
[ ] window.addEventListener('vite:preloadError', () => window.location.reload()) presente ← fix sesión 11
[ ] Está en el entry point (index.jsx o main.jsx), no en un componente que puede desmontarse
```

- [ ] **Step 6: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - TanStack Query frontend"
```

---

## Task 9: Audit Módulo Finanzas (sesión 17)

**Files:**
- Read: `frontend/src/pages/Finanzas.jsx`
- Read: `backend/main.py` o router que registra /dashboard/clientes y /dashboard/cliente/{cliente}

- [ ] **Step 1: Verificar orden de rutas FastAPI**

Buscar dónde se registran los endpoints `/dashboard/clientes` y `/dashboard/cliente/{cliente}`:

```bash
grep -rn "dashboard/clientes\|dashboard/cliente" backend/
```

```
CHECKPOINTS:
[ ] /dashboard/clientes declarado ANTES de /dashboard/cliente/{cliente} ← sesión 17
[ ] Si el orden está invertido → FastAPI matchea 'clientes' como parámetro {cliente} → bug silencioso
```

- [ ] **Step 2: Verificar invalidaciones dashboard_clientes en crud.py**

```bash
grep -n "dashboard_clientes" backend/crud.py
```

```
CHECKPOINTS — dashboard_clientes invalidado en:
[ ] create_factura
[ ] update_factura
[ ] delete_factura
[ ] pagar_factura
[ ] marcar_planilla_pagada
[ ] create_afiliado
[ ] update_afiliado
[ ] delete_afiliado
```

Si CUALQUIERA de estos falta → ALTO (caché nunca se invalida en ese path).

- [ ] **Step 3: Verificar fuente listaClientes en Finanzas.jsx**

```bash
grep -n "listaClientes\|clientes\." frontend/src/pages/Finanzas.jsx | head -20
```

```
CHECKPOINTS:
[ ] listaClientes derivado de clientes.map(c => c.cliente) ← fix sesión 17
[ ] NO usa endpoint /clientes separado (que devuelve Afiliado.cliente_txt — diferente string)
[ ] Dropdown filtro usa misma fuente que tabla (para que match funcione)
```

- [ ] **Step 4: Verificar ruta /finanzas adminOnly**

```bash
grep -n "finanzas\|adminOnly\|Finanzas" frontend/src/pages/App.jsx
```

```
CHECKPOINTS:
[ ] Ruta /finanzas con lazy import de Finanzas.jsx
[ ] Guard adminOnly activo en esa ruta
[ ] Empleado que navega a /finanzas → redirigido (no crash ni pantalla en blanco)
```

- [ ] **Step 5: Verificar ModalCliente sin cache backend**

En `Finanzas.jsx` buscar la query del modal de cliente individual. Verificar:

```
CHECKPOINTS:
[ ] Query ['finanzas-cliente', clienteSeleccionado] tiene staleTime: 0 ← sesión 17
[ ] NO tiene cache backend (endpoint /dashboard/cliente/{cliente} sin cache)
[ ] Al abrir modal → siempre refetch (datos frescos)
```

- [ ] **Step 6: Registrar hallazgos y commit**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit findings - Finanzas module"
```

---

## Task 10: Triage y priorización de hallazgos

**Files:**
- Read/Edit: `docs/superpowers/audit-findings-2026-04-24.md`

- [ ] **Step 1: Completar resumen ejecutivo del findings doc**

Contar hallazgos por severidad y escribir el resumen:

```markdown
## Resumen ejecutivo

- **CRÍTICO:** N hallazgos — [lista de 1 línea cada uno]
- **ALTO:** N hallazgos
- **MEDIO:** N hallazgos
- **BAJO:** N hallazgos
- **Áreas sin issues:** [lista]
```

- [ ] **Step 2: Ordenar fixes por impacto**

Dentro de CRÍTICO y ALTO, ordenar de mayor a menor impacto. Los fixes se implementarán en ese orden.

- [ ] **Step 3: Commit triage**

```bash
git add docs/superpowers/audit-findings-2026-04-24.md
git commit -m "docs: audit triage complete - ready for fixes"
```

---

## Task 11: Implementar fixes CRÍTICO

**Files:** Según hallazgos del Task 10

- [ ] **Step 1: Para cada hallazgo CRÍTICO, implementar el fix**

Esquema por fix:

```
1. Leer el archivo afectado (líneas exactas del hallazgo)
2. Implementar corrección mínima que resuelve el issue
3. Verificar que no rompe tests existentes: pytest backend/tests/ -v -k "related_test"
4. Commit inmediato:
   git add <archivos>
   git commit -m "fix: [descripción exacta del bug] ([área] - CRÍTICO)"
```

Ejemplos de fixes esperados (actualizar según hallazgos reales):

- **Caché faltante:** agregar `cache_invalidar("prefijo:")` en la función afectada
- **Guard de rol faltante:** agregar dependencia `require_admin` al endpoint
- **Query N+1:** refactorizar a batch query + dict lookup
- **Interceptor Axios:** corregir orden de checks en el interceptor

- [ ] **Step 2: Correr suite de tests completa tras todos los fixes CRÍTICO**

```bash
cd backend && python -m pytest tests/ -v
```

Esperado: todos los tests pasan (baseline: 37 tests).

- [ ] **Step 3: Commit resumen fixes CRÍTICO**

```bash
git commit -m "fix: all CRÍTICO findings from production audit 2026-04-24" --allow-empty
```

---

## Task 12: Implementar fixes ALTO

**Files:** Según hallazgos del Task 10

- [ ] **Step 1: Para cada hallazgo ALTO, implementar el fix**

Mismo esquema que Task 11:

```
1. Leer archivo afectado
2. Fix mínimo
3. pytest relacionado
4. Commit individual: git commit -m "fix: [descripción] ([área] - ALTO)"
```

- [ ] **Step 2: Correr suite completa**

```bash
cd backend && python -m pytest tests/ -v
```

Esperado: ≥37 tests pasando (puede aumentar si se agregan tests para los fixes).

---

## Task 13: Tests para fixes críticos sin cobertura

**Files:**
- Modify: `backend/tests/test_bbcfile.py` (o archivo de tests correspondiente)

- [ ] **Step 1: Para cada fix CRÍTICO/ALTO que no tenía test, escribir el test**

Patrón:

```python
def test_[nombre_del_bug_corregido](client, db):
    """Verifica que [descripción del fix] funciona correctamente."""
    # Arrange: setup del estado que activaba el bug
    # Act: llamar al endpoint/función
    # Assert: verificar comportamiento correcto (no el bug)
```

- [ ] **Step 2: Correr nuevos tests**

```bash
cd backend && python -m pytest tests/ -v -k "nuevo_test"
```

- [ ] **Step 3: Commit tests**

```bash
git add backend/tests/
git commit -m "test: coverage for CRÍTICO/ALTO fixes from audit 2026-04-24"
```

---

## Task 14: Actualizar Changelog Obsidian

**Files:**
- Modify: `C:/Users/braya/OneDrive/Documents/Obsidian Vault/BBC File/Changelog.md`

- [ ] **Step 1: Agregar entrada sesión 18 al Changelog**

Agregar nueva entrada con todos los fixes implementados:

```markdown
### 2026-04-24 (sesión 18)

**Auditoría producción completa — N fixes**

#### Hallazgos y correcciones
- [CRÍTICO] **[Área]** `archivo:línea` — descripción — fix aplicado
- [ALTO] **[Área]** `archivo:línea` — descripción — fix aplicado
...

#### Áreas auditadas sin issues
- Auth & Seguridad ✅
- ...

**Tests:** N/N pasando ✓
```

- [ ] **Step 2: Merge a main si CI verde**

```bash
# Solo si GitHub Actions muestra verde en dev
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

## Self-Review del plan

**Cobertura spec:** Las 9 áreas del spec tienen tasks 1–9 correspondientes. Triage en Task 10. Fixes en Tasks 11–12. Tests en Task 13. Changelog en Task 14. ✓

**Placeholders:** Ninguno — cada step tiene comandos exactos, checkpoints específicos con referencias a sesiones/fixes previos. ✓

**Type consistency:** No hay tipos/funciones — es audit de lectura. Los grep commands son exactos y reproducibles. ✓

**Scope:** Plan produce un findings doc + todos los bugs CRÍTICO/ALTO corregidos + tests verdes. Scope apropiado para una sesión. ✓
