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
# API docs: http://localhost:8000/docs
```

### Frontend
```bash
cd bbcfile/frontend
npm install
npm start          # Dev server → http://localhost:3000
npm run build      # Build de producción
```

## Architecture

### Backend (`bbcfile/backend/`)

**Archivos principales:**
- **`main.py`** — FastAPI app; incluye 9 routers + endpoints directos para eliminados, retiros, empleados, gastos, nómina, usuarios, config, dashboard, cobro, actividad, listas y clientes. Rate limiting con SlowAPI, headers de seguridad, CORS `allow_origins=["*"]`.
- **`crud.py`** — Toda la lógica de negocio (~1100 líneas). Cálculos de aportes de seguridad social colombiana (EPS, AFP, ARL, CCF, SENA, ICBF). Caché Redis en producción / dict en memoria para dev.
- **`models.py`** — 17 modelos ORM: `Usuario`, `Afiliado`, `Factura`, `Retiro`, `Eliminado`, `Empleado`, `Gasto`, `NominaMensual`, `Config`, `Lista`, `SolicitudNovedad`, `NovedadPago`, `SolicitudRetiro`, `Actividad`, `Tarea`, `TareaComentario`, `LoginAttempt`, `Notificacion`, `PlanillaPago`, `Documento`.
- **`schemas.py`** — Pydantic v2 schemas.
- **`database.py`** — SQLAlchemy; auto-crea tablas con `init_db()`; auto-migra URLs SQLite → PostgreSQL.
- **`logger.py`** — Logging estructurado.

**Routers (`backend/routers/`):**
- `auth.py` — Login, JWT, bloqueo por intentos fallidos.
- `afiliados.py` — CRUD afiliados con paginación y filtros avanzados.
- `facturas.py` — Facturación, pago, generación PDF.
- `reportes.py` — Exportaciones Excel y PDF.
- `tareas.py` — Módulo de tareas internas con comentarios y notificaciones.
- `portal.py` — Portal del cliente: solicitudes de novedad/retiro, novedades de pago.
- `documentos.py` — Subida/descarga de archivos; almacenamiento en Cloudflare R2 (producción) o disco local (dev).
- `backups.py` — Backups de base de datos.
- `planillas.py` — Planillas de pago de seguridad social por cliente.

**Auth:** JWT HS256, tokens de 12 horas, roles: `admin` | `empleado` | `cliente`.

**Soft deletes:** Afiliados eliminados → tabla `Eliminado` (restaurable). Retiro eliminado → afiliado pasa a `Eliminado` (no reactivar).

**Audit trail:** Todas las mutaciones registradas en tabla `Actividad`.

**Caché:** Redis en producción (variable `REDIS_URL`), dict en memoria para dev. Prefijos: `cobro:`, `dashboard:`. Se invalida en operaciones que afectan cobro/dashboard.

**Estados de afiliado (`estado_srv`):** ACTIVO, SUSPENDIDO, RETIRADO, DOBLE_AFILIACION, NO_ENCONTRADO, EN_ESPERA.

### Frontend (`bbcfile/frontend/src/`)

**Archivos clave:**
- **`App.jsx`** — BrowserRouter, QueryClientProvider, rutas con `PrivateRoute` y `ClienteOnlyRoute`.
- **`utils/api.js`** — Axios con interceptor JWT (Zustand store).
- **`hooks/useAuth.js`** — Zustand: token, rol, login/logout.
- **`components/Layout.jsx`** — Sidebar + shell. Notificaciones en tiempo real (polling cada 30s) con sonido Web Audio API al llegar nuevas.
- **`components/UI.jsx`** — Design system propio (sin librería externa). Exports: `C` (colores), `StatCard`, `Btn`, `fmt`, etc.
- **`components/FiltroCheck.jsx`** — Dropdown de filtros múltiples reutilizable.

**Páginas (`pages/`):**

| Ruta | Página | Acceso |
|---|---|---|
| `/afiliados` | `Afiliados.jsx` | Todos |
| `/retiros` | `Retiros.jsx` + `Pages.jsx` | Todos |
| `/tareas` | `Tareas.jsx` | Todos |
| `/facturacion` | `Facturacion.jsx` | Todos |
| `/cobro` | `Cobro.jsx` | Todos |
| `/planillas-ss` | `PlanillasSS.jsx` | Todos |
| `/empleados` | `Empleados.jsx` | Admin |
| `/usuarios` | `Usuarios.jsx` | Admin |
| `/listas` | `Listas.jsx` | Admin |
| `/calculadora` | `Calculadora.jsx` | Admin |
| `/actividad` | `Actividad.jsx` | Admin |
| `/novedades-clientes` | `NovedadesClientes.jsx` | Admin |
| `/backups` | `Backups.jsx` | Admin |
| `/portal` | `PortalCliente.jsx` | Cliente |

**Dashboard (`Dashboard.jsx`):** Filtros por año y mes. Cards de afiliados (Activos, Suspendidos, Doble afiliación, No se encuentra, En espera activac., Total). Cards financieras (Facturas, Ingresos, Pendiente período, ⚠ Pendiente total all-time, Nóminas, Gastos fijos, Utilidad neta). Refetch cada 2 minutos.

**Cobro (`Cobro.jsx`):** Solo muestra afiliados con cobro hoy (COBRAR_HOY) o mañana (PROXIMO). No carga días futuros.

**Retiros (`Pages.jsx`):** Tab "📋 Consultar retiro" — búsqueda bajo demanda por número de documento (no carga historial automáticamente). Eliminar retiro mueve el afiliado a Eliminados.

**Afiliados → tab Eliminados:** Botones: ↩ Restaurar | 📋 → Retiros | 🗑️ Borrar. "→ Retiros" crea un registro en historial de retiros desde el eliminado.

**Stack:**
- React 18.3, React Router 6, TanStack React Query 5, Zustand 5, Axios, Recharts, React Hot Toast, React Icons, Tailwind CSS 3.

### Data Flow
```
React Page → Axios (api.js) → FastAPI (main.py) → crud.py → SQLAlchemy → PostgreSQL
                ↑                                      ↑
        Zustand (auth)                         Redis cache (prod)
        React Query (cache)
```

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | SQLite (`bbcfile.db`) en dev |
| `SECRET_KEY` | JWT signing key | Key hardcoded dev — **cambiar en prod** |
| `PORT` | Puerto del servidor | 8000 |
| `REDIS_URL` | Redis para caché | Sin Redis = caché en memoria |
| `STORAGE_BUCKET` | Bucket Cloudflare R2 | Sin bucket = disco local |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credenciales R2 | — |
| `R2_ENDPOINT_URL` | Endpoint R2 | — |

## Deployment

- **Backend**: Railway (`Procfile`: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`)
- **Frontend**: Vercel
- **Almacenamiento de archivos**: Cloudflare R2
- **Base de datos**: PostgreSQL en Railway
- **Git workflow**: commits y push a `dev` por defecto. Solo push a `main` cuando se indique explícitamente ("push a main").

## Credenciales dev por defecto
- `admin / admin1234`
- `empleado1 / emp1234`

## Agents Team

BBC File tiene un equipo de 8 agentes especializados orquestados por la sesión principal de Claude Code. Los prompts de cada agente están en `bbcfile/.claude/agents/`.

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

**Regla:** Si puedes hacerlo directo en menos tiempo del que tarda el pipeline de agentes, hazlo directo. Los agentes son para calidad y paralelismo en trabajo complejo, no un modo por defecto.

### Agentes disponibles

| Agente | Archivo | Rol |
|---|---|---|
| `bbc-explorer` | `.claude/agents/bbc-explorer.md` | Exploración read-only del codebase |
| `bbc-architect` | `.claude/agents/bbc-architect.md` | Revisión arquitectónica antes de implementar |
| `bbc-planner` | `.claude/agents/bbc-planner.md` | Descomposición de tareas con dependencias |
| `bbc-db` | `.claude/agents/bbc-db.md` | Modelos SQLAlchemy + migraciones Alembic |
| `bbc-backend` | `.claude/agents/bbc-backend.md` | FastAPI, crud.py, routers |
| `bbc-frontend` | `.claude/agents/bbc-frontend.md` | React pages, TanStack Query |
| `bbc-domain-reviewer` | `.claude/agents/bbc-domain-reviewer.md` | Validación de lógica de negocio SS colombiana |
| `bbc-reviewer` | `.claude/agents/bbc-reviewer.md` | Revisión de calidad y bugs |
| `bbc-tester` | `.claude/agents/bbc-tester.md` | Tests pytest (SQLite + PostgreSQL integración) |
| `bbc-changelog` | `.claude/agents/bbc-changelog.md` | Actualización Obsidian |

### Cómo despachar un agente

El orquestador lee el skill + _shared-context antes de despachar:

```python
# Pseudocódigo — el orquestador (sesión principal) hace esto antes de cada Agent() call:
shared = Read(".claude/agents/_shared-context.md")
skill  = Read(".claude/agents/bbc-backend.md")  # o el agente que corresponda

Agent(
  description="Implementar endpoint GET /nuevo-modulo",
  prompt=f"{shared}\n\n{skill}\n\n## Tarea\n{tarea}\n\n## Context del Explorer\n{handoff_explorer}"
)
```

### Hot Context Injection

Antes de despachar el primer agente de cualquier tarea, leer:
1. Últimas 2 entradas de `Changelog.md` en Obsidian Vault
2. Nota del módulo afectado en `Obsidian Vault/BBC File/Módulos/`

### Estrategias de ejecución

```
Bug simple:             explorer → [backend|frontend] → domain-reviewer? → reviewer
Feature con endpoint:   explorer → architect → planner → db? → backend → domain-reviewer? → frontend → reviewer → tester → changelog
Feature solo frontend:  explorer → planner → frontend → reviewer → changelog
Feature paralela:       explorer → architect → planner → backend ∥ frontend (worktrees) → domain-reviewer? → reviewer → tester → changelog
Auditoría:              explorer → backend + frontend (paralelo) → domain-reviewer → reviewer
Cambio SS/facturación:  explorer → architect → planner → backend → domain-reviewer → reviewer → tester → changelog
```

`domain-reviewer` es obligatorio cuando la tarea toca: cálculos SS, estados de factura, cobro, planillas, ingresos/utilidad.
`architect` es obligatorio cuando la tarea toca: nuevo modelo, nuevo endpoint, cambio en auth, lógica de caché.

### Spec completo
Ver: `docs/superpowers/specs/2026-04-17-bbc-agents-team-design.md`
