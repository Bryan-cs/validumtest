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
  `get_org_id` toma la organización **únicamente del JWT firmado**. No lee ningún header: no existe
  "god mode" por `X-Org-Id` (se eliminó). El superadmin no tiene organización, así que recibe **403**
  en toda ruta de datos; para operar dentro de una organización debe autenticarse como un usuario de
  esa organización. Cero superficie de spoofing desde el cliente.
- **Autorización por rol**: los routers de uso interno (reportes, planillas, seguimiento_arl,
  eliminados, retiros, empleados, nomina, gastos, usuarios, dashboard, cobro, actividad, credenciales)
  se registran con `_INTERNO` = `_TENANT + require_admin_or_empleado`, que bloquea al rol `cliente`.
  Un cliente solo alcanza `/portal/*`, `/documentos`, `/listas`, `/tareas/notificaciones` y `/auth/*`.
  En `afiliados` y `facturas` el listado se filtra además por `cliente_ref`.
- **Modelos excluidos del auto-filtro**: `Usuario` (scoping explícito en `crud_usuarios.py`),
  `Organizacion`, `LoginAttempt`, `TokenBlacklist`.
- **Config/Lista** dejaron de ser globales → una fila por organización. `Afiliado.doc`, `Empleado.doc`,
  `Factura(codigo / doc,mes,anio)`, `NominaMensual` usan **unicidad compuesta con `organizacion_id`**.
- **Frontend**: `SuperAdminRoute` + página `Organizaciones.jsx` para el panel del superadmin.
  (`utils/api.js` todavía envía `X-Org-Id` cuando el rol es superadmin, pero el backend lo ignora.)
- **Seed/provisión**: `database.py` `_seed()` crea solo el superadmin (`SUPERADMIN_USER/PASS`);
  `provision_organizacion()` crea org + su Config + Listas + admin inicial.
- **Startup**: el esquema lo construye `create_all` + `_ensure_columns` en `init_db()` (NO
  `alembic upgrade`; ver el comentario en `database.py:55` — Alembic en startup multi-worker abre
  conexiones fuera del advisory lock y genera deadlocks). El `startCommand` de `railway.toml` **ya no
  llama a Alembic**: la migración raíz quedó baselineada contra la base de BBC prod (no crea tablas,
  asume que existen) y contra un Postgres nuevo fallaba en la primera sentencia. Peor: habría aplicado
  `retiros_doc_key UNIQUE(doc)`, que rompe el multi-tenant porque impide que dos organizaciones
  retiren la misma cédula. La base de producción quedó estampada con `alembic stamp head`
  (`s3t4u5v6w7x8`), así que las migraciones futuras aplican desde ahí.

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
| `STORAGE_BUCKET` | Nombre del bucket S3 | **Requerido en prod** (el guard de `documentos.py` corre en tiempo de import: sin storage el backend NO arranca contra Postgres) |
| `STORAGE_ENDPOINT` | Endpoint S3 explícito (Railway Buckets, MinIO, etc.) | Si falta, se arma el de R2 con `STORAGE_ACCOUNT` |
| `STORAGE_ACCOUNT` | Account ID de Cloudflare (solo modo R2) | — |
| `STORAGE_KEY` / `STORAGE_SECRET` | Credenciales S3 | — |
| `STORAGE_REGION` | Región S3 | `auto` |
| `SENTRY_DSN` | Monitoreo de errores | Opcional |
| `WEB_CONCURRENCY` | Workers Uvicorn | 1 |
| `ENABLE_SCHEDULER` | APScheduler en proceso web | `false` |

## Deployment

- **Backend**: Railway (`railway.toml` — fuente de verdad del startCommand)
- **Frontend**: Vercel (detecta pnpm por `pnpm-lock.yaml`)
- **Archivos**: Cloudflare R2
- **DB**: PostgreSQL en Railway (backups diarios nativos Railway Pro)
- **Cron**: `bbc-daily` (00:00 UTC) y `bbc-monthly` (06:00 UTC 1er día) — servicios separados Railway
- **Repo**: `Bryan-cs/ValidumMultiEmpresa` (privado), rama `main`. Proyecto independiente de BBC prod.
- **Proyecto Railway**: `validum` (`us-east4`). Servicios: `validum-api`, `Postgres`, `Redis`,
  `bbc-daily` (`0 0 * * *`), `bbc-monthly` (`0 6 1 * *`). Bucket S3: `validum-docs` (región `iad`).
  El deploy es automático con cada push a `main` (deployment trigger de GitHub).
- **Frontend**: proyecto Vercel `validum-frontend` → `https://validum-frontend.vercel.app`.
  `VITE_API_URL` se hornea en build time: **cambiarla exige redesplegar**, no basta con setearla.

## Credenciales dev por defecto
- Superadmin: `superadmin / superadmin1234` (solo dev/SQLite; en prod se define con `SUPERADMIN_USER/PASS`)
- Los admin/empleado de cada organización se crean desde el panel del superadmin.
