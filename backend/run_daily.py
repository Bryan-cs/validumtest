"""
Jobs diarios — ejecutado por Railway Cron a las 00:00 UTC.
Railway Cron: schedule = "0 0 * * *", command = "python run_daily.py"
"""
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import time
from datetime import datetime, timezone
import sentry_sdk

if dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=dsn, environment=os.getenv("RAILWAY_ENVIRONMENT", "development"))

from logger import logger as log


def _en_ventana_cron() -> bool:
    """Verifica si estamos dentro de ±15 min de las 00:00 UTC (ventana del cron).
    Evita que los jobs corran en cada redeploy de Railway."""
    now = datetime.now(timezone.utc)
    minutos = now.hour * 60 + now.minute
    # Ventana: 23:45-00:15 UTC (minutos 1425-1440 o 0-15)
    en_ventana = minutos >= 1425 or minutos <= 15
    if not en_ventana:
        log.info(f"run_daily: fuera de ventana cron ({now.strftime('%H:%M')} UTC) — saliendo sin ejecutar")
    return en_ventana


def _wait_for_db(max_attempts: int = 6, delay: int = 10) -> bool:
    """Espera hasta que la DB esté lista (Railway internal DNS puede tardar al arrancar)."""
    from database import SessionLocal
    import sqlalchemy
    for attempt in range(1, max_attempts + 1):
        try:
            db = SessionLocal()
            db.execute(sqlalchemy.text("SELECT 1"))
            db.close()
            log.info(f"run_daily: DB lista (intento {attempt})")
            return True
        except Exception as e:
            log.warning(f"run_daily: DB no disponible (intento {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(delay)
    log.error("run_daily: DB no disponible tras todos los intentos — abortando")
    return False


# Guard: solo ejecutar dentro de la ventana del cron
if not _en_ventana_cron():
    sys.exit(0)

from scheduler_jobs import (
    limpiar_notificaciones_diario,
    limpiar_token_blacklist,
    limpiar_actividad_antigua,
    limpiar_login_attempts,
)

log.info("run_daily: inicio")

if _wait_for_db():
    limpiar_notificaciones_diario()
    limpiar_token_blacklist()
    limpiar_actividad_antigua()
    limpiar_login_attempts()
    log.info("run_daily: fin")
else:
    log.error("run_daily: abortado por falta de conexión a DB")
