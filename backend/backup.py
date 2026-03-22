"""Backup automático de la base de datos SQLite.

Uso manual:   python backup.py
Automático:   configurado desde main.py con APScheduler (diario a las 2am).
En producción (Railway con PostgreSQL) este script no hace nada.
"""
import os
import shutil
import datetime

DB_PATH     = os.path.join(os.path.dirname(__file__), "bbcfile.db")
BACKUP_DIR  = os.path.join(os.path.dirname(__file__), "backups")
MAX_BACKUPS = 7   # conservar los últimos 7 backups


def run_backup():
    if not os.path.exists(DB_PATH):
        print("bbcfile.db no encontrado — posiblemente usando PostgreSQL. Backup omitido.")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"bbcfile_{ts}.db")
    shutil.copy2(DB_PATH, dst)
    print(f"Backup creado: {dst}")

    # Eliminar backups más antiguos si hay más de MAX_BACKUPS
    archivos = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("bbcfile_") and f.endswith(".db")
    )
    for viejo in archivos[:-MAX_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUP_DIR, viejo))
            print(f"Backup antiguo eliminado: {viejo}")
        except OSError:
            pass


if __name__ == "__main__":
    run_backup()
