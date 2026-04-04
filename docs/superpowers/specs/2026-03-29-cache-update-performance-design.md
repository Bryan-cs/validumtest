# Diseño: Optimización de rendimiento — Cache update desde respuesta del servidor

**Fecha:** 2026-03-29
**Módulos afectados:** Tareas, Pages, Afiliados, Facturacion, PortalCliente, Backups
**Tipo de cambio:** Frontend únicamente — cero cambios al backend

---

## Problema

Cada mutación exitosa llama `invalidateQueries`, lo que lanza un GET adicional al servidor y espera la respuesta antes de actualizar la UI. Esto genera lag perceptible en todas las acciones del usuario.

**Flujo actual:**
```
Acción usuario → POST/PUT/DELETE → servidor responde → invalidateQueries → GET extra → UI actualiza
```

**Flujo propuesto:**
```
Acción usuario → POST/PUT/DELETE → servidor responde → setQueryData → UI actualiza al instante
```

---

## Solución

Reemplazar `invalidateQueries` con `setQueryData` en todos los `onSuccess` de mutaciones, usando la respuesta del servidor para actualizar la caché directamente.

### Patrones

**Actualizar item** (PUT/PATCH — servidor devuelve objeto actualizado):
```js
onSuccess: (res) => {
  qc.setQueryData(['key'], prev => prev.map(x => x.id === res.data.id ? res.data : x))
}
```

**Eliminar item** (DELETE — servidor devuelve `{"ok": true}`):
```js
onSuccess: (_, id) => {
  qc.setQueryData(['key'], prev => prev.filter(x => x.id !== id))
}
```

**Crear item** (POST — servidor devuelve objeto nuevo):
```js
onSuccess: (res) => {
  qc.setQueryData(['key'], prev => [res.data, ...(prev || [])])
}
```

---

## Alcance por archivo

### Tareas.jsx
| Mutación | Operación | Query key | Patrón |
|---|---|---|---|
| `crear` | POST `/tareas` | `['tareas']` | Crear |
| `cambiarEstado` | PUT `/tareas/:id/estado` | `['tareas']` | Actualizar |
| `finalizar` | PUT `/tareas/:id/finalizar` | `['tareas']` | Actualizar |
| `finalizarLote` | PUT `/tareas/finalizar-lote` | `['tareas']` | Actualizar múltiples (usar `res.data.tareas`) |
| `eliminarTarea` | DELETE `/tareas/:id` | `['tareas']` | Eliminar |
| `comentar` | POST `/tareas/:id/comentarios` | `['tareas']` | Actualizar tarea padre (re-fetch solo esa tarea) |

Nota: `invalidateQueries(['notificaciones'])` se mantiene donde aplica — las notificaciones son side-effects de otras acciones y no se pueden reconstruir localmente.

### Pages.jsx
| Mutación | Query key | Patrón |
|---|---|---|
| `aplicarRetiro` | `['retiros']`, `['afiliados']` | Eliminar de retiros + invalidate afiliados (cross-módulo) |
| `eliminarRetiro` | `['retiros']` | Eliminar |
| `pagar` (facturas) | `['facturas']` | Actualizar |
| `eliminar` (facturas) | `['facturas']` | Eliminar |
| `guardarEmp` | `['empleados']` | Crear o Actualizar según `modal` |
| `eliminarEmp` | `['empleados']` | Eliminar |
| `addGasto` | `['gastos']` | Crear |
| `toggleG` | `['gastos']` | Actualizar |
| `delGasto` | `['gastos']` | Eliminar |
| `crearUsuario` | `['usuarios']` | Crear |
| `eliminar` (usuarios) | `['usuarios']` | Eliminar |
| `update` (listas) | `['listas']` | Actualizar |

### Afiliados.jsx
| Mutación | Query keys | Patrón |
|---|---|---|
| `guardar` (nuevo) | `['afiliados']`, `['afiliados_all']` | Crear en ambas listas |
| `guardar` (editar) | `['afiliados']`, `['afiliados_all']` | Actualizar en ambas listas |
| `eliminar` | `['afiliados']`, `['afiliados_all']`, `['eliminados']` | Eliminar de afiliados, Crear en eliminados |
| `restaurar` | `['afiliados']`, `['afiliados_all']`, `['eliminados']` | Crear en afiliados, Eliminar de eliminados |
| `borrarPermanente` | `['eliminados']` | Eliminar |
| `activarAfiliado` | `['afiliados']`, `['afiliados_all']` | Actualizar en ambas listas |

Nota: `guardar` también invalida `['facturas']` y `['documentos']` — estas se mantienen con `invalidateQueries` por ser side-effects indirectos.

### Facturacion.jsx
Se aplica el mismo patrón a las mutaciones de pago y eliminación de facturas en este módulo.

### PortalCliente.jsx y Backups.jsx
Se aplica el mismo patrón a las mutaciones identificadas.

---

## Casos especiales

### finalizarLote
El servidor devuelve `{ finalizadas: N, tareas: [...] }`. Actualizar cada tarea del array en caché:
```js
onSuccess: (res) => {
  const actualizadas = res.data.tareas;
  qc.setQueryData(['tareas'], prev =>
    prev.map(t => {
      const upd = actualizadas.find(u => u.id === t.id);
      return upd ? upd : t;
    })
  )
}
```

### comentar
El servidor devuelve el comentario creado, no la tarea completa. Opciones:
- Hacer `invalidateQueries(['tareas'])` solo para este caso (1 fetch, infrecuente)
- O hacer GET de la tarea individual y parchear. Se elige la primera por simplicidad.

### Queries que no se migran
- `invalidateQueries(['notificaciones'])` — side-effect de acciones de tareas, se mantiene
- Queries secundarias cross-módulo (`facturas` desde afiliados, `documentos`) — se mantienen con `invalidateQueries`

---

## Lo que NO cambia
- Backend: cero modificaciones
- Queries de lectura (`useQuery`)
- Polling de 60s en Tareas
- Lógica de negocio
- Manejo de errores

---

## Resultado esperado

Todas las acciones (guardar, actualizar, eliminar) reflejan el cambio en la UI inmediatamente después de la respuesta del servidor, sin un GET adicional. El usuario percibe la app como significativamente más rápida en las interacciones.
