# Audit Findings — BBC File — 2026-04-24

## Resumen ejecutivo

Auditoría completa de Auth & Seguridad. **20 checkpoints verificados, 0 fallos, 1 observación menor.**
Todos los fixes críticos de sesiones previas están presentes en el código actual.

---

## Hallazgos

### CRÍTICO

_Ninguno_

### ALTO

_Ninguno_

### MEDIO

_Ninguno_

### BAJO

**[Auth] backend/routers/auth.py:38-40** — `_blacklist_jti()` silencia todas las excepciones con `except Exception: return False`. Un fallo de DB al blacklistear un refresh token podría pasar desapercibido (el rollback es correcto, pero no hay log del error). — Recomendado: agregar `logger.error(...)` antes del `return False` para visibilidad.

**[Deps] backend/routers/deps.py** — No existe dependencia explícita `require_cliente` análoga a `require_admin`. El portal cliente aplica seguridad de rol en lógica interna de `portal.py`, lo cual es funcional pero inconsistente con el patrón de deps del resto del proyecto. — Recomendado: agregar `require_cliente` en `deps.py` para mantener el patrón uniforme.

---

### OK (verificado sin issues)

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
