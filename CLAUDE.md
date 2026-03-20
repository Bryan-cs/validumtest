# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BBC File** — Sistema de gestión de personal y seguridad social (Colombian employee benefits & social security management system). Full-stack app with React 18 frontend + FastAPI backend.

## Development Commands

### Backend
```bash
cd bbcfile/backend
pip install -r requirements.txt
uvicorn main:app --reload        # Dev server at http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Frontend
```bash
cd bbcfile/frontend
npm install
npm start          # Dev server at http://localhost:3000
npm run build      # Production build
npm test           # Run tests
```

## Architecture

### Backend (`bbcfile/backend/`)
- **`main.py`** — FastAPI app with 14 route groups, JWT auth via `HTTPBearer`, CORS `allow_origins=["*"]`
- **`database.py`** — SQLAlchemy setup; auto-creates tables on first run via `init_db()`; auto-migrates SQLite URLs to PostgreSQL format
- **`models.py`** — ORM models: Afiliado, Factura, Retiro, Empleado, Gasto, Usuario, Actividad, Eliminado, Config, and list tables (Empresa, Eps, Arl, Ccf, Afp, Banco)
- **`schemas.py`** — Pydantic v2 request/response schemas
- **`crud.py`** — All business logic and DB operations (~600 lines); Colombian social security contribution calculations (EPS, AFP, ARL, CCF, SENA, ICBF rates)

**Auth**: JWT HS256, 12-hour tokens, roles: `admin` | `empleado`
**Soft deletes**: Deleted affiliates move to `Eliminado` table for restoration
**Audit trail**: All mutations logged to `Actividad` table

### Frontend (`bbcfile/frontend/src/`)
- **`App.jsx`** — BrowserRouter, QueryClientProvider, route definitions with `PrivateRoute` wrapper
- **`utils/api.js`** — Axios instance with JWT token interceptor (reads from Zustand store)
- **`hooks/useAuth.js`** — Zustand auth store (token, user role, login/logout)
- **`components/Layout.jsx`** — Sidebar + main layout shell
- **`components/UI.jsx`** — Custom design system (no external component library)
- **`pages/`** — One file per route: Login, Dashboard, Afiliados, Facturacion, Cobro, Retiros, Empleados, Usuarios, Listas, Calculadora

**Data fetching**: TanStack React Query for server state
**Styling**: Tailwind CSS
**Admin-only routes**: Wrapped with `RequireAdmin` component

### Data Flow
```
React Page → Axios (api.js) → FastAPI (main.py) → crud.py → SQLAlchemy → DB
                ↑
        Zustand (auth token) + React Query (cache)
```

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | SQLite (`bbcfile.db`) in dev |
| `SECRET_KEY` | JWT signing key | Hardcoded dev key in `main.py` — **change in prod** |
| `PORT` | Server port | 8000 |

## Deployment

- **Backend**: Railway (uses `Procfile`: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`)
- **Frontend**: Netlify or Railway static hosting
- See `DEPLOY.md` for full step-by-step Railway + Netlify setup guide
- Default dev credentials: `admin/admin1234`, `empleado1/emp1234`
