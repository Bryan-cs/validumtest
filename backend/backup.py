"""Backup automático de la base de datos SQLite.

Uso manual:   python backup.py
Automático:   configurado desde main.py con APScheduler (diario a las 2am).
En producción (Railway con PostgreSQL) este script no hace nada.
"""
import os
import sqlite3
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

    # Usar API nativa de SQLite para backup consistente (no shutil.copy2)
    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
        print(f"Backup creado: {dst}")
    finally:
        dst_conn.close()
        src_conn.close()

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
