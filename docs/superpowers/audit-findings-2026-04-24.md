# Audit Findings — BBC File — 2026-04-24

## Resumen ejecutivo

Auditoría completa de Auth & Seguridad + Cache Invalidación + Lógica SS Colombiana + Integridad Contable + SQL/N+1. **68 checkpoints verificados, 5 fallos ALTO, 4 fallos MEDIO.**

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

---

## Task 4 — Integridad Contable (2026-04-24)

### Resumen

**[Contabilidad]** utilidad server-side, estados, dashboard, Excel — mayormente verificados. Un hallazgo MEDIO en schemas (FacturaCreate permite estados pagado/planilla_pagada al crear), una observación BAJO en fórmula de utilidad (incluye `-costo_adm` no documentado).

| Área | Resultado |
|---|---|
| create_factura: utilidad server-side | ✅ PASS — crud.py:409 |
| create_factura: frontend utilidad ignorado | ✅ PASS — crud.py:409 sobreescribe |
| update_factura: utilidad server-side | ✅ PASS — crud.py:445 |
| update_factura: bloquea mes/anio si pagado/planilla_pagada | ✅ PASS — crud.py:433-438 |
| FacturaCreate: solo 'pendiente' permitido | ❌ MEDIO — schemas.py:93 |
| FacturaUpdate: tres estados permitidos | ✅ PASS — schemas.py:121-125 |
| planilla_pagada en enum (fix s7) | ✅ PASS — schemas.py:93,121 |
| Dashboard ingresos: solo pagado/planilla_pagada | ✅ PASS — crud.py:820 |
| pend_total: sin filtro de período (all-time) | ✅ PASS — crud.py:828-831 |
| ingresos_adicionales: sumado una vez | ✅ PASS — crud.py:844-862 |
| get_dashboard: query única con CASE (fix s4) | ✅ PASS — crud.py:818-832 |
| Excel TOTAL PAGADAS: solo pagado/planilla_pagada | ✅ PASS — reportes.py:223 |
| Excel TOTAL INGRESOS = pagadas + adicionales | ✅ PASS — reportes.py:262 |
| Excel TOTAL PENDIENTE: facturas pendientes | ✅ PASS — reportes.py:271-274 |
| Excel "Tipo Doc" antes de "Documento" | ✅ PASS — reportes.py:216 col 4 |
| Excel "Fecha pago" presente | ✅ PASS — reportes.py:218 col 18 |
| portal_resumen usa f.ingresos (no f.costos) | ✅ PASS — portal.py:114-115 |

---

### CRÍTICO

_Ninguno_

---

### MEDIO

**[Contabilidad] schemas.py:93 — `FacturaCreate` permite estados `pagado` y `planilla_pagada` al crear**

El validador en `FacturaCreate`:
```python
if v is not None and v not in ('pendiente', 'pagado', 'planilla_pagada'):
    raise ValueError(...)
return v or 'pendiente'
```
Acepta `pagado` o `planilla_pagada` al crear una factura nueva, saltándose el flujo `pendiente → pagado → planilla_pagada`. Un usuario autenticado podría crear una factura directamente en estado `pagado` sin pasar por el endpoint `/facturas/{id}/pagar` (que registra `banco` y `pagado_en`). Esto podría dejar facturas "pagadas" sin banco ni fecha de pago.

El checkpoint de la auditoría era que `FacturaCreate` solo debe permitir `pendiente` (estado inicial). El enum actual es demasiado permisivo para creación.

Fix `schemas.py:93`: cambiar a:
```python
if v is not None and v not in ('pendiente',):
    raise ValueError('Estado inicial debe ser "pendiente"')
return 'pendiente'
```

---

### BAJO

**[Contabilidad] crud.py:409,445 — Fórmula de utilidad incluye `-costo_adm` no documentado**

La fórmula actual en código:
```python
utilidad = (ingresos or 0) - (costos or 0) - (costo_adm or 0) + (conceptos_extra or 0)
```
El Changelog sesión 13 documenta: `utilidad recalculada server-side como ingresos - costos + conceptos_extra`. El campo `costo_adm` también se descuenta pero no aparece en la documentación pública de la fórmula.

Sin embargo, el Changelog sesión 13 también dice: "costo_adm como campo de tracking eliminado del POST/PUT de facturas (se enviaba 0 para facturas antiguas)". Si `costo_adm` siempre es 0 en práctica, la fórmula es funcionalmente equivalente a la documentada.

**No es un bug funcional** si `costo_adm` nunca se escribe con valor > 0. Es una discrepancia entre la documentación y el código que podría confundir en el futuro.

Recomendación: actualizar el comment en crud.py:408,444 para reflejar la fórmula real, o eliminar `costo_adm` de la fórmula si nunca se usa.

---

### OK (verificado)

**[Contabilidad]** `create_factura` calcula `utilidad` server-side como `ingresos - costos - costo_adm + conceptos_extra` — valor del frontend ignorado — `crud.py:408-409` ✓

**[Contabilidad]** `update_factura` recalcula `utilidad` server-side en línea 445, después de aplicar todos los campos del request — cualquier `utilidad` enviado por frontend se sobreescribe ✓

**[Contabilidad]** `update_factura` bloquea `mes`/`anio` si `f.estado in {"pagado", "planilla_pagada"}` → HTTP 400 — `crud.py:433-438` ✓

**[Contabilidad]** `FacturaUpdate` permite `'pendiente', 'pagado', 'planilla_pagada'` — `schemas.py:121-125` ✓

**[Contabilidad]** `planilla_pagada` presente en enum de `FacturaCreate` y `FacturaUpdate` (fix sesión 7) — `schemas.py:93,121` ✓

**[Contabilidad]** `get_dashboard` usa UNA sola query con CASE expressions para facturas (fix Sentry sesión 4) — `crud.py:818-832` ✓

**[Contabilidad]** `ingresos` en dashboard = `SUM(CASE WHEN estado IN (pagado, planilla_pagada) AND period_ok THEN ingresos)` — solo facturas pagadas del período — `crud.py:820` ✓

**[Contabilidad]** `pend_total` = `SUM(CASE WHEN pendiente AND afiliado_eliminado=False THEN ingresos)` — sin filtro de período, incluye histórico completo — `crud.py:828-831` ✓

**[Contabilidad]** `ingresos_adicionales` sumado una sola vez con `filter_by(mes=, anio=)` — no duplicado — `crud.py:844-862` ✓

**[Contabilidad]** Excel `ESTADOS_PAGADO = {"pagado", "planilla_pagada"}` — `TOTAL PAGADAS` solo cuenta esas — `reportes.py:223` ✓

**[Contabilidad]** Excel `TOTAL INGRESOS = tot_ing_pag + ing_adic_total` — `reportes.py:262` ✓

**[Contabilidad]** Excel `TOTAL PENDIENTE` — fila separada con `tot_ing_pend` — `reportes.py:271-274` ✓

**[Contabilidad]** Excel columnas: `cols = [..., "Tipo Doc", "Documento", ...]` — Tipo Doc en posición 4, Documento en posición 5 — `reportes.py:216` ✓

**[Contabilidad]** Excel columna `"Fecha pago"` presente en posición 18 — `reportes.py:218` ✓

**[Contabilidad]** `portal_resumen` usa `f.ingresos` en `total_pendiente` y `total_pagado` (fix sesión 6) — `portal.py:114-115` ✓

**[Contabilidad]** `get_dashboard_meses` — función no existe en `crud.py`. El Changelog la menciona como fix de sesión 7 (`total_ingresos ahora filtra solo facturas pagadas`) pero fue absorbida o renombrada. No aplica como checkpoint independiente.

---

---

## Task 5 — SQL Queries & N+1 Audit (2026-04-24)

### Resumen

**[SQL/N+1]** `get_cobro`, `get_afiliados_filter_options`, portal reports, connection pool — verificados ✓. Un fallo MEDIO: `ix_token_blacklist_expires_at` no está en `_ensure_indexes()`.

| Área | Resultado |
|---|---|
| get_cobro: filtros SQL (empresa/cliente/doc/estado_srv) | ✅ PASS |
| get_cobro: load_only() columnas específicas | ✅ PASS |
| get_cobro: notin_() para estado_srv (B-tree indexable) | ✅ PASS |
| get_cobro: par (anio, mes) validado juntos en Python | ✅ PASS |
| filter_options: 1 query + set comprehensions | ✅ PASS |
| filter_options: resultado cacheado (TTL 120s) | ✅ PASS |
| Portal reportes: facturas en 1 batch query | ✅ PASS |
| Portal reportes: facturas_by_doc construido fuera del loop | ✅ PASS |
| Portal reportes: loop usa .get(a.doc, []) sin per-afiliado query | ✅ PASS |
| Pool: pool_size + max_overflow ≤ 25 | ✅ PASS |
| Pool: fórmula dinámica según WEB_CONCURRENCY | ✅ PASS |
| Pool: 1 worker → pool=5 + overflow=10 = 15 ≤ 25 | ✅ PASS |
| Índice ix_factura_estado_periodo | ✅ PASS |
| Índice ix_afiliado_cobro_cobertura (partial, activo=TRUE) | ✅ PASS |
| Índice ix_actividad_fecha_desc | ✅ PASS |
| Índice ix_token_blacklist_expires_at | ❌ MEDIO |

---

### CRÍTICO

_Ninguno_

---

### ALTO

_Ninguno_

---

### MEDIO

**[SQL/N+1] database.py — `ix_token_blacklist_expires_at` no está en `_ensure_indexes()`**

El Changelog sesión 5 registra: `CREATE INDEX ix_token_blacklist_expires_at` creado manualmente en producción via Railway. Sin embargo, este índice **no aparece en `_ensure_indexes()`** en `database.py`. El bloque de índices simples (líneas 125-151) y el bloque de índices parciales PostgreSQL (líneas 153-169) no contienen ninguna referencia a `token_blacklist`.

Consecuencia: en un deploy fresh (nueva BD o Railway reset), el índice no se crea automáticamente. El job `_cleanup_expired_tokens()` que hace `DELETE FROM token_blacklist WHERE expires_at < NOW()` realizaría un Seq Scan sobre una tabla que puede crecer ilimitadamente sin limpieza eficiente.

Fix `database.py`: agregar en el bloque `indexes` de `_ensure_indexes()`:
```python
("ix_token_blacklist_expires_at", "token_blacklist", "expires_at"),
```

---

### OK (verificado sin issues)

**[SQL/N+1]** `get_cobro` filtros empresa/cliente/doc aplicados en SQL con `.filter()` antes de `.all()` — `crud.py:1296-1298` ✓

**[SQL/N+1]** `get_cobro` usa `load_only()` con 14 columnas específicas (id, nombre, doc, tipo_doc, empresa, cliente_txt, estado_srv, subtipo, fecha_afiliacion, fecha_ingreso, ibc, servicios, arl, novedades) — no SELECT * — `crud.py:1280-1295` ✓

**[SQL/N+1]** `get_cobro` usa `notin_(["RETIRADO"])` para estado_srv — B-tree indexable, no ilike — `crud.py:1278` ✓

**[SQL/N+1]** `get_cobro` valida par (anio, mes) juntos: `_pares_validos = {(str(y), MESES[m-1]) for y, m in meses_ventana}` + filtro Python `if (f.anio, f.mes) in _pares_validos` — fix sesión 7 presente — `crud.py:1262-1269` ✓

**[SQL/N+1]** `get_afiliados_filter_options` ejecuta UNA sola query DISTINCT con 6 columnas + set comprehensions en Python — no 6 queries separadas — `crud.py:181-192` ✓

**[SQL/N+1]** `get_afiliados_filter_options` cacheado con TTL=120s en `afiliados:filtros` — `crud.py:192` ✓

**[SQL/N+1]** Portal `/reportes` carga facturas en UN batch `WHERE doc IN (docs_afil)` ANTES del loop — `portal.py:744-755` ✓

**[SQL/N+1]** `facturas_by_doc` dict construido FUERA del loop de afiliados — `portal.py:753-755` ✓

**[SQL/N+1]** Loop afiliados usa `facturas_by_doc.get(a.doc, [])` — 0 queries por iteración — `portal.py:764` ✓

**[SQL/N+1]** Pool fórmula: `_workers=1 → _max_per_worker=15, pool_size=5, max_overflow=10, total=15 ≤ 25` — `database.py:20-23` ✓

**[SQL/N+1]** Procfile configura `--workers 1` confirmando la fórmula — `backend/Procfile:1` ✓

**[SQL/N+1]** `ix_factura_estado_periodo` en `_ensure_indexes()` sobre `(estado, anio, mes)` — `database.py:144` ✓

**[SQL/N+1]** `ix_afiliado_cobro_cobertura` partial index `WHERE activo = TRUE` sobre `(activo, estado_srv, empresa, cliente_txt)` — `database.py:155-157` ✓

**[SQL/N+1]** `ix_actividad_fecha_desc` partial index sobre `fecha DESC` — `database.py:159` ✓

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
| 53 | SQL/N+1 | get_cobro: filtros empresa/cliente/doc en SQL | ✅ PASS | crud.py:1296-1298 |
| 54 | SQL/N+1 | get_cobro: load_only() con 14 columnas específicas | ✅ PASS | crud.py:1280-1295 |
| 55 | SQL/N+1 | get_cobro: notin_() para estado_srv (B-tree indexable) | ✅ PASS | crud.py:1278 |
| 56 | SQL/N+1 | get_cobro: par (anio,mes) validado junto en Python | ✅ PASS | crud.py:1262-1269 |
| 57 | SQL/N+1 | filter_options: 1 query DISTINCT + set comprehensions | ✅ PASS | crud.py:181-192 |
| 58 | SQL/N+1 | filter_options: TTL cacheado (120s) | ✅ PASS | crud.py:192 |
| 59 | SQL/N+1 | Portal reportes: batch query WHERE doc IN (...) | ✅ PASS | portal.py:744-755 |
| 60 | SQL/N+1 | Portal reportes: facturas_by_doc fuera del loop | ✅ PASS | portal.py:753-755 |
| 61 | SQL/N+1 | Portal reportes: loop usa .get(a.doc, []) | ✅ PASS | portal.py:764 |
| 62 | SQL/N+1 | Pool: pool_size + max_overflow ≤ 25 | ✅ PASS | database.py:20-23 — 15 total |
| 63 | SQL/N+1 | Pool: fórmula dinámica WEB_CONCURRENCY | ✅ PASS | database.py:20-23 |
| 64 | SQL/N+1 | Pool: 1 worker → pool=5 + overflow=10 = 15 | ✅ PASS | Procfile + database.py |
| 65 | SQL/N+1 | Índice ix_factura_estado_periodo en _ensure_indexes() | ✅ PASS | database.py:144 |
| 66 | SQL/N+1 | Índice ix_afiliado_cobro_cobertura partial (activo=TRUE) | ✅ PASS | database.py:155-157 |
| 67 | SQL/N+1 | Índice ix_actividad_fecha_desc en _ensure_indexes() | ✅ PASS | database.py:159 |
| 68 | SQL/N+1 | Índice ix_token_blacklist_expires_at en _ensure_indexes() | ❌ MEDIO | database.py — ausente |
