# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BBC File** — Sistema de gestión de personal y seguridad social colombiana. Administra afiliados, facturas, retiros, nóminas, gastos, tareas, portal de clientes y planillas de pago SS. Full-stack: React 18 frontend + FastAPI backend.

## Development Commands

### Backend
```bash
cd bbcfile/backend
pip install -r requirements.txt
uvicorn main:app --reload        # Dev server → http://localhost:8000
# API docs: http://localhost:8000/docs (solo en dev — deshabilitado en prod)
```

### Frontend
```bash
cd bbcfile/frontend
pnpm install
pnpm start         # Dev server → http://localhost:5173 (vite.config.js)
pnpm run build     # Build de producción
```

## Multi-tenant (Organizaciones)

Este proyecto es **multi-tenant**: aloja varias organizaciones (empresas cliente) con datos
totalmente aislados. Un **superadmin** (rol `superadmin`, sin `organizacion_id`) crea organizaciones
y sus usuarios desde `/organizaciones`.

- **Roles**: `superadmin` | `admin` | `empleado` | `cliente`. `admin/empleado/cliente` pertenecen a
  una organización (`Usuario.organizacion_id`). `username` es único **global** (login sin selector).
- **Motor de aislamiento** (`backend/tenant.py`): un `ContextVar current_org_id` + listener
  `do_orm_execute` **auto-filtra** toda lectura ORM y bloquea update/delete cross-tenant; un
  `before_flush` **auto-sella** `organizacion_id` en inserts. Regla: si no hay organización activa ni
  id explícito al escribir un modelo tenant → error ruidoso (`TenantContextError`), nunca fila huérfana.
- **Wiring**: la dependencia `tenant_scope` (en `routers/deps.py`) fija `current_org_id` por petición;
  se aplica a todos los routers de datos en `main.py` (`include_router(..., dependencies=_TENANT)`).
  `get_org_id` resuelve la org: usuario normal → su org del token; **superadmin (god mode)** → header
  `X-Org-Id` (para usuarios normales el header se IGNORA → no hay fuga).
- **Modelos excluidos del auto-filtro**: `Usuario` (scoping explícito en `crud_usuarios.py`),
  `Organizacion`, `LoginAttempt`, `TokenBlacklist`.
- **Config/Lista** dejaron de ser globales → una fila por organización. `Afiliado.doc`, `Empleado.doc`,
  `Factura(codigo / doc,mes,anio)`, `NominaMensual` usan **unicidad compuesta con `organizacion_id`**.
- **Frontend**: `useAuth` guarda `orgActiva` (god mode); `utils/api.js` envía `X-Org-Id` solo si
  superadmin; `SuperAdminRoute` + página `Organizaciones.jsx`; banner god mode en `Layout.jsx`.
- **Seed/provisión**: `database.py` `_seed()` crea solo el superadmin (`SUPERADMIN_USER/PASS`);
  `provision_organizacion()` crea org + su Config + Listas + admin inicial.
- **Startup**: el esquema lo construye `create_all` + `_ensure_columns` (NO `alembic upgrade`).
  Follow-up: re-baseline de la cadena Alembic para el proyecto nuevo (requiere Postgres para verificar).

## Architecture

### Backend (`bbcfile/backend/`)

**Archivos principales:**
- **`main.py`** — FastAPI app; incluye todos los routers + endpoints directos. Rate limiting por usuario autenticado (SlowAPI + middleware propio), headers de seguridad, CORS restringido a orígenes conocidos.
- **`crud.py`** — Shim de re-exportación. La lógica de negocio está dividida en 14 submódulos:
  - `crud_afiliados.py` — CRUD afiliados, filtros, opciones
  - `crud_facturas.py` — Facturas, pagos, ingresos adicionales
  - `crud_cobro.py` — Cálculo de cobro SS por afiliado
  - `crud_dashboard.py` — Métricas dashboard y reportes financieros por cliente
  - `crud_cache.py` — Helpers Redis / dict en memoria
  - `crud_helpers.py` — Utilidades compartidas (`_log`, `_next_codigo`, `fmt`)
  - `crud_retiros.py`, `crud_tareas.py`, `crud_usuarios.py`, `crud_empleados.py`
  - `crud_gastos.py`, `crud_nomina.py`, `crud_actividad.py`, `crud_config.py`
- **`models.py`** — Modelos ORM SQLAlchemy.
- **`schemas.py`** — Pydantic v2 schemas con validaciones de negocio SS colombiana.
- **`database.py`** — SQLAlchemy; `init_db()` + `_ensure_indexes()`. Auto-migra URLs SQLite → PostgreSQL.
- **`logger.py`** — Logging estructurado JSON (Railway-friendly).
- **`const.py`** — Constantes compartidas (`MESES`, `SMMLV`).

**Routers (`backend/routers/`):**
- `auth.py` — Login, JWT (AT 15 min / RT cookie httpOnly), bloqueo brute-force por IP + combo IP:username.
- `afiliados.py` — CRUD afiliados con paginación server-side y filtros avanzados.
- `facturas.py` — Facturación, pago, generación PDF, ingresos adicionales, `GET /calc-planilla` (cálculo SS para UI).
- `reportes.py` — Exportaciones Excel y PDF (afiliados, cobro, financiero, eliminados).
- `tareas.py` — Tareas internas con comentarios y notificaciones.
- `portal.py` — Portal del cliente: solicitudes novedad/retiro, novedades de pago, reportes.
- `documentos.py` — Subida/descarga archivos; Cloudflare R2 (prod) o disco local (dev). Valida magic bytes.
- `planillas.py` — Planillas SS por cliente; uploads paralelos a R2.
- `eliminados.py` — Restaurar, borrar permanente, mover a retiros.
- `cobro.py`, `dashboard.py`, `actividad.py`, `config.py` — Endpoints de sus dominios.
- `empleados.py`, `gastos.py`, `nomina.py`, `retiros.py`, `usuarios.py` — CRUD de sus entidades.
- `seguimiento_arl.py` — Seguimiento de afiliados en espera de activación ARL.

**Auth:** JWT HS256. Access token 15 min. Refresh token en cookie httpOnly (`SameSite=None; Secure` en prod). Roles: `admin` | `empleado` | `cliente`.

**Soft deletes:** Afiliados eliminados → tabla `Eliminado` (restaurable). Retiro → afiliado pasa a `Eliminado` (no reactivar).

**Audit trail:** Mutaciones registradas en tabla `Actividad` (excepto admin — intencional). Retención 90 días.

**Caché:** Redis en producción (`REDIS_URL`), dict en memoria para dev. Prefijos: `cobro:`, `dashboard:`, `dashboard_clientes:`, `afiliados:`. Invalidación explícita en cada mutación relevante.

**Estados de afiliado (`estado_srv`):** ACTIVO, SUSPENDIDO, RETIRADO, DOBLE_AFILIACION, NO_ENCONTRADO, EN_ESPERA.

**Scheduler:** `bbc-daily` y `bbc-monthly` como servicios Cron separados en Railway. `ENABLE_SCHEDULER=false` en el servicio web — APScheduler no corre en prod.

### Frontend (`bbcfile/frontend/src/`)

**Archivos clave:**
- **`App.jsx`** — BrowserRouter, QueryClientProvider (`staleTime:30s, refetchOnWindowFocus:false`), rutas con `PrivateRoute` y `ClienteOnlyRoute`. Cada ruta envuelta en `ErrorBoundary` individual.
- **`utils/api.js`** — Axios con interceptor JWT, `_refreshPromise` compartida (evita race condition 401 simultáneos), `withCredentials:true`.
- **`hooks/useAuth.js`** — Zustand persist con `_hasHydrated` guard. Token en `bbc-auth` store, sin `localStorage['token']` separado.
- **`components/Layout.jsx`** — Sidebar colapsable con grupos, notificaciones polling 30s con sonido, WelcomeModal al iniciar sesión.
- **`components/UI.jsx`** — Design system propio. Exports: `C` (colores), `StatCard`, `Btn`, `fmt`, `Modal`, `ErrorMsg`, `SkeletonRow`, etc.
- **`components/FiltroCheck.jsx`** — Dropdown de filtros múltiples reutilizable.
- **`utils/colors.js`** — `hashStr`, colores determinísticos por empresa/banco.

**Páginas (`pages/`):**

| Ruta | Página | Acceso |
|---|---|---|
| `/` | `Dashboard.jsx` | Admin/Empleado |
| `/afiliados` | `Afiliados.jsx` | Admin/Empleado |
| `/retiros` | `Retiros.jsx` | Admin/Empleado |
| `/tareas` | `Tareas.jsx` | Todos |
| `/facturacion` | `Facturacion.jsx` | Admin/Empleado |
| `/cobro` | `Cobro.jsx` | Admin/Empleado |
| `/planillas-ss` | `PlanillasSS.jsx` | Admin/Empleado |
| `/finanzas` | `Finanzas.jsx` | Admin |
| `/empleados` | `Empleados.jsx` | Admin |
| `/usuarios` | `Usuarios.jsx` | Admin |
| `/listas` | `Listas.jsx` | Admin |
| `/calculadora` | `Calculadora.jsx` | Admin |
| `/actividad` | `Actividad.jsx` | Admin |
| `/novedades-clientes` | `NovedadesClientes.jsx` | Admin |
| `/portal` | `PortalCliente.jsx` | Cliente |

**Cobro (`Cobro.jsx`):** Solo muestra afiliados con cobro hoy (COBRAR_HOY) o mañana (PROXIMO). Ventana 2 meses.

**Retiros (`Retiros.jsx`):** Búsqueda bajo demanda por documento. Eliminar retiro mueve afiliado a Eliminados.

**Afiliados → tab Eliminados:** ↩ Restaurar | 📋 → Retiros | 🗑️ Borrar permanente.

**Stack:**
- React 18.3, React Router 6, TanStack React Query 5, Zustand 5, Axios, Recharts, Sonner, Tailwind CSS 3, shadcn/ui, pnpm.

### Data Flow
```
React Page → Axios (api.js) → FastAPI (main.py) → crud_*.py → SQLAlchemy → PostgreSQL
                ↑                                      ↑
        Zustand (auth)                         Redis cache (prod)
        React Query (cache)
```

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | SQLite (`bbcfile.db`) en dev |
| `SECRET_KEY` | JWT signing key | Vacío — **requerido en prod** |
| `PORT` | Puerto del servidor | 8000 |
| `REDIS_URL` | Redis para caché | Sin Redis = caché en memoria |
| `STORAGE_BUCKET` | Bucket Cloudflare R2 | Sin bucket = disco local (falla en prod) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credenciales R2 | — |
| `R2_ENDPOINT_URL` | Endpoint R2 | — |
| `SENTRY_DSN` | Monitoreo de errores | Opcional |
| `WEB_CONCURRENCY` | Workers Uvicorn | 1 |
| `ENABLE_SCHEDULER` | APScheduler en proceso web | `false` |

## Deployment

- **Backend**: Railway (`railway.toml` — fuente de verdad del startCommand)
- **Frontend**: Vercel (detecta pnpm por `pnpm-lock.yaml`)
- **Archivos**: Cloudflare R2
- **DB**: PostgreSQL en Railway (backups diarios nativos Railway Pro)
- **Cron**: `bbc-daily` (00:00 UTC) y `bbc-monthly` (06:00 UTC 1er día) — servicios separados Railway
- **Git workflow**: commits y push a `dev` por defecto. Solo push a `main` cuando se indique explícitamente ("push a main"). Merge solo si GitHub Actions ✅ verde.

## Credenciales dev por defecto
- `admin / admin1234`
- `empleado1 / emp1234`

## Agents Team

BBC File tiene un equipo de agentes especializados orquestados por la sesión principal de Claude Code. Los prompts están en `bbcfile/.claude/agents/`.

### Cuándo usar agentes (NECESARIO, no por defecto)

**USAR agentes cuando:**
- La tarea toca 3+ archivos en capas distintas (DB + backend + frontend)
- Feature nueva que requiere nuevo endpoint + UI
- Auditoría o revisión independiente de un módulo completo
- Trabajo en módulo complejo o poco familiar

**NO usar agentes cuando:**
- Bug en 1 archivo → implementar directo en sesión principal
- Fix de UI menor, ajuste de estilo, cambio de texto
- Cambio de configuración o variable
- Cualquier tarea describible en 1 línea
- El orquestador ya conoce el contexto completo y el cambio es trivial

**Regla:** Si puedes hacerlo directo en menos tiempo del que tarda el pipeline de agentes, hazlo directo.

### Agentes disponibles

| Agente | Archivo | Rol |
|---|---|---|
| `bbc-explorer` | `.claude/agents/bbc-explorer.md` | Exploración read-only del codebase |
| `bbc-architect` | `.claude/agents/bbc-architect.md` | Revisión arquitectónica antes de implementar |
| `bbc-planner` | `.claude/agents/bbc-planner.md` | Descomposición de tareas con dependencias |
| `bbc-db` | `.claude/agents/bbc-db.md` | Modelos SQLAlchemy + migraciones Alembic |
| `bbc-backend` | `.claude/agents/bbc-backend.md` | FastAPI, crud_*.py, routers |
| `bbc-frontend` | `.claude/agents/bbc-frontend.md` | React pages, TanStack Query |
| `bbc-domain-reviewer` | `.claude/agents/bbc-domain-reviewer.md` | Validación de lógica de negocio SS colombiana |
| `bbc-reviewer` | `.claude/agents/bbc-reviewer.md` | Revisión de calidad y bugs |
| `bbc-tester` | `.claude/agents/bbc-tester.md` | Tests pytest (SQLite + PostgreSQL integración) |
| `bbc-changelog` | `.claude/agents/bbc-changelog.md` | Actualización Obsidian |

### Estrategias de ejecución

```
Bug simple:             explorer → [backend|frontend] → domain-reviewer? → reviewer
Feature con endpoint:   explorer → architect → planner → db? → backend → domain-reviewer? → frontend → reviewer → tester → changelog
Feature solo frontend:  explorer → planner → frontend → reviewer → changelog
Feature paralela:       explorer → architect → planner → backend ∥ frontend (worktrees) → domain-reviewer? → reviewer → tester → changelog
Auditoría:              explorer → backend + frontend (paralelo) → domain-reviewer → reviewer
Cambio SS/facturación:  explorer → architect → planner → backend → domain-reviewer → reviewer → tester → changelog
```

`domain-reviewer` obligatorio: cálculos SS, estados factura, cobro, planillas, ingresos/utilidad.
`architect` obligatorio: nuevo modelo, nuevo endpoint, cambio auth, lógica caché.
