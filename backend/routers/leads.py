"""Proxy de solo lectura a la API de Laura (agente de ventas Messenger).

Laura corre como microservicio aparte (Node/Express en Railway). Este router
expone sus datos a BBC File manteniendo la ADMIN_KEY en el servidor (nunca llega
al browser) y protegiendo el acceso con la auth de BBC.

Config (env vars):
  LAURA_API_URL   — ej. https://laura-production-e5fe.up.railway.app
  LAURA_ADMIN_KEY — la ADMIN_KEY del panel de Laura
"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from .deps import require_admin_or_empleado

router = APIRouter(prefix="/leads", tags=["leads"])

LAURA_API_URL = os.getenv("LAURA_API_URL", "").rstrip("/")
LAURA_ADMIN_KEY = os.getenv("LAURA_ADMIN_KEY", "")


def _check_config():
    if not LAURA_API_URL or not LAURA_ADMIN_KEY:
        raise HTTPException(503, "Laura no configurada (faltan LAURA_API_URL / LAURA_ADMIN_KEY)")


async def _laura_request(method: str, path: str, params: dict | None = None):
    _check_config()
    p = {"key": LAURA_ADMIN_KEY, **(params or {})}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.request(method, f"{LAURA_API_URL}{path}", params=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Laura respondió {e.response.status_code}")
    except httpx.HTTPError:
        raise HTTPException(502, "No se pudo contactar a Laura")


@router.get("/stats")
async def leads_stats(token=Depends(require_admin_or_empleado)):
    """Métricas agregadas de leads (totales, por estado, serie 14d, etc.)."""
    return await _laura_request("GET", "/admin/stats")


@router.get("/list")
async def leads_list(limit: int = Query(100, ge=1, le=100), token=Depends(require_admin_or_empleado)):
    """Últimos prospectos con su página de origen."""
    return await _laura_request("GET", "/admin/leads", {"limit": limit})


@router.post("/estado")
async def leads_set_estado(id: int, estado: str, token=Depends(require_admin_or_empleado)):
    """Cambia el estado de un prospecto (nuevo/interesado/caliente/cerrado)."""
    if estado not in ("nuevo", "interesado", "caliente", "cerrado"):
        raise HTTPException(400, "estado inválido")
    return await _laura_request("POST", "/admin/lead-estado", {"id": id, "estado": estado})
