"""
Jobs diarios — ejecutado por Railway Cron a las 00:00 UTC.
Railway Cron: schedule = "0 0 * * *", command = "python run_daily.py"
"""
from dotenv import load_dotenv
load_dotenv()

import os
import sentry_sdk

if dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=dsn, environment=os.getenv("RAILWAY_ENVIRONMENT", "development"))

from logger import logger as log
from scheduler_jobs import (
    limpiar_notificaciones_diario,
    limpiar_token_blacklist,
    limpiar_actividad_antigua,
)

log.info("run_daily: inicio")
limpiar_notificaciones_diario()
limpiar_token_blacklist()
limpiar_actividad_antigua()
log.info("run_daily: fin")
