"""
Jobs mensuales — ejecutado por Railway Cron el día 1 de cada mes a las 06:00 UTC.
Railway Cron: schedule = "0 6 1 * *", command = "python run_monthly.py"
"""
from dotenv import load_dotenv
load_dotenv()

import sys
import sentry_sdk

if dsn := __import__("os").getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=dsn, environment=__import__("os").getenv("RAILWAY_ENVIRONMENT", "development"))

from logger import logger as log
from utils.cron_runtime import en_ventana_cron, wait_for_db

if not en_ventana_cron(330, 390, "run_monthly", log):
    sys.exit(0)

from scheduler_jobs import (
    limpiar_tareas_mensuales,
    limpiar_novedades_antiguas,
    limpiar_planillas_antiguas,
)

log.info("run_monthly: inicio")

if wait_for_db("run_monthly", log):
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
