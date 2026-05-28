"""Helpers compartidos para scripts cron (run_daily / run_monthly)."""
import time
from datetime import datetime, timezone


def en_ventana_cron(min_inicio: int, min_fin: int, etiqueta: str, log, *, wrap_midnight: bool = False) -> bool:
    """True si la hora UTC actual está en la ventana (minutos desde medianoche)."""
    now = datetime.now(timezone.utc)
    minutos = now.hour * 60 + now.minute
    if wrap_midnight:
        en_ventana = minutos >= min_inicio or minutos <= min_fin
    else:
        en_ventana = min_inicio <= minutos <= min_fin
    if not en_ventana:
        log.info(f"{etiqueta}: fuera de ventana cron ({now.strftime('%H:%M')} UTC) — saliendo sin ejecutar")
    return en_ventana


def wait_for_db(etiqueta: str, log, max_attempts: int = 15, delay: int = 20, warmup: int = 10) -> bool:
    """Espera a que la DB esté disponible con reintentos.

    warmup: segundos de espera antes del primer intento (Railway private DNS tarda en resolverse
    en cold starts — sin este sleep el primer intento falla por DNS antes de que la red esté lista).
    """
    from database import SessionLocal
    import sqlalchemy
    if warmup:
        log.info(f"{etiqueta}: esperando {warmup}s para warm-up de red privada…")
        time.sleep(warmup)
    for attempt in range(1, max_attempts + 1):
        try:
            db = SessionLocal()
            db.execute(sqlalchemy.text("SELECT 1"))
            db.close()
            log.info(f"{etiqueta}: DB lista (intento {attempt})")
            return True
        except Exception as e:
            log.warning(f"{etiqueta}: DB no disponible (intento {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(delay)
    log.error(f"{etiqueta}: DB no disponible tras todos los intentos — abortando")
    return False
