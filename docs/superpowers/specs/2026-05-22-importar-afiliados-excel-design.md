# Importar Afiliados desde Excel — Design Spec
**Fecha:** 2026-05-22  
**Estado:** Aprobado

## Problema

Onboarding de cliente nuevo requiere ingresar 30–80 afiliados uno a uno. No existe importación masiva.

## Solución

Template Excel descargable + upload con validación fila por fila + preview antes de confirmar. Importación parcial: filas válidas se crean, filas con error se omiten y se reportan.

## Flujo de usuario

1. Afiliados → botón "⬇ Plantilla" → descarga `plantilla_afiliados.xlsx`
2. Usuario llena datos en Excel
3. Botón "⬆ Importar Excel" → abre modal
4. Modal paso 1: drag & drop o selector de archivo `.xlsx`
5. Modal paso 2 (tras subir): tabla preview con filas coloreadas
6. Botón "Crear N afiliados" → importa solo filas válidas → toast con resumen

## Endpoints backend

### GET `/afiliados/importar/template`
- Requiere: `admin` o `empleado`
- Genera `.xlsx` con `openpyxl` (ya instalado)
- Fila 1: headers en negrita con fondo gris
- Fila 2: ejemplo completo con datos reales ficticios
- Headers: `nombre` `doc` `tipo_doc` `empresa` `cliente_txt` `eps` `afp` `ccf` `ibc` `fecha_afiliacion` `cargo` `tel` `estado_srv`
- Descarga: `Content-Disposition: attachment; filename=plantilla_afiliados.xlsx`

### POST `/afiliados/importar/preview`
- Requiere: `admin` o `empleado`
- Body: `multipart/form-data` con archivo `.xlsx`
- Lee con `openpyxl`, itera filas desde la 2 (fila 1 = headers)
- Retorna JSON:
```json
{
  "total": 10,
  "validas": 8,
  "errores": 2,
  "filas": [
    { "fila": 2, "estado": "ok", "data": {...} },
    { "fila": 3, "estado": "error", "errores": ["doc duplicado"], "data": {...} },
    { "fila": 4, "estado": "warning", "warnings": ["EPS 'COOSALUD' no está en listas"], "data": {...} }
  ]
}
```

**Validaciones por fila:**

| Campo | Regla | Tipo |
|---|---|---|
| `nombre` | requerido, no vacío | error |
| `doc` | requerido, no vacío | error |
| `empresa` | requerido, no vacío | error |
| `doc` | no existe ya en `afiliados` activos | error |
| `ibc` | si > 0: >= SMMLV (1_300_000) | error |
| `fecha_afiliacion` | formato `YYYY-MM-DD` si presente | error |
| `eps` / `afp` / `ccf` | no está en tabla `listas` | warning (no bloquea) |
| `tipo_doc` | no es CC/CE/PA/NIT | warning |
| `estado_srv` | no es valor válido | warning, default ACTIVO |

### POST `/afiliados/importar/confirmar`
- Requiere: `admin` o `empleado`
- Body: `{ "filas": [ {...data}, ... ] }` — solo filas con `estado='ok'` o `estado='warning'`
- Llama `crud_afiliados.create_afiliado()` por cada fila en un loop con try/except individual
- Log de auditoría por cada afiliado creado (`_log()`)
- Retorna: `{ "creados": N, "fallidos": M, "errores": [...] }`

## Frontend — `Afiliados.jsx`

### Botones en topbar (junto a "Nuevo afiliado")
```
[⬇ Plantilla]  [⬆ Importar Excel]  [+ Nuevo afiliado]
```

### Modal importación (2 pasos, mismo patrón que modales existentes)

**Paso 1 — Upload:**
- Área drag & drop o `<input type="file" accept=".xlsx">`
- Botón "⬇ Descargar plantilla" como link secundario
- Al seleccionar archivo: POST automático a `/preview`, muestra spinner

**Paso 2 — Preview:**
- Resumen: `8 válidas / 2 con error de 10 filas`
- Tabla con columnas: `#fila`, `Nombre`, `Doc`, `Empresa`, `Estado`
  - Verde: fila válida
  - Rojo: fila con error bloqueante + mensaje de error
  - Ámbar: fila con warning (se importará igual)
- Botón "Crear 8 afiliados" → POST a `/confirmar` → cierra modal + toast + invalida query afiliados
- Botón "Cancelar"

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `backend/routers/afiliados.py` | 3 nuevos endpoints (template, preview, confirmar) |
| `frontend/src/pages/Afiliados.jsx` | Botones topbar + modal 2 pasos |

## Sin cambios de modelo / migración

No se requiere cambio de DB. Se reutiliza `create_afiliado()` existente.

## Tests

- `test_importar_template_descarga_xlsx`: GET → 200 + content-type Excel
- `test_importar_preview_valida_requeridos`: fila sin nombre → error
- `test_importar_preview_doc_duplicado`: doc ya en DB → error
- `test_importar_preview_ibc_bajo_smmlv`: ibc=500000 → error
- `test_importar_confirmar_crea_afiliados`: 3 filas válidas → 3 creados en DB
- `test_importar_confirmar_parcial`: 2 válidas + 1 con error → solo crea las 2 válidas
