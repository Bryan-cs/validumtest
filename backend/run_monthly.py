"""
Jobs mensuales — ejecutado por Railway Cron el día 1 de cada mes a las 06:00 UTC.
Railway Cron: schedule = "0 6 1 * *", command = "python run_monthly.py"
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
    """Verifica si estamos dentro de ±30 min de las 06:00 UTC (ventana del cron).
    Evita que los jobs corran en cada redeploy de Railway."""
    now = datetime.now(timezone.utc)
    minutos = now.hour * 60 + now.minute
    # Ventana: 05:30-06:30 UTC (minutos 330-390)
    en_ventana = 330 <= minutos <= 390
    if not en_ventana:
        log.info(f"run_monthly: fuera de ventana cron ({now.strftime('%H:%M')} UTC) — saliendo sin ejecutar")
    return en_ventana


def _wait_for_db(max_attempts: int = 10, delay: int = 15) -> bool:
    """Espera hasta que la DB esté lista."""
    from database import SessionLocal
    import sqlalchemy
    for attempt in range(1, max_attempts + 1):
        try:
            db = SessionLocal()
            db.execute(sqlalchemy.text("SELECT 1"))
            db.close()
            log.info(f"run_monthly: DB lista (intento {attempt})")
            return True
        except Exception as e:
            log.warning(f"run_monthly: DB no disponible (intento {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(delay)
    log.error("run_monthly: DB no disponible tras todos los intentos — abortando")
    return False


# Guard: solo ejecutar dentro de la ventana del cron
if not _en_ventana_cron():
    sys.exit(0)

from scheduler_jobs import (
    limpiar_tareas_mensuales,
    limpiar_novedades_antiguas,
    limpiar_planillas_antiguas,
)

log.info("run_monthly: inicio")

if _wait_for_db():
    _jobs = [
        limpiar_tareas_mensuales,
        limpiar_novedades_antiguas,
        limpiar_planillas_antiguas,
    ]
    for job in _jobs:
        try:
            job()
        except Exception as _exc:
            log.error(f"run_monthly: fallo en {job.__name__}: {_exc}")
            try:
                sentry_sdk.capture_exception(_exc)
            except Exception:
                pass
    log.info("run_monthly: fin")
else:
    log.error("run_monthly: abortado por falta de conexión a DB")
