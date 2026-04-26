"""
Jobs diarios — ejecutado por Railway Cron a las 00:00 UTC.
Railway Cron: schedule = "0 0 * * *", command = "python run_daily.py"
"""
from dotenv import load_dotenv
load_dotenv()

import os
import time
import sentry_sdk

if dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=dsn, environment=os.getenv("RAILWAY_ENVIRONMENT", "development"))

from logger import logger as log


def _wait_for_db(max_attempts: int = 5, delay: int = 5) -> bool:
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
