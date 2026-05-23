"""
Jobs diarios — ejecutado por Railway Cron a las 00:00 UTC.
Railway Cron: schedule = "0 0 * * *", command = "python run_daily.py"
"""
from dotenv import load_dotenv
load_dotenv()

import sys
import sentry_sdk

if dsn := __import__("os").getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=dsn, environment=__import__("os").getenv("RAILWAY_ENVIRONMENT", "development"))

from logger import logger as log
from utils.cron_runtime import en_ventana_cron, wait_for_db

if not en_ventana_cron(1425, 15, "run_daily", log, wrap_midnight=True):
    sys.exit(0)

from scheduler_jobs import (
    limpiar_notificaciones_diario,
    limpiar_token_blacklist,
    limpiar_actividad_antigua,
    limpiar_login_attempts,
)

log.info("run_daily: inicio")

if wait_for_db("run_daily", log):
    _jobs = [
        limpiar_notificaciones_diario,
        limpiar_token_blacklist,
        limpiar_actividad_antigua,
        limpiar_login_attempts,
    ]
    for job in _jobs:
        try:
            job()
        except Exception as _exc:
            log.error(f"run_daily: fallo en {job.__name__}: {_exc}")
            try:
                sentry_sdk.capture_exception(_exc)
            except Exception:
                pass
    log.info("run_daily: fin")
else:
    log.error("run_daily: abortado por falta de conexión a DB")
