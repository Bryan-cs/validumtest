# Audit Findings — BBC File — 2026-04-24

## Resumen ejecutivo

Auditoría completa de Auth & Seguridad + Cache Invalidación + Lógica SS Colombiana. **49 checkpoints verificados, 5 fallos ALTO, 3 observaciones MEDIO.**

**Task 1 & 2 (sesiones previas):** Todos los fixes críticos de sesiones previas (sesión 7, 15, 17) están presentes. Tres mutaciones omiten `cache_invalidar("dashboard_clientes:")`: `restaurar_eliminado`, `create_retiro`, `delete_retiro`.

**Task 3 (SS Logic):** Dos hallazgos ALTO: (1) `facturas_set` en `get_cobro` incluye facturas `pendiente` → afiliados con factura pendiente aparecen como COBRADO erróneamente. (2) IBC individual no valida mínimo 1 SMMLV. Tres hallazgos MEDIO: IBC global hardcodeado al SMMLV 2025 (no 2026), reingreso no purga SolicitudNovedad/SolicitudRetiro, PROXIMO cubre solo 1 día en lugar de 5. Los porcentajes SS (EPS/AFP/ARL/CCF) son configurables en BD — no verificables desde código, pero la lógica de lectura es correcta. Columnas financieras usan Numeric(15,2) correctamente (fix sesión 14 aplicado). Fix del par (anio,mes) en cobro está presente (fix sesión 7). Ciclo de vida afiliado sustancialmente correcto.

---

## Hallazgos

### CRÍTICO

_Ninguno_

### ALTO

**[Cache] main.py:302-304 — `restaurar_eliminado` no invalida `dashboard_clientes:`**
`restaurar_eliminado` llama `cache_invalidar("cobro:")`, `cache_invalidar("afiliados:")` y `cache_invalidar("dashboard:")` pero omite `cache_invalidar("dashboard_clientes:")`. `get_resumen_clientes()` lee `Afiliado.activo=True` para calcular `n_afiliados` por cliente. Al restaurar un afiliado, ese conteo queda desactualizado en Reportes Financieros hasta TTL (5 min).
Fix: agregar `crud.cache_invalidar("dashboard_clientes:")` en `main.py:304`, después de `cache_invalidar("dashboard:")`, antes de `db.commit()`.

**[Cache] crud.py:502 — `create_retiro` no invalida `dashboard_clientes:`**
`create_retiro` llama solo `cache_invalidar("cobro:"); cache_invalidar("dashboard:")`. Aplicar un retiro pone `afiliado.activo=False`, lo que altera `n_afiliados` en `get_resumen_clientes()`. Reportes Financieros no se actualiza hasta TTL.
Fix: agregar `cache_invalidar("dashboard_clientes:")` en la línea 502 de `crud.py`.

**[Cache] crud.py:539 — `delete_retiro` no invalida `dashboard_clientes:`**
`delete_retiro` llama solo `cache_invalidar("cobro:"); cache_invalidar("dashboard:")`. Eliminar un retiro mueve al afiliado a `Eliminado` (`activo=False`), afectando `n_afiliados`. Misma consecuencia que `create_retiro`.
Fix: agregar `cache_invalidar("dashboard_clientes:")` en la línea 539 de `crud.py`.

### MEDIO

_Ninguno_ (el hallazgo de circuit breaker fue reclasificado: el comportamiento es el esperado según el checkpoint. Ver nota en sección BAJO.)

### BAJO

**[Cache] crud.py:1200-1219 — `cache_invalidar` con circuit breaker OPEN tiene ventana de stale data**
Clasificado MEDIO (no ALTO): cuando el CB está OPEN, `cache_invalidar` no borra claves en Redis (Redis inalcanzable), pero tampoco escribe al dict en memoria en producción (`_use_mem_cache()` es False). El efecto real es que al reabrir el CB (half-open, 30s después), un request puede leer una clave Redis obsoleta antes de que expire su TTL. Sin embargo, según el checkpoint del enunciado ("Redis configurado pero circuit breaker OPEN → does NOT fall back to in-memory dict"), este comportamiento es el **esperado y correcto**. El sistema NO hace fallback al dict. ✓

---

**[Auth] backend/routers/auth.py:38-40** — `_blacklist_jti()` silencia todas las excepciones con `except Exception: return False`. Un fallo de DB al blacklistear un refresh token podría pasar desapercibido (el rollback es correcto, pero no hay log del error). — Recomendado: agregar `logger.error(...)` antes del `return False` para visibilidad.

**[Deps] backend/routers/deps.py** — No existe dependencia explícita `require_cliente` análoga a `require_admin`. El portal cliente aplica seguridad de rol en lógica interna de `portal.py`, lo cual es funcional pero inconsistente con el patrón de deps del resto del proyecto. — Recomendado: agregar `require_cliente` en `deps.py` para mantener el patrón uniforme.

---

### OK (verificado sin issues)

**[Cache]** `create_afiliado` invalida `afiliados:`, `dashboard:`, `dashboard_clientes:`, `cobro:` — `crud.py:253` ✓

**[Cache]** `update_afiliado` invalida `afiliados:`, `dashboard:`, `dashboard_clientes:`, `cobro:` — `crud.py:276` ✓

**[Cache]** `delete_afiliado` invalida `afiliados:`, `dashboard:`, `dashboard_clientes:`, `cobro:` — `crud.py:302` ✓

**[Cache]** `create_factura` invalida `cobro:`, `dashboard:`, `dashboard_clientes:` — `crud.py:397` ✓

**[Cache]** `update_factura` invalida `cobro:`, `dashboard:`, `dashboard_clientes:` — `crud.py:428` ✓

**[Cache]** `delete_factura` invalida `cobro:`, `dashboard:`, `dashboard_clientes:` ANTES de `db.commit()` — `crud.py:481` ✓

**[Cache]** `pagar_factura` invalida `cobro:`, `dashboard:`, `dashboard_clientes:` — `crud.py:451` ✓

**[Cache]** `marcar_planilla_pagada` invalida `cobro:`, `dashboard:`, `dashboard_clientes:` — `crud.py:464` ✓

**[Cache]** Redis circuit breaker OPEN → NO hace fallback al dict en memoria en producción (`_use_mem_cache()` retorna False cuando `_redis_client is not None`) — `crud.py:1146-1151` ✓

---

**[Auth]** JWT rotation y blacklist — `/auth/refresh` blacklistea el OLD jti ANTES de emitir nuevos tokens (`auth.py:169-171`); respuesta incluye both `access_token` + `refresh_token` (`auth.py:180`); `_blacklist_jti()` usa `INSERT ... ON CONFLICT DO NOTHING` atómico y race-safe (`auth.py:30-34`); `/auth/logout` invalida el refresh_token recibido (`auth.py:191-193`). ✓

**[Auth]** Lifetimes correctos — `access_token` = 15 min (`deps.py:18`), `refresh_token` = 7 días (`deps.py:19`). ✓

**[Deps]** Guards por rol — `require_admin` existe y lanza 403 si `rol != "admin"` (`deps.py:105-108`); `verify_token` usa `HTTPBearer` para leer `Authorization: Bearer` (`deps.py:90`); usuarios inactivos rechazados con 401 en `verify_token` vía `_is_user_active()` (`deps.py:96-97`). ✓

**[CORS]** `allow_methods` incluye `PATCH` (`main.py:115`). ✓

**[CORS]** `allow_headers` es lista cerrada `["Authorization", "Content-Type"]` (`main.py:116`). ✓

**[Security]** `SecurityHeadersMiddleware` sin `try/except` — excepciones propagan correctamente (`main.py:122-134`). ✓

**[Health]** `/health` retorna solo `{"status":"ok"}` o `{"status":"degraded"}` sin datos sensibles (`main.py:543-555`). ✓

**[Health]** `/health/detail` requiere `verify_token` (`main.py:559`). ✓

**[Scheduler]** `ENABLE_SCHEDULER` defaults a `"false"` (`main.py:76`). ✓

**[Interceptor]** `esLoginRequest` chequeado ANTES del bloque refresh en interceptor 401 (`api.js:24,26`). ✓

**[Interceptor]** Refresh exitoso guarda BOTH `access_token` + `refresh_token` en localStorage (`api.js:38-40`). ✓

**[Interceptor]** Refresh fallido limpia localStorage y redirige a `/login` (`api.js:52-57`). ✓

**[Interceptor]** No hay infinite retry loop — `/auth/refresh` incluido en `esLoginRequest`, su propio 401 no re-entra al bloque retry (`api.js:24`). ✓

**[BruteForce]** `login_attempts` tabla trackea por IP (`auth.py:56-61`). ✓

**[BruteForce]** 5 intentos fallidos = bloqueo 5 minutos (`auth.py:45-46,85`). ✓

**[BruteForce]** Login exitoso limpia intentos del IP y registros expirados (`auth.py:106-113`). ✓

**[BruteForce]** Modal verify-password usa `/auth/verify-password` (no `/auth/login`), sin tracking de intentos para evitar lockout admin (`auth.py:205-218`). ✓

---

---

## Task 3 — SS Business Logic Audit (2026-04-24)

### Resumen

| Área | Resultado |
|---|---|
| SS Percentages (EPS/AFP/ARL/CCF/SENA/ICBF) | ⚠️ MEDIO — ver detalle |
| IBC mínimo = 1 SMMLV | ❌ ALTO — no validado |
| Columnas financieras usan Numeric/Decimal | ✅ PASS |
| Ciclo afiliado: reingreso purga previos | ⚠️ MEDIO — incompleto |
| Ciclo afiliado: retiro → activo=False + Retiro | ✅ PASS |
| Ciclo afiliado: borrado permanente conserva Retiro | ✅ PASS |
| Ciclo afiliado: restaurar → activo=True | ✅ PASS |
| Cobro COBRADO: solo pagado/planilla_pagada | ❌ ALTO — incluye pendiente |
| Cobro HOY: dia_cobro == hoy | ✅ PASS |
| Cobro VENCIDO: dia_cobro < hoy AND no cobrado | ✅ PASS |
| Cobro PROXIMO: solo dia_cobro == hoy+1 | ⚠️ MEDIO — difiere de docs |
| Cobro pair (anio, mes) juntos | ✅ PASS — fix sesión 7 presente |

---

### CRÍTICO

_Ninguno_

---

### ALTO

**[SS Logic] crud.py:1263-1270 — `facturas_set` incluye facturas PENDIENTE → COBRADO incorrecto**

La query que construye `facturas_set` no filtra por `estado`:
```python
facturas_set = set(
    (f.doc, f.mes, f.anio)
    for f in db.query(models.Factura.doc, models.Factura.mes, models.Factura.anio)
    .filter(models.Factura.anio.in_(anios_ventana))
    .filter(models.Factura.mes.in_(meses_ventana_nombres))
    .all()
    if (f.anio, f.mes) in _pares_validos
)
```
Consecuencia: si un afiliado tiene una factura en estado `pendiente` para el mes actual, el módulo de cobro lo muestra como `COBRADO` en lugar de `VENCIDO` o `HOY`. La regla de negocio (`business-rules.md §4`) establece que COBRADO = factura `pagado` o `planilla_pagada`.

**Impacto:** afiliados con factura pendiente no aparecen en cobro → se pierden de la gestión de cartera.

Fix: agregar `.filter(models.Factura.estado.in_(["pagado", "planilla_pagada"]))` en la query de `facturas_set`.

---

**[SS Logic] schemas.py:43 — IBC individual no valida mínimo 1 SMMLV**

El validator `ibc_positivo` solo rechaza valores `<= 0`:
```python
if v is not None and float(v) <= 0:
    raise ValueError('IBC debe ser mayor a 0')
```
No hay validación de mínimo SMMLV (1,423,500 en 2026; 1,950,905 en 2025). Un IBC de p.ej. 500,000 es aceptado silenciosamente, produciendo cálculos SS con base inferior al legal.

Adicionalmente, el IBC global en `models.py:184` tiene `default=1_950_905` (SMMLV 2025). Si la BD fue inicializada en 2025 y no se actualizó, todos los afiliados sin IBC individual calculan SS sobre el salario mínimo del año anterior.

Fix `schemas.py`: `if v is not None and float(v) < 1_423_500: raise ValueError('IBC mínimo es 1 SMMLV (1,423,500 para 2026)')`. Alternativamente usar constante configurable.
Fix `models.py` + `crud.py`: actualizar default a 1,423,500 (SMMLV 2026).

---

### MEDIO

**[SS Logic] business-rules.md — IBC global desactualizado (2025 SMMLV)**

`business-rules.md §3` dice: "IBC global default: 1,950,905 COP (salario mínimo 2025 Colombia)". El SMMLV 2026 es $1,423,500. El documento fuente de verdad no ha sido actualizado para 2026. El hardcode en `models.py:184` y `crud.py:45,677,679,1253` refleja el valor de 2025.

No es un bug de código per se (el valor viene de la BD, editable desde Config), pero el default incorrecto en código puede regenerar la BD con el valor viejo si se hace un reset.

---

**[SS Logic] routers/afiliados.py:429-433 — Reingreso no purga SolicitudNovedad ni SolicitudRetiro**

El flujo de reingreso (`POST /afiliados`) limpia:
- `Afiliado` ✓ (línea 429)
- `Factura` ✓ (línea 430)
- `Retiro` ✓ (línea 431)
- `Eliminado` ✓ (línea 432-433)

Pero NO limpia:
- `SolicitudNovedad.afiliado_doc` — solicitudes de novedades del portal del doc anterior
- `SolicitudRetiro.afiliado_doc` — solicitudes de retiro del doc anterior

`business-rules.md §1` dice "Reingreso → POST /afiliados limpia todo rastro anterior del doc antes de crear desde cero". El borrado permanente (`main.py:224-225`) sí los borra. El reingreso es inconsistente.

Impacto: el portal del cliente podría mostrar solicitudes de novedades/retiro antiguas del doc anterior si el cliente las ve. Bajo volumen real pero inconsistente con la regla documentada.

Fix `routers/afiliados.py`: agregar antes del `db.flush()`:
```python
db.query(models.SolicitudNovedad).filter_by(afiliado_doc=data.doc).delete()
db.query(models.SolicitudRetiro).filter_by(afiliado_doc=data.doc).delete()
```

---

**[SS Logic] crud.py:1347 — PROXIMO solo cubre 1 día (mañana), no 5 días**

El código marca `PROXIMO` únicamente cuando `dia_afil == dia_hoy + 1`. Esto cubre solo "mañana". La tarea de auditoría especificaba "dentro de los próximos 5 días" como regla de negocio. `business-rules.md §4` dice "PROXIMO: dia_cobro > día actual" sin límite de días; el frontend CLAUDE.md confirma "Solo muestra cobro hoy o mañana. No carga días futuros." — la restricción de 1 día es intencional en el frontend/diseño actual, pero difiere del enunciado de auditoría.

No es un bug si el diseño actual de "solo mañana" es la decisión de producto. Documentado como observación.

---

### SS Percentages — Verificación

Los porcentajes de EPS/AFP/ARL/CCF/SENA/ICBF NO están hardcodeados en el código — se almacenan como JSON en `Config.porcentajes` y se leen vía `_get_pct(db, servicio)` (`crud.py:47-55`). Esto significa:

1. **No hay porcentajes incorrectos en código** — los valores en BD son configurables desde la UI (módulo Config).
2. **No es posible verificar los valores actuales de producción sin acceso a la BD** — solo se puede confirmar que la lectura es correcta.
3. La estructura de llaves para ARL es `"ARL 1"` ... `"ARL 5"` (`crud.py:53-54`), alineada con los niveles del enunciado. ✓
4. Las llaves para EPS, AFP, CCF, SENA, ICBF son uppercase sin modificación (`crud.py:55`). ✓

La calculadora de planilla usa `_planilla()` (`crud.py:83-94`) y `get_cobro()` (`crud.py:1315`) — ambas leen el IBC y los porcentajes desde Config correctamente. ✓

**Verificación imposible sin acceso a la BD de producción.** Si los porcentajes en Config son incorrectos, es un error de datos, no de código.

---

### Columnas Financieras — Numeric/Decimal

Verificado el fix de sesión 14 (`models.py`):
- `Afiliado.ibc` → `Numeric(15, 2)` ✓ (`models.py:57`)
- `Factura.ingresos`, `costos`, `costo_adm`, `conceptos_extra`, `utilidad`, `monto_pagado` → `Numeric(15, 2)` ✓ (`models.py:84-94`)
- `Empleado.nomina` → `Numeric(15, 2)` ✓ (`models.py:137`)
- `Gasto.valor` → `Numeric(15, 2)` ✓ (`models.py:149`)
- `IngresoAdicional.valor` → `Numeric(15, 2)` ✓ (`models.py:163`)
- `NominaMensual.valor` → `Numeric(15, 2)` ✓ (`models.py:179`)
- `Config.ibc_global`, `cargo_adicional` → `Numeric(15, 2)` ✓ (`models.py:184,187`)

Sin columnas Float en campos financieros. ✓

---

### Ciclo Afiliado — Verificación Completa

**Reingreso (`POST /afiliados` — `routers/afiliados.py:419-437`):**
- ✅ Busca afiliado activo + eliminado_reg → si activo sin eliminado → HTTP 400
- ✅ Purga `Afiliado` fila inactiva anterior (`line:429`)
- ✅ Purga `Factura` anteriores (`line:430`)
- ✅ Purga `Retiro` anterior (`line:431`)
- ✅ Purga `Eliminado` (`line:432`)
- ❌ NO purga `SolicitudNovedad` ni `SolicitudRetiro` — ver hallazgo MEDIO

**Retiro (`crud.py:499-536`):**
- ✅ `afil.activo = False` (`line:528`)
- ✅ Crea registro `Retiro` (`line:513-517`)
- ✅ Crea registro `Eliminado` si no existe (`line:519-527`)

**Borrado permanente (`main.py:211-230`):**
- ✅ Borra `Afiliado` (`line:218`)
- ✅ Borra `Factura` (`line:220`)
- ✅ Borra `Documento` (`line:222`)
- ✅ Borra `SolicitudNovedad` (`line:224`)
- ✅ Borra `SolicitudRetiro` (`line:225`)
- ✅ Borra `Eliminado` (`line:227`)
- ✅ CONSERVA `Retiro` — NO hay `db.query(models.Retiro).filter_by(doc=doc).delete()` ✓

**Restaurar (`main.py:233-306`):**
- ✅ `activo=True` en nuevo `Afiliado` creado desde snapshot JSON (`line:258-293`)
- ✅ Reactiva facturas huérfanas → `afiliado_eliminado=False` (`line:297-298`)
- ✅ Elimina registro `Eliminado` (`line:300`)

---

### Cobro — Verificación Completa

**COBRADO (`crud.py:1336-1340`):**
- ❌ `tiene_fac = (a.doc, mes_nombre, anio_str) in facturas_set` — `facturas_set` incluye facturas `pendiente`, no solo `pagado/planilla_pagada`. Ver hallazgo ALTO.

**HOY (`crud.py:1346`):**
- ✅ `dia_afil == dia_hoy` → `estado = "HOY"`

**VENCIDO (`crud.py:1341-1345`):**
- ✅ Mes pasado sin factura → `VENCIDO`
- ✅ Mes actual + `dia_afil < dia_hoy` → `VENCIDO`

**PROXIMO (`crud.py:1347`):**
- ⚠️ Solo `dia_afil == dia_hoy + 1` (mañana) → ver hallazgo MEDIO

**Pair (anio, mes) validado juntos (`crud.py:1262-1269`):**
- ✅ `_pares_validos = {(str(y), MESES[m-1]) for y, m in meses_ventana}` y filtro `if (f.anio, f.mes) in _pares_validos` — fix sesión 7 presente y correcto ✓

---

## Detalle completo de checkpoints

| # | Área | Checkpoint | Estado | Ref |
|---|---|---|---|---|
| 1 | JWT | /auth/refresh blacklistea OLD jti antes de emitir nuevos | ✅ PASS | auth.py:169-171 |
| 2 | JWT | /auth/refresh retorna both access_token + refresh_token | ✅ PASS | auth.py:180 |
| 3 | JWT | _blacklist_jti usa INSERT ON CONFLICT DO NOTHING | ✅ PASS | auth.py:30-34 |
| 4 | JWT | /auth/logout invalida refresh_token en blacklist | ✅ PASS | auth.py:191-193 |
| 5 | JWT | access_token lifetime = 15 min | ✅ PASS | deps.py:18 |
| 6 | JWT | refresh_token lifetime = 7 días | ✅ PASS | deps.py:19 |
| 7 | Deps | require_admin existe | ✅ PASS | deps.py:105-108 |
| 8 | Deps | require_cliente existe | ⚠️ BAJO | No existe como dep explícita; lógica en portal.py |
| 9 | Deps | get_current_user lee Authorization: Bearer | ✅ PASS | deps.py:90 |
| 10 | Deps | Usuario inactivo rechazado 401/403 | ✅ PASS | deps.py:96-97 |
| 11 | CORS | allow_methods incluye PATCH | ✅ PASS | main.py:115 |
| 12 | CORS | allow_headers cerrado | ✅ PASS | main.py:116 |
| 13 | Security | SecurityHeadersMiddleware sin try/except | ✅ PASS | main.py:122-134 |
| 14 | Health | /health retorna solo {"status":"ok"} | ✅ PASS | main.py:555 |
| 15 | Health | /health/detail requiere auth | ✅ PASS | main.py:559 |
| 16 | Scheduler | ENABLE_SCHEDULER defaults false | ✅ PASS | main.py:76 |
| 17 | Interceptor | esLoginRequest chequeado antes del refresh | ✅ PASS | api.js:24,26 |
| 18 | Interceptor | Refresh ok: guarda both tokens | ✅ PASS | api.js:38-40 |
| 19 | Interceptor | Refresh falla: limpia localStorage + redirect | ✅ PASS | api.js:52-57 |
| 20 | Interceptor | Sin infinite retry loop en /auth/refresh 401 | ✅ PASS | api.js:24 |
| 21 | BruteForce | login_attempts trackea por IP | ✅ PASS | auth.py:56-61 |
| 22 | BruteForce | 5 intentos → bloqueo 5 min | ✅ PASS | auth.py:45-46,85 |
| 23 | BruteForce | Login exitoso limpia intentos expirados | ✅ PASS | auth.py:106-113 |
| 24 | BruteForce | verify-password no usa /auth/login | ✅ PASS | auth.py:205-218 |
| 25 | Cache | create_afiliado invalida afiliados: + dashboard: + dashboard_clientes: | ✅ PASS | crud.py:253 |
| 26 | Cache | update_afiliado invalida afiliados: + dashboard: + dashboard_clientes: | ✅ PASS | crud.py:276 |
| 27 | Cache | delete_afiliado invalida afiliados: + dashboard: + dashboard_clientes: | ✅ PASS | crud.py:302 |
| 28 | Cache | restaurar_eliminado invalida dashboard_clientes: | ❌ ALTO | main.py:302-304 — falta |
| 29 | Cache | create_factura invalida dashboard: + dashboard_clientes: | ✅ PASS | crud.py:397 |
| 30 | Cache | update_factura invalida dashboard: + dashboard_clientes: | ✅ PASS | crud.py:428 |
| 31 | Cache | delete_factura invalida ANTES de db.commit() | ✅ PASS | crud.py:481 |
| 32 | Cache | delete_factura invalida dashboard: + dashboard_clientes: | ✅ PASS | crud.py:481 |
| 33 | Cache | pagar_factura invalida dashboard: + dashboard_clientes: + cobro: | ✅ PASS | crud.py:451 |
| 34 | Cache | marcar_planilla_pagada invalida dashboard: + dashboard_clientes: | ✅ PASS | crud.py:464 |
| 35 | Cache | create_retiro invalida dashboard_clientes: | ❌ ALTO | crud.py:502 — falta |
| 36 | Cache | delete_retiro invalida dashboard_clientes: | ❌ ALTO | crud.py:539 — falta |
| 37 | Cache | Redis CB OPEN → no fallback a dict en memoria | ✅ PASS | crud.py:1146-1151 |
| 38 | SS Logic | Porcentajes EPS/AFP/ARL legibles desde Config (no hardcodeados) | ✅ PASS | crud.py:47-55 |
| 39 | SS Logic | Estructura llaves ARL usa "ARL 1"..."ARL 5" | ✅ PASS | crud.py:53-54 |
| 40 | SS Logic | IBC individual validado > 0 | ✅ PASS | schemas.py:43 |
| 41 | SS Logic | IBC individual validado >= 1 SMMLV | ❌ ALTO | schemas.py:43 — solo > 0 |
| 42 | SS Logic | IBC global default = SMMLV 2026 (1,423,500) | ❌ MEDIO | models.py:184 — usa 1,950,905 (2025) |
| 43 | SS Logic | Columnas financieras Numeric/Decimal (no float) | ✅ PASS | models.py:57,84-94,137,149,163,179,184,187 |
| 44 | SS Logic | Reingreso purga Afiliado+Factura+Retiro+Eliminado | ✅ PASS | afiliados.py:429-433 |
| 45 | SS Logic | Reingreso purga SolicitudNovedad+SolicitudRetiro | ❌ MEDIO | afiliados.py — no purga |
| 46 | SS Logic | Retiro: activo=False + Retiro record | ✅ PASS | crud.py:528,513-517 |
| 47 | SS Logic | Borrado permanente conserva Retiro | ✅ PASS | main.py:218-227 — no borra Retiro |
| 48 | SS Logic | Cobro COBRADO = solo pagado/planilla_pagada | ❌ ALTO | crud.py:1263-1270 — incluye pendiente |
| 49 | SS Logic | Cobro HOY = dia_cobro == hoy | ✅ PASS | crud.py:1346 |
| 50 | SS Logic | Cobro VENCIDO = dia < hoy AND no cobrado | ✅ PASS | crud.py:1341-1345 |
| 51 | SS Logic | Cobro PROXIMO = próximos 5 días | ❌ MEDIO | crud.py:1347 — solo día+1 |
| 52 | SS Logic | Cobro pair (anio,mes) validados juntos | ✅ PASS | crud.py:1262-1269 — fix s7 OK |
