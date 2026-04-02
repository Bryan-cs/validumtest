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
