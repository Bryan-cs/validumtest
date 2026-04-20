"""
Jobs mensuales — ejecutado por Railway Cron el día 1 de cada mes a las 06:00 UTC.
Railway Cron: schedule = "0 6 1 * *", command = "python run_monthly.py"
"""
from dotenv import load_dotenv
load_dotenv()

import os
import sentry_sdk

if dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(dsn=dsn, environment=os.getenv("RAILWAY_ENVIRONMENT", "development"))

from logger import logger as log
from scheduler_jobs import (
    limpiar_tareas_mensuales,
    limpiar_novedades_antiguas,
    limpiar_planillas_antiguas,
)

log.info("run_monthly: inicio")
limpiar_tareas_mensuales()
limpiar_novedades_antiguas()
limpiar_planillas_antiguas()
log.info("run_monthly: fin")
