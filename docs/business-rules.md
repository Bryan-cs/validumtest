# BBC File — Reglas de Negocio

Documento de referencia para agentes, desarrolladores y revisores. Cualquier implementación que contradiga estas reglas es un bug.

---

## 1. Afiliados

### Estados de servicio (`estado_srv`)
Los únicos valores válidos son:
```
ACTIVO | SUSPENDIDO | DOBLE AFILIACION | EN ESPERA DE ACTIVACION | RETIRADO | EN MORA | NO AFILIADO | PENDIENTE
```

### Ciclo de vida
```
Nuevo afiliado → activo=True, estado_srv=ACTIVO
Retiro → activo=False, registro en tabla Eliminado, registro en tabla Retiro
Eliminación permanente → borra Afiliado + Facturas + Documentos + SolicitudNovedad + SolicitudRetiro
                        CONSERVA Retiro (historial legal)
Reingreso → POST /afiliados limpia todo rastro anterior del doc antes de crear desde cero
```

### Reglas críticas
- Un afiliado con `activo=False` NO aparece en listados ni búsquedas activas
- El campo `doc` es unique solo para afiliados activos — un retirado puede reingresar con el mismo doc
- `fecha_afiliacion` es la fecha de afiliación al servicio, NO la fecha de ingreso al sistema (`fecha_ingreso`)
- Los afiliados en estado SUSPENDIDO siguen generando cobro salvo indicación explícita del cliente

---

## 2. Facturación

### Estados de factura
```
pendiente → pagado → planilla_pagada
```
- `pendiente`: factura emitida, sin pago registrado
- `pagado`: pago recibido, registrado en sistema
- `planilla_pagada`: pago verificado en planilla SS — estado final, no reversible

### Reglas de ingresos
- **Ingresos contables** = facturas con `estado IN ('pagado', 'planilla_pagada')`
- Facturas `pendiente` NO cuentan como ingreso — son cartera
- Facturas de afiliados retirados/eliminados son **historial real** — NUNCA filtrar por `activo` al calcular ingresos históricos
- `ingresos_adicionales` (comisiones, planillas verificables) suman al ingreso total y a la utilidad neta

### Campos de factura
- `banco`: banco por el que llegó el pago — obligatorio al marcar como pagado
- `ingresos`: monto total facturado al cliente
- `costos`: costo de la seguridad social del afiliado
- `utilidad`: `ingresos - costos - costo_adm`
- `periodo`: string descriptivo del período (ej. "Enero 2025")

---

## 3. Seguridad Social (Cálculos)

### Porcentajes base (configurables en Config)
| Concepto | Porcentaje empleador | Notas |
|---|---|---|
| EPS | 8.5% total (4% empleador aprox.) | Varía por tipo de cotizante |
| AFP | 16% total | Empleador paga la mayoría |
| ARL nivel 1 | 0.522% | Riesgo mínimo |
| ARL nivel 2 | 1.044% | |
| ARL nivel 3 | 2.436% | |
| ARL nivel 4 | 4.350% | |
| ARL nivel 5 | 6.960% | Riesgo máximo |
| CCF | 4% | Solo si salario > 1 SMMLV |
| SENA | 2% | Empresas > 10 empleados |
| ICBF | 3% | Empresas > 10 empleados |

### IBC (Ingreso Base de Cotización)
- IBC global default: **1,950,905 COP** (salario mínimo 2025 Colombia)
- Configurable por cliente en tabla `Config`
- Los cálculos de aportes usan el IBC del afiliado, no el global, si está definido

### Subtipos de cotizante
```
0  — Empleado regular
3  — Empleado parcial
4  — Pensionado
20 — Independiente
22 — Independiente por contrato
```
El subtipo afecta los porcentajes y conceptos aplicables.

---

## 4. Cobro

### Lógica de día de cobro
- Cada afiliado tiene `dia_cobro` (día del mes en que se genera el cobro)
- Estados de cobro: `HOY` / `VENCIDO` / `PROXIMO` / `COBRADO`
- `HOY`: `dia_cobro == día actual`
- `VENCIDO`: `dia_cobro < día actual` y sin pago del mes
- `PROXIMO`: `dia_cobro > día actual`
- `COBRADO`: factura del mes en estado `pagado` o `planilla_pagada`

### Regla de planilla
- `planilla` = suma de aportes SS del afiliado para el período
- El campo `plan` en cobro es el monto a recaudar por planilla de SS

---

## 5. Autenticación y Seguridad

### JWT
- Access token: **15 minutos** de vida
- Refresh token: rotation obligatoria — cada `/auth/refresh` invalida el token recibido en `token_blacklist` antes de emitir uno nuevo
- Blacklist en PostgreSQL, no en memoria — persiste entre reinicios
- `token_blacklist` se limpia periódicamente de tokens expirados

### Roles
| Rol | Permisos |
|---|---|
| `admin` | Acceso total a todos los módulos |
| `empleado` | Acceso operativo — sin módulos de configuración (Listas, Usuarios, Calculadora, Actividad) |
| `cliente` | Solo ve sus propios afiliados — filtro obligatorio por `cliente_ref` del token |

### Bloqueo por intentos fallidos
- Después de N intentos fallidos consecutivos → cuenta bloqueada temporalmente
- Registro en tabla `login_attempts`

---

## 6. Documentos

### Almacenamiento
- **Producción**: Cloudflare R2 — descarga via presigned URLs (no proxy)
- **Desarrollo**: disco local en `backend/uploads/`
- `upload_id` (UUID) en tabla `documentos` garantiza idempotencia — subir el mismo archivo dos veces retorna el registro existente

### Limpieza
- Si el commit a DB falla después de subir a R2 → se elimina el archivo de R2 automáticamente
- Al borrar permanentemente un afiliado → se eliminan sus documentos de R2

---

## 7. Caché

### Prefijos y TTLs
| Prefijo | Contenido | TTL |
|---|---|---|
| `afiliados:all` | Lista completa sin filtros | 180s |
| `afiliados:filtros` | Opciones de filtros (distinct) | 120s |
| `dashboard:` | Métricas del dashboard | configurable |
| `cobro:` | Estado de cobro por afiliado | configurable |

### Regla de invalidación
**TODA mutación** que afecte afiliados, facturas o configuración DEBE invalidar:
```python
cache_invalidar("cobro:")
cache_invalidar("dashboard:")
cache_invalidar("afiliados:")
```
No hacerlo causa datos desactualizados en dashboard y cobro.

---

## 8. Audit Trail

- **Toda mutación** (crear, editar, eliminar) genera registro en tabla `Actividad`
- Formato: `_log(db, username, "acción en pasado", "Módulo", "referencia")`
- Ejemplos: `"agregó un afiliado nuevo"`, `"editó una factura"`, `"aplicó retiro"`
- NO omitir en ninguna operación que modifique datos

---

## 9. Portal de Clientes

- Clientes acceden via `/portal` con rol `cliente`
- Solo ven sus propios afiliados — el backend filtra por `cliente_ref` del JWT
- Pueden crear solicitudes de novedad y retiro — quedan en estado `pendiente` hasta que admin las procese
- NO pueden aprobar ni rechazar solicitudes — solo crearlas

---

## 10. Planillas SS

- Una planilla por cliente por mes
- Estado: `pendiente` → `pagada`
- Al marcar planilla como pagada → las facturas asociadas pasan a `planilla_pagada`
- Las planillas agrupan todos los afiliados activos de un cliente en un período

---

## Errores Frecuentes en Producción (no repetir)

1. **Filtrar facturas por `activo` del afiliado** → pierde historial de afiliados retirados
2. **No invalidar caché en mutaciones** → dashboard y cobro muestran datos viejos
3. **No guardar nuevo refresh token en frontend** → usuario queda con token en blacklist, cierre de sesión forzado
4. **Comparar TIMESTAMP vs TIMESTAMPTZ en PostgreSQL** → usar `DateTime(timezone=True)` siempre
5. **Patrón TOCTOU en blacklist** → usar INSERT directo + captura de `IntegrityError`, no SELECT→INSERT
