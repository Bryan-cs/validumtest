# Chat en Tiempo Real — Spec de Diseño

**Fecha:** 2026-04-03

---

## Resumen

Módulo de chat en tiempo real con dos canales:
1. **Chat grupal interno** — admin + todos los empleados (como grupo de trabajo)
2. **Chat 1-a-1 con clientes** — cada cliente del portal tiene su conversación privada con el admin

---

## Decisiones de diseño confirmadas

| Decisión | Elección |
|----------|----------|
| Acceso desde la app | Página dedicada `/chat` en el sidebar |
| Layout admin | Panel lateral con tabs "Interno" / "Clientes" + panel de chat |
| Chat en portal cliente | Tab "💬 Chat" dentro del portal existente |
| Sincronización multi-worker | Redis pub/sub (`redis.asyncio`) |
| Notificaciones sonoras | Web Audio API nativa, tono 1000Hz/0.2s |

---

## Arquitectura

### Backend

**Nuevo archivo:** `backend/routers/chat.py`

Componentes:
- `ConnectionManager` — gestiona WebSockets activos por canal en memoria del worker
- `_escuchar_redis()` — tarea async de fondo, suscrita a `chat:*` via pub/sub
- `_publicar_redis()` — publica mensaje en Redis; fallback a broadcast directo si no hay Redis
- Endpoints REST + WebSocket endpoint

**Lifespan:** `iniciar_listener()` y `detener_listener()` se invocan desde el `lifespan` de `main.py`.

**Flujo de mensaje:**
```
Usuario escribe
  → WS send JSON {texto}
  → backend valida token, identifica canal
  → guarda Mensaje en PostgreSQL
  → publica en Redis canal correspondiente
  → todos los workers reciben via pub/sub
  → cada worker hace broadcast a sus WS conectados en ese canal
```

**Autenticación WebSocket:** token JWT pasado como query param `?token=xxx` (WebSocket API no soporta headers custom). El backend verifica con `_decode_token()` expuesto en `deps.py`.

### Frontend

WebSocket API nativa del browser. Sin socket.io ni librerías de chat externas.

**Canales Redis:**
- `chat:grupal` → admin + empleados
- `chat:privado:{cliente_ref}` → admin ↔ cliente específico

---

## Modelo de datos

```python
class Mensaje(Base):
    __tablename__ = "mensajes"
    id                = Column(Integer, primary_key=True)
    tipo              = Column(String(10), index=True)      # "grupal" | "privado"
    remitente         = Column(String(60), index=True)      # username
    remitente_nombre  = Column(String(120))
    destinatario      = Column(String(120), nullable=True)  # cliente_ref (solo privado)
    texto             = Column(Text)
    creado            = Column(DateTime, default=_utcnow, index=True)
    leido             = Column(Boolean, default=False)      # solo aplica a mensajes privados
```

`leido` se usa para contar no leídos del admin (badge sidebar). Para el chat grupal no hay tracking de lectura por usuario.

---

## API

| Método | Endpoint | Acceso | Descripción |
|--------|----------|--------|-------------|
| GET | `/chat/mensajes?tipo=grupal` | admin, empleado | Historial grupal (últimos 100) |
| GET | `/chat/mensajes?tipo=privado&cliente_ref=X` | admin | Historial con cliente X |
| GET | `/chat/mensajes?tipo=privado` | cliente | Su propio historial (cliente_ref del token) |
| GET | `/chat/clientes-activos` | admin | Lista de clientes con conversación + count no leídos |
| GET | `/chat/no-leidos` | admin | Count total mensajes privados no leídos |
| PUT | `/chat/mensajes/{cliente_ref}/leer` | admin | Marca mensajes de cliente como leídos |
| WS | `/ws/chat?token=X&tipo=Y[&cliente_ref=Z]` | todos | Conexión en tiempo real |

**Payload WS recibido del cliente:**
```json
{ "texto": "Hola equipo" }
```

**Payload WS enviado al cliente:**
```json
{
  "id": 123,
  "tipo": "grupal",
  "remitente": "admin1",
  "remitente_nombre": "Juan Admin",
  "destinatario": null,
  "texto": "Hola equipo",
  "creado": "2026-04-03T15:00:00",
  "leido": false
}
```

---

## Frontend

### Archivos modificados

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `backend/models.py` | Modificar | Agregar modelo `Mensaje` |
| `backend/routers/chat.py` | Crear | Router completo |
| `backend/routers/deps.py` | Modificar | Exponer `_decode_token()` |
| `backend/main.py` | Modificar | Registrar router + listener en lifespan |
| `frontend/src/pages/Chat.jsx` | Crear | Página `/chat` |
| `frontend/src/pages/PortalCliente.jsx` | Modificar | Tab "💬 Chat" |
| `frontend/src/components/Layout.jsx` | Modificar | Nav item + badge + sonido |
| `frontend/src/pages/App.jsx` | Modificar | Ruta `/chat` |

### Chat.jsx (admin + empleados)

- **Panel izquierdo (240px):** tabs "👥 Interno" y "💬 Clientes"
  - Tab Interno: texto informativo del canal grupal
  - Tab Clientes: lista de `clientes-activos` con badge de no leídos por cliente
- **Panel derecho:** historial de mensajes + input
  - Burbujas: propias a la derecha (color `C.primary`), ajenas a la izquierda (`C.surface2`)
  - Separadores de fecha entre días
  - `Enter` envía; `Shift+Enter` nueva línea
  - Auto-scroll al recibir nuevo mensaje
- Al seleccionar cliente → `PUT /chat/mensajes/{ref}/leer` → invalida query `chat-clientes`
- WS URL: `${REACT_APP_API_URL.replace('http','ws')}/ws/chat?token=X&tipo=Y`

**Visibilidad por rol:**
- Admin: panel izquierdo con ambos tabs
- Empleado: sin panel izquierdo, solo chat grupal directo

### PortalCliente.jsx

- Nuevo tab "💬 Chat" en la barra de tabs existente
- Al activar el tab: carga historial `GET /chat/mensajes?tipo=privado` + conecta WS `tipo=privado`
- El cliente nunca pasa `cliente_ref` — el backend lo extrae del JWT
- Al desmontar o cambiar tab: cierra WS

### Layout.jsx

**Nav item:**
```
{ to: '/chat', label: '💬 Chat', section: null }
```
Posición: después de `📋 Tareas`, antes de `🧾 Facturación`.

**Badge de no leídos (admin):**
- `useQuery` con `queryKey: ['chat-no-leidos']`, `refetchInterval: 30_000`, `enabled: user?.rol === 'admin'`
- Badge rojo sobre el nav item (mismo estilo que badge de notificaciones)

**Sonido:**
- Se dispara cuando `chatNoLeidos.count` aumenta respecto al valor anterior (mismo patrón que `prevNoLeidas` de tareas)
- Web Audio API: oscilador 1000Hz, duración 0.2s, gain 0.25
- Solo para admin (privados no leídos)

---

## Comportamiento de notificaciones sonoras

| Evento | Quién escucha | Condición para sonar |
|--------|--------------|----------------------|
| Mensaje privado nuevo de cliente | Admin | `chatNoLeidos.count` sube (polling 30s) |
| Mensaje en chat grupal | — | No hay sonido por canal grupal (demasiado frecuente) |
| Respuesta del admin | Cliente portal | Siempre que llegue un mensaje por WS, sin importar qué tab esté activo |

---

## Seguridad

- Admin puede leer cualquier conversación privada (por diseño)
- Cliente solo puede leer/escribir en su propia conversación (`cliente_ref` del JWT, no parámetro)
- Empleado no ve conversaciones privadas con clientes — solo chat grupal
- Validación de token en el WS antes de `accept()` — si falla, cierra con code 1008

---

## Restricciones / fuera de alcance

- Sin edición ni borrado de mensajes
- Sin adjuntos en el chat (hay módulo de documentos separado)
- Sin historial ilimitado — se cargan últimos 100 mensajes al abrir canal
- Sin limpieza automática de mensajes (se agrega después si es necesario)
- Sin indicador "escribiendo..."
