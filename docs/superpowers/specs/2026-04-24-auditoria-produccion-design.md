# Auditoría de Producción — BBC File

**Fecha:** 2026-04-24
**Tipo:** Audit codebase — sin tocar producción live
**Método:** Lectura sistemática backend + frontend, sin credenciales prod

---

## Objetivo

Verificar que el sistema en producción no tenga crashes, bugs de lógica, gaps de seguridad ni inconsistencias contables. Cubrir todos los módulos activos post-sesión 17.

---

## Alcance — 9 áreas en orden de criticidad

### 1. Auth & Seguridad

**Archivos:** `backend/routers/auth.py`, `backend/routers/deps.py`, `backend/crud.py`, `frontend/src/utils/api.js`

Verificar:
- JWT rotation obligatoria en `/auth/refresh` — blacklist jti anterior antes de emitir nuevo
- `ON CONFLICT DO NOTHING` en blacklist — sin duplicate key errors
- Brute force: 5 intentos → bloqueo 5 min por IP — lógica correcta
- Guards por rol: todos los endpoints admin usan `require_admin`, portal usa `require_cliente`
- Endpoints empleado no accesibles con token cliente y viceversa
- CORS: métodos permitidos incluyen PATCH (fix sesión 6)
- `SecurityHeadersMiddleware` no traga excepciones (fix sesión 13)

### 2. Invalidación de caché

**Archivos:** `backend/crud.py`

Mapeo completo prefijos → mutations:

| Prefijo | Debe invalidarse en |
|---------|---------------------|
| `afiliados:` | create/update/delete/restore afiliado |
| `dashboard:` | create/update/delete factura, pagar, create/update/delete afiliado |
| `dashboard_clientes:` | create/update/delete factura, pagar, planilla_pagada, create/update/delete afiliado |
| `cobro:` | mutations afiliados/facturas |
| `filter_options:` | create/update/delete afiliado |

Verificar que ningún mutation deje un prefijo sin invalidar. Bug de sesión 17: `dashboard_clientes:` no se invalidaba desde mutations de facturas/afiliados.

### 3. Lógica negocio SS colombiana

**Archivos:** `backend/crud.py`, `docs/business-rules.md`

Verificar:
- Porcentajes EPS: empleado 4%, empleador 8.5% (nivel riesgo I–II–III–IV–V para ARL)
- Porcentajes AFP: empleado 4%, empleador 12%
- CCF: 4% empleador solo si salario ≥ 10 SMMLV o empresa ≥ 25 trabajadores
- SENA/ICBF: 2%/3% empleador, exentos si empresa < 10 trabajadores
- IBC: base de cálculo correcta, mínimo 1 SMMLV
- Estados ciclo afiliado: `activo → retirado/eliminado`, reingreso limpia rastro anterior
- Cobro: `HOY` (vence hoy), `VENCIDO` (pasado), `PROXIMO` (próximos 5 días), `COBRADO` — condiciones exactas
- Par `(anio, mes)` en cobro — fix sesión 7, no solo `anio IN (...) AND mes IN (...)`

### 4. Integridad contable

**Archivos:** `backend/crud.py`, `backend/routers/facturas.py`, `backend/routers/reportes.py`

Verificar:
- `utilidad` calculada server-side: `ingresos - costos + conceptos_extra` — frontend no puede sobreescribir
- Estados válidos factura: `pendiente → pagado → planilla_pagada` — no otros
- `update_factura` rechaza cambio `mes`/`anio` en facturas `pagado`/`planilla_pagada`
- Dashboard `ingresos` = solo facturas `pagado` + `planilla_pagada` del período
- `pend_total` sin filtro de período (all-time)
- Ingresos adicionales sumados una sola vez, no duplicados
- Excel financiero totales == dashboard totales (misma fuente)
- `portal_resumen` usa `ingresos` no `costos` (fix sesión 6)

### 5. Queries SQL & N+1s

**Archivos:** `backend/crud.py`, `backend/routers/`

Verificar:
- `get_cobro()`: filtros empresa/cliente/doc/estado_srv en SQL, no Python post-fetch
- `get_dashboard()`: dos queries facturas combinadas en una sola (fix sesión 4 Sentry)
- Portal reportes: batch lookup facturas por doc, no N+1 por afiliado (fix sesión 9)
- `get_afiliados_filter_options()`: 1 query con set comprehensions, no 6 queries DISTINCT separadas
- Pool conexiones: `pool_size` + `max_overflow` ≤ 25 (límite Railway)
- Índices: `ix_factura_estado_periodo`, `ix_afiliado_cobro_cobertura`, `ix_actividad_fecha_desc` presentes

### 6. Permisos & aislamiento de datos

**Archivos:** `backend/routers/portal.py`, todos los routers

Verificar:
- Portal: cliente solo ve afiliados de su propio `cliente_txt` — no puede ver datos de otros clientes
- `GET /portal/reportes` filtra por cliente del token, no acepta parámetro cliente externo
- Empleados no pueden acceder a módulos `adminOnly` (Finanzas, Usuarios, Empleados, Listas)
- `delete_usuario`: guard que bloquea si es el único admin activo
- `/health/detail` requiere token — `/health` público sin datos sensibles

### 7. Scheduler jobs

**Archivos:** `backend/run_daily.py`, `backend/run_monthly.py`, `backend/scheduler_jobs.py`

Verificar:
- `run_daily.py`: notificaciones, token_blacklist cleanup, actividad >7d — todos presentes y correctos
- `run_monthly.py`: tareas >30d, novedades >30d, planillas antiguas R2+DB
- `limpiar_login_attempts()`: borra registros >24h — no borra activos
- No hay APScheduler en `main.py` que duplique los Cron jobs de Railway
- `ENABLE_SCHEDULER` default `"false"` en main

### 8. Frontend — TanStack Query

**Archivos:** `frontend/src/pages/`

Verificar:
- `Facturacion.jsx`: mutations usan `invalidateQueries` no `setQueryData` con key incompleta (fix sesión 13)
- `Facturacion.jsx`: `onSuccess` invalida `['finanzas-cliente']` además de `['finanzas-clientes']` (fix sesión 17)
- Keys de query consistentes en todos los módulos — sin typos que causen stale data
- `staleTime: 0` en Finanzas para refetch al navegar
- `refetchInterval` en Finanzas: 300,000ms (alineado con TTL backend 300s)
- Búsqueda activa fuerza `limit: 0` en Facturación (fix sesión 7)
- `vite:preloadError` listener para auto-reload tras deploy

### 9. Módulo Finanzas (sesión 17 — nuevo)

**Archivos:** `frontend/src/pages/Finanzas.jsx`, `backend/routers/dashboard.py` o equivalente

Verificar:
- Rutas FastAPI: `/dashboard/clientes` declarada ANTES de `/dashboard/cliente/{cliente}` — sin conflicto path
- `cache_invalidar("dashboard_clientes:")` llamado en: create/update/delete factura, pagar_factura, marcar_planilla_pagada, create/update/delete afiliado
- `listaClientes` en Finanzas derivado de `clientes.map(c => c.cliente)` — no de `/clientes` directamente
- `ModalCliente` sin cache backend (`staleTime: 0`)
- Ruta `/finanzas` es `adminOnly` en `App.jsx`
- Breadcrumb: `Panel / Reportes Financieros`

---

## Criterios de severidad

| Nivel | Descripción | Ejemplo |
|-------|-------------|---------|
| **CRÍTICO** | Crash, pérdida de datos, acceso no autorizado | Portal ve datos de otro cliente |
| **ALTO** | Dato incorrecto silencioso, caché nunca invalidado | `utilidad` calculada por frontend |
| **MEDIO** | UX rota, feature no funciona | Búsqueda paginada incorrecta |
| **BAJO** | Inconsistencia visual, log faltante | Badge estado erróneo |

---

## Output esperado

Lista priorizada de hallazgos con:
- Área y archivo exacto (con línea si aplica)
- Severidad
- Descripción del bug
- Fix recomendado

Bugs CRÍTICO/ALTO deben corregirse en la misma sesión.
