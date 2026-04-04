# Chat Tiempo Real — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar chat en tiempo real con dos canales: grupo interno (admin + empleados) y conversaciones 1-a-1 entre admin y clientes del portal.

**Architecture:** WebSockets nativos de FastAPI para transporte en tiempo real; Redis pub/sub (`redis.asyncio`) para sincronizar mensajes entre múltiples workers de uvicorn. Historial persistido en PostgreSQL con el modelo `Mensaje`. El frontend usa la WebSocket API nativa del browser sin librerías externas.

**Tech Stack:** FastAPI WebSockets, `redis.asyncio` (ya en requirements), SQLAlchemy, React 18, WebSocket API nativa

---

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `backend/models.py` | Modificar | Agregar modelo `Mensaje` |
| `backend/routers/chat.py` | Crear | Manager WS, pub/sub Redis, endpoints REST + WS |
| `backend/main.py` | Modificar | Registrar router chat |
| `frontend/src/pages/Chat.jsx` | Crear | UI de chat para admin y empleados |
| `frontend/src/pages/PortalCliente.jsx` | Modificar | Panel de chat 1-a-1 para clientes |
| `frontend/src/components/Layout.jsx` | Modificar | Nav item + badge de no leídos |
| `frontend/src/pages/App.jsx` | Modificar | Ruta `/chat` |

---

### Task 1: Modelo `Mensaje` en models.py

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1: Agregar el modelo al final de models.py, antes del último import**

Abrir `backend/models.py` y agregar al final del archivo:

```python
class Mensaje(Base):
    __tablename__ = "mensajes"
    __table_args__ = (
        Index('ix_mensaje_tipo_creado', 'tipo', 'creado'),
        Index('ix_mensaje_destinatario', 'destinatario', 'leido'),
    )
    id                = Column(Integer, primary_key=True, index=True)
    tipo              = Column(String(10), index=True)       # grupal | privado
    remitente         = Column(String(60), index=True)       # username
    remitente_nombre  = Column(String(120))
    destinatario      = Column(String(120), nullable=True)   # cliente_ref (solo privado)
    texto             = Column(Text)
    creado            = Column(DateTime, default=_utcnow, index=True)
    leido             = Column(Boolean, default=False)       # para mensajes privados
```

- [ ] **Step 2: Verificar que la tabla se crea automáticamente**

```bash
cd backend
python -c "from database import init_db; init_db(); print('OK')"
```
Esperado: `OK` sin errores

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "feat(chat): agregar modelo Mensaje"
```

---

### Task 2: Router `backend/routers/chat.py`

**Files:**
- Create: `backend/routers/chat.py`

Este router contiene:
- `ConnectionManager`: gestiona conexiones WS activas por canal
- `redis_listener`: tarea async que escucha pub/sub y reenvía a WS conectados
- `GET /chat/mensajes`: historial (últimos 100 mensajes)
- `GET /chat/clientes-activos`: admin only, lista clientes con count de no leídos
- `PUT /chat/mensajes/{cliente_ref}/leer`: marcar mensajes privados como leídos
- `GET /chat/no-leidos`: count de mensajes privados no leídos (para badge admin)
- `WebSocket /ws/chat`: conexión principal

- [ ] **Step 1: Crear el archivo**

```python
# backend/routers/chat.py
import asyncio
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
import models
from routers.deps import verify_token, require_admin

router = APIRouter(tags=["chat"])

# ─── MANAGER DE CONEXIONES ──────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        # canal -> lista de (websocket, username)
        self._connections: dict[str, list[tuple[WebSocket, str]]] = {}

    async def connect(self, ws: WebSocket, canal: str, username: str):
        await ws.accept()
        self._connections.setdefault(canal, []).append((ws, username))

    def disconnect(self, ws: WebSocket, canal: str):
        conns = self._connections.get(canal, [])
        self._connections[canal] = [(w, u) for w, u in conns if w is not ws]

    async def broadcast_canal(self, canal: str, data: dict):
        for ws, _ in list(self._connections.get(canal, [])):
            try:
                await ws.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()

# ─── REDIS PUB/SUB ──────────────────────────────────────────────────────────
_redis_url = os.getenv("REDIS_URL")
_pubsub_task: asyncio.Task | None = None

async def _escuchar_redis():
    """Tarea de fondo: escucha todos los canales de chat en Redis y reenvía a WS."""
    if not _redis_url:
        return
    import redis.asyncio as aioredis
    r = aioredis.from_url(_redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.psubscribe("chat:*")  # suscripción a todos los canales chat:*
    try:
        async for raw in pubsub.listen():
            if raw["type"] not in ("message", "pmessage"):
                continue
            canal = raw.get("channel") or raw.get("pattern")
            # para pmessage el canal real viene en "channel"
            if raw["type"] == "pmessage":
                canal = raw["channel"]
            try:
                data = json.loads(raw["data"])
            except Exception:
                continue
            await manager.broadcast_canal(canal, data)
    finally:
        await pubsub.close()
        await r.aclose()

async def _publicar_redis(canal: str, data: dict):
    """Publica un mensaje en Redis pub/sub."""
    if not _redis_url:
        # sin Redis: broadcast directo (solo funciona con 1 worker)
        await manager.broadcast_canal(canal, data)
        return
    import redis.asyncio as aioredis
    r = aioredis.from_url(_redis_url, decode_responses=True)
    try:
        await r.publish(canal, json.dumps(data, default=str))
    finally:
        await r.aclose()

def iniciar_listener():
    """Llamar desde el lifespan de la app para iniciar el listener Redis."""
    global _pubsub_task
    if _redis_url and _pubsub_task is None:
        _pubsub_task = asyncio.create_task(_escuchar_redis())

def detener_listener():
    global _pubsub_task
    if _pubsub_task:
        _pubsub_task.cancel()
        _pubsub_task = None

# ─── HELPERS ────────────────────────────────────────────────────────────────
def _canal_privado(cliente_ref: str) -> str:
    return f"chat:privado:{cliente_ref}"

CANAL_GRUPAL = "chat:grupal"

def _msg_to_dict(m: models.Mensaje) -> dict:
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
    tipo: str = Query("grupal"),               # grupal | privado
    cliente_ref: str | None = Query(None),     # requerido si tipo=privado
    limit: int = Query(100, le=200),
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    rol = payload.get("rol")
    username = payload.get("sub")

    if tipo == "grupal":
        q = db.query(models.Mensaje).filter(models.Mensaje.tipo == "grupal")
    elif tipo == "privado":
        if not cliente_ref:
            raise HTTPException(400, "cliente_ref requerido para tipo=privado")
        # admin ve la conversación con cualquier cliente; cliente solo la suya
        if rol == "cliente":
            cliente_ref = payload.get("cliente_ref")
        q = db.query(models.Mensaje).filter(
            models.Mensaje.tipo == "privado",
            models.Mensaje.destinatario == cliente_ref,
        )
    else:
        raise HTTPException(400, "tipo inválido")

    mensajes = q.order_by(models.Mensaje.creado.asc()).limit(limit).all()
    return [_msg_to_dict(m) for m in mensajes]


@router.get("/chat/clientes-activos")
def get_clientes_activos(
    payload=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: lista de clientes que tienen al menos un mensaje privado, con count de no leídos."""
    from sqlalchemy import func
    rows = (
        db.query(
            models.Mensaje.destinatario,
            func.count(models.Mensaje.id).label("total"),
            func.sum((~models.Mensaje.leido).cast(models.Mensaje.leido.property.columns[0].type)).label("no_leidos"),
        )
        .filter(models.Mensaje.tipo == "privado")
        .group_by(models.Mensaje.destinatario)
        .all()
    )
    return [{"cliente_ref": r.destinatario, "total": r.total, "no_leidos": int(r.no_leidos or 0)} for r in rows]


@router.put("/chat/mensajes/{cliente_ref}/leer")
def marcar_leidos(
    cliente_ref: str,
    payload=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin marca como leídos los mensajes privados de un cliente."""
    db.query(models.Mensaje).filter(
        models.Mensaje.tipo == "privado",
        models.Mensaje.destinatario == cliente_ref,
        models.Mensaje.leido == False,
    ).update({"leido": True})
    db.commit()
    return {"ok": True}


@router.get("/chat/no-leidos")
def get_no_leidos(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Count de mensajes privados no leídos (para badge en sidebar, admin only)."""
    rol = payload.get("rol")
    if rol != "admin":
        return {"count": 0}
    count = db.query(models.Mensaje).filter(
        models.Mensaje.tipo == "privado",
        models.Mensaje.leido == False,
    ).count()
    return {"count": count}


# ─── WEBSOCKET ───────────────────────────────────────────────────────────────
@router.websocket("/ws/chat")
async def ws_chat(
    ws: WebSocket,
    token: str = Query(...),
    tipo: str = Query("grupal"),          # grupal | privado
    cliente_ref: str | None = Query(None),
):
    # Verificar token manualmente (no usa Depends en WS)
    from routers.deps import _decode_token
    try:
        payload = _decode_token(token)
    except Exception:
        await ws.close(code=1008)
        return

    username = payload.get("sub")
    nombre   = payload.get("nombre") or username
    rol      = payload.get("rol")

    # Determinar canal
    if tipo == "privado":
        if rol == "cliente":
            canal_ref = payload.get("cliente_ref")
        elif rol == "admin" and cliente_ref:
            canal_ref = cliente_ref
        else:
            await ws.close(code=1008)
            return
        canal = _canal_privado(canal_ref)
    else:
        canal = CANAL_GRUPAL
        canal_ref = None

    await manager.connect(ws, canal, username)
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
                    destinatario=canal_ref,
                    texto=texto,
                )
                db.add(msg)
                db.commit()
                db.refresh(msg)
                msg_dict = _msg_to_dict(msg)
            finally:
                db.close()

            # Publicar en Redis (o broadcast directo si no hay Redis)
            await _publicar_redis(canal, msg_dict)

    except WebSocketDisconnect:
        manager.disconnect(ws, canal)
    except Exception:
        manager.disconnect(ws, canal)
```

- [ ] **Step 2: Verificar que el archivo no tiene errores de sintaxis**

```bash
cd backend
python -c "import routers.chat; print('OK')"
```
Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/routers/chat.py
git commit -m "feat(chat): router WebSocket + REST endpoints"
```

---

### Task 3: Exponer `_decode_token` en deps.py y registrar router en main.py

**Files:**
- Modify: `backend/routers/deps.py`
- Modify: `backend/main.py`

El WebSocket del task 2 necesita llamar `_decode_token` directamente (sin `Depends`). Además hay que arrancar el listener Redis en el lifespan.

- [ ] **Step 1: Agregar `_decode_token` en deps.py**

Leer `backend/routers/deps.py` y encontrar donde está la lógica de decode del token (la función `verify_token`). Extraer el decode a una función separada:

```python
# Agregar antes de verify_token:
def _decode_token(token: str) -> dict:
    """Decodifica y valida un JWT. Lanza excepción si inválido."""
    import jwt as _jwt
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    return _jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
```

Y en `verify_token`, reemplazar la lógica de decode con una llamada a `_decode_token`:

```python
def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ", 1)[1]
    try:
        payload = _decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    return payload
```

- [ ] **Step 2: Verificar deps.py**

```bash
cd backend
python -c "from routers.deps import verify_token, _decode_token; print('OK')"
```
Esperado: `OK`

- [ ] **Step 3: Registrar el router y el listener en main.py**

En `backend/main.py`, agregar el import del router junto a los demás imports de routers:

```python
from routers.chat import router as chat_router, iniciar_listener, detener_listener
```

En la función `lifespan` (ya existente), agregar dentro del bloque `async with` antes del `yield`:

```python
    iniciar_listener()
```

Y después del `yield`:

```python
    detener_listener()
```

Registrar el router con los demás `app.include_router(...)`:

```python
app.include_router(chat_router)
```

- [ ] **Step 4: Verificar que el servidor arranca**

```bash
cd backend
uvicorn main:app --port 8001 --reload &
sleep 3
curl http://localhost:8001/docs | grep -c "chat" && kill %1
```
Esperado: número > 0 (confirma que los endpoints /chat/* aparecen en docs)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/deps.py backend/main.py
git commit -m "feat(chat): registrar router y listener Redis en lifespan"
```

---

### Task 4: `frontend/src/pages/Chat.jsx` — UI para admin y empleados

**Files:**
- Create: `frontend/src/pages/Chat.jsx`

Esta página tiene:
- Admin: panel izquierdo con tabs "Interno" (grupo) y "Clientes" (lista de conversaciones privadas). Al seleccionar un cliente, el panel derecho muestra esa conversación.
- Empleado: solo el chat grupal.
- Conexión WS nativa. Al enviar mensaje se escribe en el WS. Al recibir mensaje se agrega a la lista.
- Historial cargado via REST al montar/cambiar canal.

- [ ] **Step 1: Crear Chat.jsx**

```jsx
// frontend/src/pages/Chat.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { C } from '../components/UI';

const WS_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws');

export default function Chat() {
  const { user, token } = useAuthStore();
  const isAdmin = user?.rol === 'admin';
  const qc = useQueryClient();

  // ── Estado ─────────────────────────────────────────────────────────────
  const [tab, setTab] = useState('grupal');              // 'grupal' | 'privado'
  const [clienteActivo, setClienteActivo] = useState(null); // cliente_ref seleccionado
  const [mensajes, setMensajes] = useState([]);
  const [texto, setTexto] = useState('');
  const wsRef = useRef(null);
  const bottomRef = useRef(null);

  // ── Clientes activos (admin) ────────────────────────────────────────────
  const { data: clientes = [] } = useQuery({
    queryKey: ['chat-clientes'],
    queryFn: () => api.get('/chat/clientes-activos').then(r => r.data),
    enabled: isAdmin,
    refetchInterval: 30_000,
  });

  // ── Cargar historial ────────────────────────────────────────────────────
  const cargarHistorial = useCallback(async (tipo, ref) => {
    const params = { tipo };
    if (tipo === 'privado' && ref) params.cliente_ref = ref;
    try {
      const res = await api.get('/chat/mensajes', { params });
      setMensajes(res.data);
    } catch (_) {}
  }, []);

  // ── Conexión WebSocket ──────────────────────────────────────────────────
  const conectarWS = useCallback((tipo, ref) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    let url = `${WS_BASE}/ws/chat?token=${token}&tipo=${tipo}`;
    if (tipo === 'privado' && ref) url += `&cliente_ref=${encodeURIComponent(ref)}`;
    const ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        setMensajes(prev => [...prev, msg]);
      } catch (_) {}
    };
    ws.onerror = () => {};
    wsRef.current = ws;
  }, [token]);

  // ── Efecto: cambio de canal ─────────────────────────────────────────────
  useEffect(() => {
    if (tab === 'grupal') {
      cargarHistorial('grupal', null);
      conectarWS('grupal', null);
    } else if (tab === 'privado' && clienteActivo) {
      cargarHistorial('privado', clienteActivo);
      conectarWS('privado', clienteActivo);
      // Marcar como leídos
      api.put(`/chat/mensajes/${clienteActivo}/leer`).then(() =>
        qc.invalidateQueries({ queryKey: ['chat-clientes'] })
      ).catch(() => {});
    }
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [tab, clienteActivo, cargarHistorial, conectarWS, qc]);

  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mensajes]);

  // ── Enviar mensaje ───────────────────────────────────────────────────────
  const enviar = () => {
    const t = texto.trim();
    if (!t || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ texto: t }));
    setTexto('');
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
  };

  // ── Helpers de UI ────────────────────────────────────────────────────────
  const fmtHora = (iso) => {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
  };

  const fmtFecha = (iso) => {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('es-CO', { day: '2-digit', month: 'short' });
  };

  // Agrupar mensajes por fecha para separadores
  const mensajesConFecha = mensajes.reduce((acc, m, i) => {
    const fecha = m.creado ? new Date(m.creado).toDateString() : '';
    const prevFecha = i > 0 && mensajes[i - 1].creado
      ? new Date(mensajes[i - 1].creado).toDateString() : '';
    if (fecha !== prevFecha) acc.push({ separador: true, fecha: fmtFecha(m.creado) });
    acc.push(m);
    return acc;
  }, []);

  const esMio = (m) => m.remitente === user?.username;

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 48px)', gap: 0, background: C.bg }}>

      {/* Sidebar izquierdo — solo admin */}
      {isAdmin && (
        <div style={{
          width: 240, flexShrink: 0, background: C.surface, borderRight: `1px solid ${C.border}`,
          display: 'flex', flexDirection: 'column',
        }}>
          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}` }}>
            {[['grupal', '👥 Interno'], ['privado', '💬 Clientes']].map(([id, label]) => (
              <button key={id} onClick={() => { setTab(id); if (id === 'grupal') setClienteActivo(null); }}
                style={{
                  flex: 1, padding: '12px 8px', border: 'none', fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', borderBottom: tab === id ? `2px solid ${C.primary}` : '2px solid transparent',
                  background: 'transparent', color: tab === id ? C.primary : C.text2,
                }}>
                {label}
              </button>
            ))}
          </div>

          {/* Lista de clientes */}
          {tab === 'privado' && (
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {clientes.length === 0 && (
                <p style={{ padding: 16, color: C.text2, fontSize: 12 }}>Sin conversaciones aún</p>
              )}
              {clientes.map(c => (
                <div key={c.cliente_ref}
                  onClick={() => setClienteActivo(c.cliente_ref)}
                  style={{
                    padding: '10px 14px', cursor: 'pointer', fontSize: 13,
                    background: clienteActivo === c.cliente_ref ? C.surface2 : 'transparent',
                    borderBottom: `1px solid ${C.border}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                  <span style={{ color: C.text, fontWeight: clienteActivo === c.cliente_ref ? 600 : 400 }}>
                    {c.cliente_ref}
                  </span>
                  {c.no_leidos > 0 && (
                    <span style={{
                      background: C.primary, color: '#fff', borderRadius: 10,
                      padding: '1px 7px', fontSize: 11, fontWeight: 700,
                    }}>
                      {c.no_leidos}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Chat grupal no tiene lista secundaria */}
          {tab === 'grupal' && (
            <div style={{ flex: 1, padding: '12px 14px' }}>
              <p style={{ color: C.text2, fontSize: 12, margin: 0 }}>
                Canal interno para admin y empleados.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Panel principal de chat */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Header */}
        <div style={{
          padding: '14px 20px', borderBottom: `1px solid ${C.border}`,
          background: C.surface, fontWeight: 700, fontSize: 14, color: C.text,
          flexShrink: 0,
        }}>
          {tab === 'grupal' ? '👥 Chat interno' : clienteActivo ? `💬 ${clienteActivo}` : 'Selecciona un cliente'}
        </div>

        {/* Mensajes */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {(tab === 'privado' && !clienteActivo) ? (
            <p style={{ color: C.text2, textAlign: 'center', marginTop: 40, fontSize: 13 }}>
              Selecciona un cliente para ver la conversación
            </p>
          ) : mensajesConFecha.length === 0 ? (
            <p style={{ color: C.text2, textAlign: 'center', marginTop: 40, fontSize: 13 }}>
              Sin mensajes aún
            </p>
          ) : mensajesConFecha.map((item, i) => {
            if (item.separador) return (
              <div key={`sep-${i}`} style={{ textAlign: 'center', margin: '8px 0' }}>
                <span style={{ background: C.surface2, color: C.text2, borderRadius: 10, padding: '2px 12px', fontSize: 11 }}>
                  {item.fecha}
                </span>
              </div>
            );
            const mio = esMio(item);
            return (
              <div key={item.id} style={{
                display: 'flex', flexDirection: 'column',
                alignItems: mio ? 'flex-end' : 'flex-start',
                marginBottom: 2,
              }}>
                {!mio && (
                  <span style={{ fontSize: 11, color: C.text2, marginBottom: 2, marginLeft: 2 }}>
                    {item.remitente_nombre}
                  </span>
                )}
                <div style={{
                  maxWidth: '72%', padding: '8px 12px', borderRadius: mio ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                  background: mio ? C.primary : C.surface2,
                  color: mio ? '#fff' : C.text,
                  fontSize: 13, lineHeight: 1.45, wordBreak: 'break-word',
                }}>
                  {item.texto}
                </div>
                <span style={{ fontSize: 10, color: C.text2, marginTop: 2, marginLeft: 2, marginRight: 2 }}>
                  {fmtHora(item.creado)}
                </span>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        {(tab === 'grupal' || (tab === 'privado' && clienteActivo)) && (
          <div style={{
            padding: '12px 16px', borderTop: `1px solid ${C.border}`,
            background: C.surface, display: 'flex', gap: 8, flexShrink: 0,
          }}>
            <textarea
              value={texto}
              onChange={e => setTexto(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Escribe un mensaje… (Enter para enviar)"
              style={{
                flex: 1, padding: '9px 12px', border: `1px solid ${C.border}`,
                borderRadius: 8, fontSize: 13, color: C.text, background: C.bg,
                resize: 'none', outline: 'none', fontFamily: 'inherit',
              }}
            />
            <button onClick={enviar} style={{
              background: C.primary, border: 'none', color: '#fff',
              borderRadius: 8, padding: '0 18px', cursor: 'pointer', fontWeight: 700, fontSize: 18,
            }}>
              ➤
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Chat.jsx
git commit -m "feat(chat): página Chat.jsx para admin y empleados"
```

---

### Task 5: Panel de chat en `PortalCliente.jsx`

**Files:**
- Modify: `frontend/src/pages/PortalCliente.jsx`

El portal cliente necesita un panel de chat visible en la parte inferior de la pantalla (tipo widget flotante) o como tab adicional. Se implementa como tab dado que la página ya tiene navegación por tabs.

- [ ] **Step 1: Leer la estructura de tabs actual de PortalCliente.jsx**

Buscar en `frontend/src/pages/PortalCliente.jsx` el array/variable que define los tabs disponibles (buscar `tab`, `tabs`, `activeTab` o similar). La estructura exacta determinará dónde insertar el nuevo tab.

- [ ] **Step 2: Agregar hook de chat al componente principal**

Dentro del componente principal de `PortalCliente.jsx`, agregar después de los hooks existentes:

```jsx
// ── Chat 1-a-1 ────────────────────────────────────────────────────────────
const { token } = useAuthStore();
const WS_BASE_PORTAL = (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws');
const [chatMsgs, setChatMsgs] = useState([]);
const [chatTexto, setChatTexto] = useState('');
const wsPortalRef = useRef(null);
const chatBottomRef = useRef(null);

useEffect(() => {
  // Cargar historial privado
  api.get('/chat/mensajes', { params: { tipo: 'privado' } })
    .then(r => setChatMsgs(r.data))
    .catch(() => {});

  // Conectar WS
  const ws = new WebSocket(`${WS_BASE_PORTAL}/ws/chat?token=${token}&tipo=privado`);
  ws.onmessage = (e) => {
    try { setChatMsgs(prev => [...prev, JSON.parse(e.data)]); } catch (_) {}
  };
  wsPortalRef.current = ws;
  return () => ws.close();
}, [token, WS_BASE_PORTAL]);

useEffect(() => {
  chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [chatMsgs]);

const enviarChatPortal = () => {
  const t = chatTexto.trim();
  if (!t || !wsPortalRef.current || wsPortalRef.current.readyState !== WebSocket.OPEN) return;
  wsPortalRef.current.send(JSON.stringify({ texto: t }));
  setChatTexto('');
};
```

- [ ] **Step 3: Agregar el tab de chat en la lista de tabs**

Encontrar donde se renderizan los tabs del portal (buscar el array o JSX de tabs) y agregar:

```jsx
{ id: 'chat', label: '💬 Chat con admin' }
```

- [ ] **Step 4: Agregar el panel de chat en el render del tab activo**

En el bloque `if (tab === 'chat')` o equivalente:

```jsx
{tab === 'chat' && (
  <div style={{ display: 'flex', flexDirection: 'column', height: 500, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}`, overflow: 'hidden' }}>
    {/* Mensajes */}
    <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 4 }}>
      {chatMsgs.length === 0 && (
        <p style={{ color: C.text2, textAlign: 'center', marginTop: 40, fontSize: 13 }}>
          Escríbenos, te respondemos pronto.
        </p>
      )}
      {chatMsgs.map((m) => {
        const mio = m.remitente === user?.username;
        return (
          <div key={m.id} style={{ display: 'flex', flexDirection: 'column', alignItems: mio ? 'flex-end' : 'flex-start', marginBottom: 2 }}>
            {!mio && <span style={{ fontSize: 11, color: C.text2, marginBottom: 2 }}>{m.remitente_nombre}</span>}
            <div style={{
              maxWidth: '72%', padding: '8px 12px',
              borderRadius: mio ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
              background: mio ? C.primary : C.surface2,
              color: mio ? '#fff' : C.text, fontSize: 13, lineHeight: 1.45, wordBreak: 'break-word',
            }}>
              {m.texto}
            </div>
            <span style={{ fontSize: 10, color: C.text2, marginTop: 2 }}>
              {new Date(m.creado).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        );
      })}
      <div ref={chatBottomRef} />
    </div>
    {/* Input */}
    <div style={{ padding: '10px 12px', borderTop: `1px solid ${C.border}`, display: 'flex', gap: 8, background: C.bg }}>
      <textarea
        value={chatTexto}
        onChange={e => setChatTexto(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarChatPortal(); } }}
        rows={1}
        placeholder="Escribe un mensaje…"
        style={{ flex: 1, padding: '8px 10px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, color: C.text, background: C.surface, resize: 'none', outline: 'none', fontFamily: 'inherit' }}
      />
      <button onClick={enviarChatPortal} style={{ background: C.primary, border: 'none', color: '#fff', borderRadius: 7, padding: '0 14px', cursor: 'pointer', fontWeight: 700, fontSize: 18 }}>➤</button>
    </div>
  </div>
)}
```

- [ ] **Step 5: Agregar `useRef` a los imports si no está**

Verificar que `useRef` esté en el import de React al inicio de `PortalCliente.jsx`. Ya está según lo leído: `import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/PortalCliente.jsx
git commit -m "feat(chat): panel de chat en portal cliente"
```

---

### Task 6: Badge y nav item en `Layout.jsx`

**Files:**
- Modify: `frontend/src/components/Layout.jsx`

Agregar "💬 Chat" en el sidebar con badge de mensajes privados no leídos (solo visible para admin).

- [ ] **Step 1: Agregar polling de no-leídos en Layout.jsx**

En el componente `Layout`, después del query de notificaciones existente (línea ~64), agregar:

```jsx
const { data: chatNoLeidos = { count: 0 } } = useQuery({
  queryKey: ['chat-no-leidos'],
  queryFn: () => api.get('/chat/no-leidos').then(r => r.data),
  refetchInterval: 30_000,
  enabled: user?.rol === 'admin',
});
```

- [ ] **Step 2: Agregar nav item de chat en `navItems`**

En la función `navItems` (línea ~19), agregar el item de chat. Para todos los roles (admin y empleado):

```jsx
// Agregar antes del spread de admin-only items:
{ to: '/chat', label: '💬 Chat', section: null },
```

La sección puede ir bajo `null` (sin encabezado de sección) o bajo `'PRINCIPAL'` — seguir el patrón existente. Agregarlo después de `{ to: '/tareas', ... }` ya que es comunicación.

- [ ] **Step 3: Renderizar badge en el nav item de chat**

El nav item de chat necesita mostrar el badge. La función actual renderiza todos los items igual. Modificar el render del NavLink para que el item `/chat` muestre el badge cuando `chatNoLeidos.count > 0`:

Encontrar el JSX del `<NavLink>` en Layout.jsx y agregar, dentro del label del item `/chat`, un badge similar al de notificaciones:

```jsx
<NavLink to={item.to} end={item.to === '/'}
  ...
>
  <span style={{ fontSize: collapsed ? 16 : 14 }}>{item.label.split(' ')[0]}</span>
  {!collapsed && (
    <span style={{ marginLeft: 6, overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>
      {item.label.split(' ').slice(1).join(' ')}
    </span>
  )}
  {item.to === '/chat' && chatNoLeidos.count > 0 && (
    <span style={{
      background: '#E53E3E', color: 'white', borderRadius: '50%',
      minWidth: 17, height: 17, fontSize: 10, fontWeight: 700,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      marginLeft: 'auto', flexShrink: 0,
    }}>
      {chatNoLeidos.count > 9 ? '9+' : chatNoLeidos.count}
    </span>
  )}
</NavLink>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Layout.jsx
git commit -m "feat(chat): nav item con badge de no leídos en sidebar"
```

---

### Task 7: Registrar ruta `/chat` en `App.jsx`

**Files:**
- Modify: `frontend/src/pages/App.jsx` (el archivo con el router real — `frontend/src/App.jsx` si ese es el usado; verificar cuál tiene `BrowserRouter`)

- [ ] **Step 1: Verificar cuál App.jsx tiene el BrowserRouter activo**

```bash
grep -rn "BrowserRouter\|Routes\|Route" frontend/src/ --include="*.jsx" -l
```

Leer el archivo correcto para confirmar dónde van las rutas.

- [ ] **Step 2: Agregar import lazy de Chat**

```jsx
const Chat = lazy(() => import('./pages/Chat'));
```

- [ ] **Step 3: Agregar la ruta `/chat` dentro del layout protegido**

En el bloque de rutas protegidas (dentro de `<PrivateRoute>`), agregar:

```jsx
<Route path="/chat" element={<Chat />} />
```

- [ ] **Step 4: Verificar que la app compila sin errores**

```bash
cd frontend
npm run build 2>&1 | tail -20
```
Esperado: `Successfully compiled` o `webpack compiled successfully`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/App.jsx
git commit -m "feat(chat): agregar ruta /chat en App.jsx"
```

---

### Task 8: Push y verificación final

- [ ] **Step 1: Push a dev**

```bash
git push origin dev
```

- [ ] **Step 2: Prueba manual en dev local**

1. Arrancar backend: `uvicorn main:app --reload`
2. Arrancar frontend: `npm start`
3. Login como admin → navegar a `/chat` → verificar que carga el chat grupal
4. Login como empleado en otra ventana → verificar que ve el chat grupal y puede enviarse mensajes
5. Login como cliente en portal → ir al tab Chat → enviar mensaje → verificar que aparece en la vista admin
6. Admin marca como leído → badge desaparece

- [ ] **Step 3: Commit de cierre si hay ajustes**

```bash
git add -A
git commit -m "fix(chat): ajustes post-prueba"
git push origin dev
```

---

## Notas importantes

- **Sin Redis en dev:** El broadcast funciona directamente (1 worker). En prod Railway tiene Redis, el pub/sub sincroniza los 4 workers.
- **`cliente_ref` en token:** El JWT del cliente tiene `cliente_ref` en el payload. El backend lo usa para identificar la conversación privada. El cliente nunca puede escribir como otra persona.
- **Limpieza:** No se implementa limpieza automática de mensajes por YAGNI. Se puede agregar después si es necesario.
- **Sin librerías nuevas en frontend:** Solo WebSocket API nativa. Sin socket.io, sin librerías de chat.
