# backend/routers/chat.py
import asyncio
import json
import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from database import get_db, SessionLocal
import models
from routers.deps import verify_token, require_admin, _decode_token
import jwt

router = APIRouter(tags=["chat"])

# ─── CONNECTION MANAGER ─────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        # canal -> lista de websockets
        self._conns: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, canal: str):
        await ws.accept()
        self._conns.setdefault(canal, []).append(ws)

    def disconnect(self, ws: WebSocket, canal: str):
        conns = self._conns.get(canal, [])
        self._conns[canal] = [w for w in conns if w is not ws]

    async def broadcast(self, canal: str, data: dict):
        for ws in list(self._conns.get(canal, [])):
            try:
                await ws.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()

# ─── REDIS PUB/SUB ──────────────────────────────────────────────────────────
_REDIS_URL = os.getenv("REDIS_URL")
_pubsub_task: asyncio.Task | None = None

async def _escuchar_redis():
    """Tarea de fondo: escucha canales chat:* en Redis y reenvía a WS locales."""
    if not _REDIS_URL:
        return
    import redis.asyncio as aioredis
    r = aioredis.from_url(_REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.psubscribe("chat:*")
    try:
        async for raw in pubsub.listen():
            if raw["type"] != "pmessage":
                continue
            canal = raw["channel"]
            try:
                data = json.loads(raw["data"])
            except Exception:
                continue
            await manager.broadcast(canal, data)
    finally:
        await pubsub.aclose()
        await r.aclose()

async def _publicar(canal: str, data: dict):
    """Publica en Redis; si no hay Redis hace broadcast directo (1 worker)."""
    if not _REDIS_URL:
        await manager.broadcast(canal, data)
        return
    import redis.asyncio as aioredis
    r = aioredis.from_url(_REDIS_URL, decode_responses=True)
    try:
        await r.publish(canal, json.dumps(data, default=str))
    finally:
        await r.aclose()

def iniciar_listener():
    global _pubsub_task
    if _REDIS_URL and _pubsub_task is None:
        _pubsub_task = asyncio.create_task(_escuchar_redis())

def detener_listener():
    global _pubsub_task
    if _pubsub_task:
        _pubsub_task.cancel()
        _pubsub_task = None

# ─── HELPERS ────────────────────────────────────────────────────────────────
CANAL_GRUPAL = "chat:grupal"

def _canal_privado(cliente_ref: str) -> str:
    return f"chat:privado:{cliente_ref}"

def _to_dict(m: models.Mensaje) -> dict:
    return {
        "id":               m.id,
        "tipo":             m.tipo,
        "remitente":        m.remitente,
        "remitente_nombre": m.remitente_nombre,
        "destinatario":     m.destinatario,
        "texto":            m.texto,
        "creado":           m.creado.isoformat() if m.creado else None,
        "leido":            m.leido,
    }

# ─── REST ENDPOINTS ─────────────────────────────────────────────────────────
@router.get("/chat/mensajes")
def get_mensajes(
    tipo: str = Query("grupal"),
    cliente_ref: str | None = Query(None),
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    rol = payload.get("rol")
    if tipo == "grupal":
        if rol not in ("admin", "empleado"):
            raise HTTPException(403, "Acceso denegado al canal grupal")
        q = db.query(models.Mensaje).filter(models.Mensaje.tipo == "grupal")
    elif tipo == "privado":
        # cliente solo ve su propia conversación (cliente_ref del token)
        if rol == "cliente":
            cliente_ref = payload.get("cliente_ref")
        if not cliente_ref:
            raise HTTPException(400, "cliente_ref requerido para tipo=privado")
        q = db.query(models.Mensaje).filter(
            models.Mensaje.tipo == "privado",
            models.Mensaje.destinatario == cliente_ref,
        )
    else:
        raise HTTPException(400, "tipo inválido")
    msgs = q.order_by(models.Mensaje.creado.asc()).limit(100).all()
    return [_to_dict(m) for m in msgs]


@router.get("/chat/clientes-activos")
def get_clientes_activos(
    payload=Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            models.Mensaje.destinatario,
            func.count(models.Mensaje.id).label("total"),
            func.sum(
                case((models.Mensaje.leido == False, 1), else_=0)
            ).label("no_leidos"),
        )
        .filter(models.Mensaje.tipo == "privado")
        .group_by(models.Mensaje.destinatario)
        .all()
    )
    return [
        {"cliente_ref": r.destinatario, "total": r.total, "no_leidos": int(r.no_leidos or 0)}
        for r in rows
    ]


@router.get("/chat/no-leidos")
def get_no_leidos(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    if payload.get("rol") != "admin":
        return {"count": 0}
    count = db.query(models.Mensaje).filter(
        models.Mensaje.tipo == "privado",
        models.Mensaje.leido == False,
    ).count()
    return {"count": count}


@router.put("/chat/mensajes/{cliente_ref}/leer")
def marcar_leidos(
    cliente_ref: str,
    payload=Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.query(models.Mensaje).filter(
        models.Mensaje.tipo == "privado",
        models.Mensaje.destinatario == cliente_ref,
        models.Mensaje.leido == False,
    ).update({"leido": True})
    db.commit()
    return {"ok": True}


# ─── WEBSOCKET ───────────────────────────────────────────────────────────────
@router.websocket("/ws/chat")
async def ws_chat(
    ws: WebSocket,
    token: str = Query(...),
    tipo: str = Query("grupal"),
    cliente_ref: str | None = Query(None),
):
    # Verificar token (no se puede usar Depends en WebSocket)
    try:
        payload = _decode_token(token)
    except Exception:
        await ws.close(code=1008)
        return

    username = payload.get("sub")
    nombre   = payload.get("nombre") or username
    rol      = payload.get("rol")

    # Determinar canal y destinatario
    if tipo == "privado":
        if rol == "cliente":
            ref = payload.get("cliente_ref")
        elif rol == "admin" and cliente_ref:
            ref = cliente_ref
        else:
            await ws.close(code=1008)
            return
        canal = _canal_privado(ref)
    else:
        ref = None
        canal = CANAL_GRUPAL

    await manager.connect(ws, canal)
    try:
        while True:
            data = await ws.receive_json()
            texto = (data.get("texto") or "").strip()
            if not texto:
                continue

            # Guardar en DB
            db = SessionLocal()
            try:
                msg = models.Mensaje(
                    tipo=tipo,
                    remitente=username,
                    remitente_nombre=nombre,
                    destinatario=ref,
                    texto=texto,
                )
                db.add(msg)
                db.commit()
                db.refresh(msg)
                msg_dict = _to_dict(msg)
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

            await _publicar(canal, msg_dict)

    except WebSocketDisconnect:
        manager.disconnect(ws, canal)
    except Exception as exc:
        from logger import logger as _log
        _log.error(f"ws_chat error (canal={canal}, user={username}): {exc}", exc_info=True)
        manager.disconnect(ws, canal)
