"""Esquema en un solo proceso, antes de que arranquen los workers.

`create_all` sigue siendo el que crea tablas nuevas. Alembic no se corre
dentro de uvicorn: cada worker abría su conexión y se bloqueaban entre sí.
Si la base no tiene revisión, se marca head (el esquema ya lo armó
create_all). Si ya tiene revisión, se aplican solo las que falten.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from database import engine, init_db

# Clave fija de int4 para que no choque con el candado de facturas.
_CANDADO = 847362911


def _revision_actual(conn):
    existe = conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    if not existe:
        return None
    return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def main() -> int:
    init_db()
    url = os.getenv("DATABASE_URL", "")
    if "postgresql" not in url and "postgres://" not in url:
        print("migrate_once: sqlite, sin alembic")
        return 0

    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _CANDADO})
        conn.commit()
        try:
            revision = _revision_actual(conn)
            if not revision:
                command.stamp(cfg, "head")
                print("migrate_once: base sin revisión, marcada en head")
            else:
                command.upgrade(cfg, "head")
                print(f"migrate_once: upgrade desde {revision}")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _CANDADO})
            conn.commit()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"migrate_once: fallo {exc}", file=sys.stderr)
        sys.exit(1)
