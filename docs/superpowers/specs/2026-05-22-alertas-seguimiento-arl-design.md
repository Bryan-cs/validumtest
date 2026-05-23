# Alertas Automáticas SeguimientoARL — Design Spec
**Fecha:** 2026-05-22  
**Estado:** Aprobado

## Problema

Afiliados entran a `SeguimientoArl` con `estado='activo'` y nadie los activa. Pasan semanas sin visibilidad para admin/empleado.

## Solución

Job diario en `scheduler_jobs.py` que detecta registros ARL sin activar por más de 15 días y crea notificaciones internas para todos los usuarios admin y empleado. Re-alerta cada 7 días por registro para evitar spam.

## Cambio de modelo

`SeguimientoArl` (tabla `seguimiento_arl`) necesita campo nuevo:
- `ultima_alerta_en = Column(DateTime(timezone=True), nullable=True)` — registra cuándo se envió la última alerta para ese registro. NULL = nunca alertado.

Requiere migración Alembic: `p1q2r3s4t5u6_add_ultima_alerta_en_seguimiento_arl`.

## Job: `alertar_arl_pendientes()`

**Archivo:** `backend/scheduler_jobs.py`  
**Cuándo corre:** diario, ya incluido en `run_daily.py`

**Lógica:**
```
umbral_alerta   = hoy - 15 días   # lleva >= 15 días sin activar
umbral_reenvio  = hoy - 7 días    # no alertado en los últimos 7 días

registros = SeguimientoArl
  WHERE estado = 'activo'
  AND creado_en < umbral_alerta
  AND (ultima_alerta_en IS NULL OR ultima_alerta_en < umbral_reenvio)
```

**Por cada registro:**
1. Calcular `dias = (hoy - creado_en).days`
2. Mensaje: `"⚠️ {nombre} lleva {dias} días en SeguimientoARL sin activar ({entidad_arl})"`
3. Crear `Notificacion(usuario=u.username, mensaje=msg)` para cada `Usuario` con `rol IN ('admin', 'empleado')` y `activo=True`
4. Actualizar `registro.ultima_alerta_en = now()`
5. `db.commit()`

**Logging:** `log.info(f"ARL alertas: {n} registros, {total_notifs} notificaciones creadas")`

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `backend/models.py` | Agregar `ultima_alerta_en` a `SeguimientoArl` |
| `backend/alembic/versions/p1q2r3s4t5u6_*.py` | Migración ADD COLUMN |
| `backend/scheduler_jobs.py` | Nueva función `alertar_arl_pendientes()` |
| `backend/run_daily.py` | Llamar `alertar_arl_pendientes()` |

## Comportamiento

- Umbral inicio: 15 días desde `creado_en`
- Frecuencia re-alerta: cada 7 días por registro
- Destinatarios: todos los `Usuario.activo=True` con `rol in ('admin','empleado')`
- Las notificaciones aparecen en el campano del Layout (sistema existente, polling 30s)
- `ultima_alerta_en` se resetea si el admin cambia `estado` a `retirar` o `retirado` — no aplica, el estado cambia y deja de entrar al query

## Sin cambios en frontend

El sistema de notificaciones ya existe y ya muestra badge + sonido. No se requiere código frontend nuevo.

## Tests

- `test_alertar_arl_pendientes_crea_notificaciones`: registro con 16 días → notificación creada
- `test_alertar_arl_pendientes_no_spam`: registro con alerta enviada hace 3 días → no crea nueva
- `test_alertar_arl_pendientes_retirado_ignorado`: registro con `estado='retirado'` → ignorado
- `test_alertar_arl_pendientes_fresco_ignorado`: registro con 10 días → ignorado
