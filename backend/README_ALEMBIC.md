# Alembic — Migraciones de base de datos

## Comandos

```bash
# Crear nueva migración automática
alembic revision --autogenerate -m "descripción del cambio"

# Aplicar migraciones pendientes
alembic upgrade head

# Ver historial
alembic history

# Ver estado actual
alembic current
```
