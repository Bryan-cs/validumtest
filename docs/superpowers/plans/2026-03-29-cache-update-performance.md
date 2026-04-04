# Cache Update Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar `invalidateQueries` con `setQueryData` en todos los `onSuccess` de mutaciones del frontend para eliminar el GET extra post-mutación y reflejar cambios en la UI de forma inmediata.

**Architecture:** El backend ya devuelve el objeto actualizado en la mayoría de mutaciones. En lugar de lanzar un fetch adicional, se usa `queryClient.setQueryData` para parchear la caché directamente con la respuesta del servidor. Para deletes (que retornan `{"ok": true}`), se filtra el array por el `id` pasado como variable de la mutación. Para cross-module side-effects (e.g., afiliado → facturas), se mantiene `invalidateQueries` solo en la query secundaria.

**Tech Stack:** React 18, TanStack React Query v5, JavaScript

---

## Archivos a modificar

- `frontend/src/pages/Tareas.jsx` — 5 mutations
- `frontend/src/pages/Pages.jsx` — 13 mutations
- `frontend/src/pages/Afiliados.jsx` — 5 mutations
- `frontend/src/pages/Facturacion.jsx` — 4 mutations
- `frontend/src/pages/PortalCliente.jsx` — 2 mutations
- `frontend/src/pages/Backups.jsx` — 1 mutation

---

## Task 1: Tareas.jsx

**Files:**
- Modify: `frontend/src/pages/Tareas.jsx`

- [ ] **Paso 1: Mutación `crear` — agregar tarea nueva al inicio de la caché**

Reemplaza el `onSuccess` de la mutación `crear` (línea ~177):

```js
// ANTES
onSuccess: () => {
  toast.success('Tarea creada');
  qc.invalidateQueries({ queryKey: ['tareas'] });
  setModalNueva(false);
  setForm({ titulo: '', descripcion: '', asignado_a: '', fecha_limite: '', privada: false });
  setNuevaFiles([]);
},

// DESPUÉS
onSuccess: (res) => {
  toast.success('Tarea creada');
  qc.setQueryData(['tareas'], prev => [res.data, ...(prev || [])]);
  setModalNueva(false);
  setForm({ titulo: '', descripcion: '', asignado_a: '', fecha_limite: '', privada: false });
  setNuevaFiles([]);
},
```

- [ ] **Paso 2: Mutación `cambiarEstado` — actualizar tarea por id**

Reemplaza el `onSuccess` de la mutación `cambiarEstado` (línea ~189):

```js
// ANTES
onSuccess: () => {
  toast.success('Estado actualizado');
  qc.invalidateQueries({ queryKey: ['tareas'] });
  qc.invalidateQueries({ queryKey: ['notificaciones'] });
},

// DESPUÉS
onSuccess: (res) => {
  toast.success('Estado actualizado');
  qc.setQueryData(['tareas'], prev => prev?.map(t => t.id === res.data.id ? res.data : t));
  qc.invalidateQueries({ queryKey: ['notificaciones'] });
},
```

- [ ] **Paso 3: Mutación `finalizar` — actualizar tarea finalizada**

Reemplaza el `onSuccess` de la mutación `finalizar` (línea ~199):

```js
// ANTES
onSuccess: () => {
  toast.success('Tarea finalizada y archivada');
  qc.invalidateQueries({ queryKey: ['tareas'] });
  qc.invalidateQueries({ queryKey: ['notificaciones'] });
},

// DESPUÉS
onSuccess: (res) => {
  toast.success('Tarea finalizada y archivada');
  qc.setQueryData(['tareas'], prev => prev?.map(t => t.id === res.data.id ? res.data : t));
  qc.invalidateQueries({ queryKey: ['notificaciones'] });
},
```

- [ ] **Paso 4: Mutación `finalizarLote` — actualizar múltiples tareas**

Reemplaza el `onSuccess` de la mutación `finalizarLote` (línea ~208):

```js
// ANTES
onSuccess: data => {
  toast.success(`${data.data.finalizadas} tarea${data.data.finalizadas !== 1 ? 's' : ''} finalizada${data.data.finalizadas !== 1 ? 's' : ''}`);
  qc.invalidateQueries({ queryKey: ['tareas'] });
  qc.invalidateQueries({ queryKey: ['notificaciones'] });
  setSeleccionadas(new Set());
},

// DESPUÉS
onSuccess: (res) => {
  const { finalizadas, tareas: actualizadas } = res.data;
  toast.success(`${finalizadas} tarea${finalizadas !== 1 ? 's' : ''} finalizada${finalizadas !== 1 ? 's' : ''}`);
  qc.setQueryData(['tareas'], prev =>
    prev?.map(t => {
      const upd = actualizadas.find(u => u.id === t.id);
      return upd ? upd : t;
    })
  );
  qc.invalidateQueries({ queryKey: ['notificaciones'] });
  setSeleccionadas(new Set());
},
```

- [ ] **Paso 5: Mutación `eliminarTarea` — filtrar por id**

Reemplaza el `onSuccess` de la mutación `eliminarTarea` (línea ~219):

```js
// ANTES
onSuccess: () => { toast.success('Tarea eliminada'); qc.invalidateQueries({ queryKey: ['tareas'] }); },

// DESPUÉS
onSuccess: (_, id) => { toast.success('Tarea eliminada'); qc.setQueryData(['tareas'], prev => prev?.filter(t => t.id !== id)); },
```

- [ ] **Paso 6: Verificar en la app**

1. Abre la sección Tareas en el browser con DevTools → Network tab
2. Crea una tarea → verifica que NO aparece un GET `/tareas` en Network; la tarea nueva aparece al instante en la lista
3. Cambia el estado de una tarea → verifica sin GET extra
4. Finaliza una tarea → verifica sin GET extra
5. Elimina una tarea → verifica sin GET extra

- [ ] **Paso 7: Commit**

```bash
cd C:/Projects/bbcfile
git add frontend/src/pages/Tareas.jsx
git commit -m "perf: setQueryData en mutaciones de Tareas.jsx para eliminar refetch extra"
```

---

## Task 2: Pages.jsx — Retiros y Facturas

**Files:**
- Modify: `frontend/src/pages/Pages.jsx`

- [ ] **Paso 1: Mutación `aplicarRetiro` — agregar retiro a caché**

Busca la mutación `aplicarRetiro` en Pages.jsx. Reemplaza su `onSuccess`:

```js
// ANTES
onSuccess: (r)=>{
  const n = r.data?.facturas_pendientes;
  toast.success(n ? `Retiro aplicado. ${n} factura(s) pendiente(s) del mes` : 'Retiro aplicado');
  qc.invalidateQueries({queryKey:['retiros']}); qc.invalidateQueries({queryKey:['afiliados']});
  setModal(false); setDoc(''); setObs('');
},

// DESPUÉS
onSuccess: (res)=>{
  const n = res.data?.facturas_pendientes;
  toast.success(n ? `Retiro aplicado. ${n} factura(s) pendiente(s) del mes` : 'Retiro aplicado');
  qc.setQueryData(['retiros'], prev => [res.data.retiro, ...(prev || [])]);
  qc.invalidateQueries({queryKey:['afiliados']});
  setModal(false); setDoc(''); setObs('');
},
```

- [ ] **Paso 2: Mutación `eliminar` (retiros) — filtrar por id**

Busca la mutación `eliminar` de retiros. Reemplaza su `onSuccess`:

```js
// ANTES
onSuccess:()=>{ toast.success('Retiro eliminado'); qc.invalidateQueries({queryKey:['retiros']}); },

// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Retiro eliminado'); qc.setQueryData(['retiros'], prev => prev?.filter(r => r.id !== id)); },
```

- [ ] **Paso 3: Mutación `pagar` (facturas en Retiros/Cobro) — actualizar factura**

Busca la mutación `pagar` en la sección de facturas de Pages.jsx. Reemplaza su `onSuccess`:

```js
// ANTES
onSuccess:()=>{ toast.success('Factura marcada como pagada'); qc.invalidateQueries({queryKey:['facturas']}); },

// DESPUÉS
onSuccess:(res)=>{ toast.success('Factura marcada como pagada'); qc.setQueryData(['facturas'], prev => prev?.map(f => f.id === res.data.id ? res.data : f)); },
```

- [ ] **Paso 4: Mutación `eliminar` (facturas) — filtrar por id**

Busca la mutación `eliminar` de facturas en Pages.jsx. Reemplaza su `onSuccess`:

```js
// ANTES
onSuccess:()=>{ toast.success('Factura eliminada'); qc.invalidateQueries({queryKey:['facturas']}); },

// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Factura eliminada'); qc.setQueryData(['facturas'], prev => prev?.filter(f => f.id !== id)); },
```

- [ ] **Paso 5: Mutación `guardarEmp` — crear o actualizar empleado**

Reemplaza el `onSuccess` de `guardarEmp`:

```js
// ANTES
onSuccess:()=>{ toast.success('Empleado guardado'); qc.invalidateQueries({queryKey:['empleados']}); setModal(null); },

// DESPUÉS
onSuccess:(res)=>{
  toast.success('Empleado guardado');
  if (modal === 'nuevo') {
    qc.setQueryData(['empleados'], prev => [...(prev || []), res.data]);
  } else {
    qc.setQueryData(['empleados'], prev => prev?.map(e => e.id === res.data.id ? res.data : e));
  }
  setModal(null);
},
```

- [ ] **Paso 6: Mutación `eliminarEmp` — filtrar por id**

```js
// ANTES
onSuccess:()=>{ toast.success('Empleado eliminado'); qc.invalidateQueries({queryKey:['empleados']}); },

// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Empleado eliminado'); qc.setQueryData(['empleados'], prev => prev?.filter(e => e.id !== id)); },
```

- [ ] **Paso 7: Commit**

```bash
git add frontend/src/pages/Pages.jsx
git commit -m "perf: setQueryData en retiros, facturas y empleados de Pages.jsx"
```

---

## Task 3: Pages.jsx — Gastos, Usuarios, Listas, Config, Portal Admin

**Files:**
- Modify: `frontend/src/pages/Pages.jsx`

- [ ] **Paso 1: Mutación `addGasto` — agregar gasto a caché**

```js
// ANTES
onSuccess:()=>{ toast.success('Gasto agregado'); qc.invalidateQueries({queryKey:['gastos']}); setGnom(''); setGval(0); },

// DESPUÉS
onSuccess:(res)=>{ toast.success('Gasto agregado'); qc.setQueryData(['gastos'], prev => [...(prev || []), res.data]); setGnom(''); setGval(0); },
```

- [ ] **Paso 2: Mutación `toggleG` — actualizar gasto**

```js
// ANTES
onSuccess:()=>qc.invalidateQueries({queryKey:['gastos']}),

// DESPUÉS
onSuccess:(res)=>qc.setQueryData(['gastos'], prev => prev?.map(g => g.id === res.data.id ? res.data : g)),
```

- [ ] **Paso 3: Mutación `delGasto` — filtrar por id**

```js
// ANTES
onSuccess:()=>{ toast.success('Gasto eliminado'); qc.invalidateQueries({queryKey:['gastos']}); },

// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Gasto eliminado'); qc.setQueryData(['gastos'], prev => prev?.filter(g => g.id !== id)); },
```

- [ ] **Paso 4: Mutación `crearUsuario` — agregar usuario a caché**

```js
// ANTES
onSuccess:()=>{ toast.success('Usuario creado'); qc.invalidateQueries({queryKey:['usuarios']}); setModal(false); setErr(''); },

// DESPUÉS
onSuccess:(res)=>{ toast.success('Usuario creado'); qc.setQueryData(['usuarios'], prev => [...(prev || []), res.data]); setModal(false); setErr(''); },
```

- [ ] **Paso 5: Mutación `eliminar` (usuarios) — filtrar por id**

```js
// ANTES
onSuccess:()=>{ toast.success('Usuario eliminado'); qc.invalidateQueries({queryKey:['usuarios']}); },

// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Usuario eliminado'); qc.setQueryData(['usuarios'], prev => prev?.filter(u => u.id !== id)); },
```

- [ ] **Paso 6: Mutación `update` (listas) — actualizar lista por nombre**

El backend devuelve `{nombre, items}`. La query `['listas']` es un objeto `{nombreLista: [items]}`:

```js
// ANTES
onSuccess:()=>{ toast.success('Lista actualizada'); qc.invalidateQueries({queryKey:['listas']}); },

// DESPUÉS
onSuccess:(res)=>{ toast.success('Lista actualizada'); qc.setQueryData(['listas'], prev => ({ ...prev, [res.data.nombre]: res.data.items })); },
```

- [ ] **Paso 7: Mutación `guardar` (config) — reemplazar config en caché**

El backend devuelve el objeto config completo actualizado:

```js
// ANTES
onSuccess:()=>{ toast.success('Configuración actualizada'); qc.invalidateQueries({queryKey:['config']}); },

// DESPUÉS
onSuccess:(res)=>{ toast.success('Configuración actualizada'); qc.setQueryData(['config'], res.data); },
```

- [ ] **Paso 8: Mutaciones `updNovedad`, `updSolicitud`, `updNovedadAfil` — actualizar estado manualmente**

Estas tres mutaciones del portal admin devuelven `{"ok": true}`. Se actualiza el estado y respuesta usando las variables pasadas a la mutación:

```js
// updNovedad — ANTES
onSuccess:()=>{ toast.success('Estado actualizado'); qc.invalidateQueries({queryKey:['admin-novedades-pago']}); cerrarModalResp(); },

// updNovedad — DESPUÉS
onSuccess:(_, { id, estado, respuesta })=>{
  toast.success('Estado actualizado');
  qc.setQueryData(['admin-novedades-pago'], prev =>
    prev?.map(n => n.id === id ? { ...n, estado, respuesta: respuesta ?? n.respuesta } : n)
  );
  cerrarModalResp();
},

// updSolicitud — ANTES
onSuccess:()=>{ toast.success('Estado actualizado'); qc.invalidateQueries({queryKey:['admin-solicitudes-retiro']}); cerrarModalResp(); },

// updSolicitud — DESPUÉS
onSuccess:(_, { id, estado, respuesta })=>{
  toast.success('Estado actualizado');
  qc.setQueryData(['admin-solicitudes-retiro'], prev =>
    prev?.map(s => s.id === id ? { ...s, estado, respuesta: respuesta ?? s.respuesta } : s)
  );
  cerrarModalResp();
},

// updNovedadAfil — ANTES
onSuccess:()=>{ toast.success('Estado actualizado'); qc.invalidateQueries({queryKey:['admin-novedades-afil']}); cerrarModalResp(); },

// updNovedadAfil — DESPUÉS
onSuccess:(_, { id, estado, respuesta })=>{
  toast.success('Estado actualizado');
  qc.setQueryData(['admin-novedades-afil'], prev =>
    prev?.map(s => s.id === id ? { ...s, estado, respuesta: respuesta ?? s.respuesta } : s)
  );
  cerrarModalResp();
},
```

- [ ] **Paso 9: Mutaciones `delNovedad`, `delSolicitud`, `delNovedadAfil` — filtrar por id**

```js
// delNovedad — ANTES
onSuccess:()=>{ toast.success('Novedad eliminada'); qc.invalidateQueries({queryKey:['admin-novedades-pago']}); },
// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Novedad eliminada'); qc.setQueryData(['admin-novedades-pago'], prev => prev?.filter(n => n.id !== id)); },

// delSolicitud — ANTES
onSuccess:()=>{ toast.success('Solicitud eliminada'); qc.invalidateQueries({queryKey:['admin-solicitudes-retiro']}); },
// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Solicitud eliminada'); qc.setQueryData(['admin-solicitudes-retiro'], prev => prev?.filter(s => s.id !== id)); },

// delNovedadAfil — ANTES
onSuccess:()=>{ toast.success('Solicitud eliminada'); qc.invalidateQueries({queryKey:['admin-novedades-afil']}); },
// DESPUÉS
onSuccess:(_, id)=>{ toast.success('Solicitud eliminada'); qc.setQueryData(['admin-novedades-afil'], prev => prev?.filter(s => s.id !== id)); },
```

- [ ] **Paso 10: Commit**

```bash
git add frontend/src/pages/Pages.jsx
git commit -m "perf: setQueryData en gastos, usuarios, listas, config y portal admin de Pages.jsx"
```

---

## Task 4: Afiliados.jsx

**Files:**
- Modify: `frontend/src/pages/Afiliados.jsx`

- [ ] **Paso 1: Mutación `guardar` (nuevo/editar) — crear o actualizar en ambas listas**

La variable `modal` es `'nuevo'` o un objeto con `id`. El backend devuelve el afiliado completo:

```js
// ANTES
onSuccess: () => {
  toast.success(modal==='nuevo'?'Afiliado registrado':'Actualizado');
  if (pendingFiles.length > 0) toast.success(`${pendingFiles.length} documento(s) adjuntado(s)`);
  qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); qc.invalidateQueries({queryKey:['facturas']}); qc.invalidateQueries({queryKey:['documentos']}); setModal(null);
},

// DESPUÉS
onSuccess: (res) => {
  toast.success(modal==='nuevo'?'Afiliado registrado':'Actualizado');
  if (pendingFiles.length > 0) toast.success(`${pendingFiles.length} documento(s) adjuntado(s)`);
  if (modal === 'nuevo') {
    qc.setQueryData(['afiliados'], prev => [res.data, ...(prev || [])]);
    qc.setQueryData(['afiliados_all'], prev => [res.data, ...(prev || [])]);
  } else {
    qc.setQueryData(['afiliados'], prev => prev?.map(a => a.id === res.data.id ? res.data : a));
    qc.setQueryData(['afiliados_all'], prev => prev?.map(a => a.id === res.data.id ? res.data : a));
  }
  qc.invalidateQueries({queryKey:['facturas']});
  qc.invalidateQueries({queryKey:['documentos']});
  setModal(null);
},
```

- [ ] **Paso 2: Mutación `eliminar` — filtrar de afiliados, mantener invalidate para eliminados**

El backend devuelve `{"ok": true, "facturas_pendientes": N}`, no el objeto eliminado. Se actualiza afiliados localmente y se invalida `eliminados` para que la lista de papelera sea consistente:

```js
// ANTES
onSuccess: res => { const n=res.data?.facturas_pendientes; toast.success(n?`Eliminado. ${n} factura(s) conservadas`:'Afiliado eliminado'); qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); qc.invalidateQueries({queryKey:['eliminados']}); },

// DESPUÉS
onSuccess: (res, id) => {
  const n = res.data?.facturas_pendientes;
  toast.success(n ? `Eliminado. ${n} factura(s) conservadas` : 'Afiliado eliminado');
  qc.setQueryData(['afiliados'], prev => prev?.filter(a => a.id !== id));
  qc.setQueryData(['afiliados_all'], prev => prev?.filter(a => a.id !== id));
  qc.invalidateQueries({queryKey:['eliminados']});
},
```

- [ ] **Paso 3: Mutación `restaurar` — mantener invalidateQueries (no hay objeto completo disponible)**

Esta mutación retorna solo `{"ok": true, "nombre": "..."}` sin el afiliado completo. Se mantiene `invalidateQueries` para los tres query keys. No hay cambio aquí.

- [ ] **Paso 4: Mutación `borrarPermanente` — filtrar eliminados por id**

```js
// ANTES
onSuccess: () => { toast.success('Eliminado permanentemente'); qc.invalidateQueries({queryKey:['eliminados']}); },

// DESPUÉS
onSuccess: (_, id) => { toast.success('Eliminado permanentemente'); qc.setQueryData(['eliminados'], prev => prev?.filter(e => e.id !== id)); },
```

- [ ] **Paso 5: Mutación `activarAfiliado` — actualizar en ambas listas**

```js
// ANTES
onSuccess: () => { toast.success('Afiliado activado'); qc.invalidateQueries({queryKey:['afiliados']}); qc.invalidateQueries({queryKey:['afiliados_all']}); },

// DESPUÉS
onSuccess: (res) => {
  toast.success('Afiliado activado');
  qc.setQueryData(['afiliados'], prev => prev?.map(a => a.id === res.data.id ? res.data : a));
  qc.setQueryData(['afiliados_all'], prev => prev?.map(a => a.id === res.data.id ? res.data : a));
},
```

- [ ] **Paso 6: Verificar en la app**

1. Edita un afiliado → verifica sin GET extra en Network, cambio visible inmediato
2. Crea un afiliado → verifica que aparece en la lista sin refetch
3. Elimina un afiliado → desaparece inmediatamente de la lista

- [ ] **Paso 7: Commit**

```bash
git add frontend/src/pages/Afiliados.jsx
git commit -m "perf: setQueryData en mutaciones de Afiliados.jsx para eliminar refetch extra"
```

---

## Task 5: Facturacion.jsx

**Files:**
- Modify: `frontend/src/pages/Facturacion.jsx`

- [ ] **Paso 1: Mutación `guardar` en `ModalNuevaFactura` — agregar factura nueva**

Busca el primer componente `ModalNuevaFactura` y su mutación `guardar`. Reemplaza el `onSuccess`:

```js
// ANTES
onSuccess: () => { toast.success('Factura guardada'); qc.invalidateQueries({queryKey:['facturas']}); qc.invalidateQueries({queryKey:['cobro']}); onClose(); },

// DESPUÉS
onSuccess: (res) => {
  toast.success('Factura guardada');
  qc.setQueryData(['facturas'], prev => [res.data, ...(prev || [])]);
  qc.invalidateQueries({queryKey:['cobro']});
  onClose();
},
```

- [ ] **Paso 2: Mutación `guardar` en `ModalEditarFactura` — actualizar factura existente**

Busca el componente `ModalEditarFactura` y su mutación `guardar`. Reemplaza el `onSuccess`:

```js
// ANTES
onSuccess: () => { toast.success('Factura actualizada'); qc.invalidateQueries({queryKey:['facturas']}); onClose(); },

// DESPUÉS
onSuccess: (res) => { toast.success('Factura actualizada'); qc.setQueryData(['facturas'], prev => prev?.map(f => f.id === res.data.id ? res.data : f)); onClose(); },
```

- [ ] **Paso 3: Mutación `pagar` — actualizar factura pagada**

```js
// ANTES
onSuccess: () => { toast.success('Factura marcada como pagada'); qc.invalidateQueries({queryKey:['facturas']}); setModalPagar(null); setBancoPago(''); },

// DESPUÉS
onSuccess: (res) => { toast.success('Factura marcada como pagada'); qc.setQueryData(['facturas'], prev => prev?.map(f => f.id === res.data.id ? res.data : f)); setModalPagar(null); setBancoPago(''); },
```

- [ ] **Paso 4: Mutación `eliminar` — filtrar factura por id**

```js
// ANTES
onSuccess: () => { toast.success('Factura eliminada'); qc.invalidateQueries({queryKey:['facturas']}); },

// DESPUÉS
onSuccess: (_, id) => { toast.success('Factura eliminada'); qc.setQueryData(['facturas'], prev => prev?.filter(f => f.id !== id)); },
```

- [ ] **Paso 5: Commit**

```bash
git add frontend/src/pages/Facturacion.jsx
git commit -m "perf: setQueryData en mutaciones de Facturacion.jsx para eliminar refetch extra"
```

---

## Task 6: PortalCliente.jsx y Backups.jsx

**Files:**
- Modify: `frontend/src/pages/PortalCliente.jsx`
- Modify: `frontend/src/pages/Backups.jsx`

- [ ] **Paso 1: PortalCliente — mutación `leer` notificaciones — marcar todas como leídas en caché**

Busca en `PortalCliente.jsx` el componente de notificaciones y la mutación `leer`:

```js
// ANTES
onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-notifs'] }),

// DESPUÉS
onSuccess: () => qc.setQueryData(['portal-notifs'], prev => prev?.map(n => ({ ...n, leida: true }))),
```

- [ ] **Paso 2: PortalCliente — mutación `limpiar` notificaciones — vaciar caché**

```js
// ANTES
onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-notifs'] }); setOpen(false); },

// DESPUÉS
onSuccess: () => { qc.setQueryData(['portal-notifs'], []); setOpen(false); },
```

- [ ] **Paso 3: Commit PortalCliente**

```bash
git add frontend/src/pages/PortalCliente.jsx
git commit -m "perf: setQueryData en notificaciones de PortalCliente.jsx"
```

- [ ] **Paso 4: Backups — eliminar backup de caché**

La query `['backups']` devuelve `{total: N, backups: [...]}`. `confirmDel` es el nombre del archivo (`archivo`). Busca el `onConfirm` dentro del `ConfirmModal` de eliminación en `Backups.jsx`:

```js
// ANTES
onConfirm={async () => {
  try {
    await api.delete(`/backups/${confirmDel}`);
    toast.success('Backup eliminado');
    qc.invalidateQueries({ queryKey: ['backups'] });
  } catch { toast.error('Error eliminando backup'); }
  setConfirmDel(null);
}}

// DESPUÉS
onConfirm={async () => {
  try {
    await api.delete(`/backups/${confirmDel}`);
    toast.success('Backup eliminado');
    qc.setQueryData(['backups'], prev => {
      const backups = (prev?.backups || []).filter(b => b.archivo !== confirmDel);
      return { ...prev, backups, total: backups.length };
    });
  } catch { toast.error('Error eliminando backup'); }
  setConfirmDel(null);
}}
```

Nota: `crearBackup` y `restaurarBackup` mantienen `invalidateQueries` porque el backend no devuelve el objeto completo del backup (tamaño, fecha exacta, etc.).

- [ ] **Paso 5: Commit Backups**

```bash
git add frontend/src/pages/Backups.jsx
git commit -m "perf: setQueryData al eliminar backup en Backups.jsx"
```

---

## Task 7: Push a producción

- [ ] **Paso 1: Verificación final en dev**

Abre la app localmente y verifica en DevTools → Network que tras cada tipo de acción (crear, editar, eliminar, pagar, cambiar estado) **no aparece un GET** adicional a la misma query que acaba de mutar.

- [ ] **Paso 2: Flujo completo a producción**

```bash
cd C:/Projects/bbcfile
git checkout main
git merge dev
git push origin main
git checkout dev
```

Railway despliega automáticamente desde `main`. Vercel lo mismo. Verificar en producción que el comportamiento es correcto en al menos: Tareas, Afiliados, Facturación.
