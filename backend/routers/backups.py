"""Router de Backups — gestión de respaldos en Cloudflare R2."""
import io
import re
import json
from typing import List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from database import get_db, SessionLocal
from routers.deps import require_admin
import models, crud

router = APIRouter(prefix="/backups", tags=["backups"])

_COL_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _get_r2():
    """Obtiene cliente S3 y bucket. Lanza HTTPException si no está disponible."""
    from routers.documentos import _get_s3, _R2_BUCKET
    s3 = _get_s3()
    if not s3:
        raise HTTPException(503, "R2 no disponible")
    return s3, _R2_BUCKET


# ─── Funciones de backup ────────────────────────────────────────────────────

def backup_db_to_r2():
    """Exporta todas las tablas como JSON y lo sube a Cloudflare R2."""
    from logger import logger as _log
    try:
        from routers.documentos import _get_s3, _R2_BUCKET
        s3 = _get_s3()
        if not s3:
            _log.warning("Backup: R2 no disponible, saltando backup")
            return
        # Exportar datos
        db = SessionLocal()
        try:
            insp = inspect(db.bind)
            tables = insp.get_table_names()
            backup_data = {}
            for table in tables:
                if table in ('alembic_version',):
                    continue
                rows = db.execute(text(f'SELECT * FROM "{table}"')).fetchall()
                col_names = list(db.execute(text(f'SELECT * FROM "{table}" LIMIT 0')).keys())
                backup_data[table] = {
                    "columns": col_names,
                    "rows": [
                        {col: (str(val) if val is not None and not isinstance(val, (int, float, bool)) else val)
                         for col, val in zip(col_names, row)}
                        for row in rows
                    ],
                    "count": len(rows),
                }
            dump = json.dumps(backup_data, ensure_ascii=False, indent=1).encode("utf-8")
        finally:
            db.close()
        # Subir a R2
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        key = f"backups/{ts}.json"
        s3.put_object(Bucket=_R2_BUCKET, Key=key, Body=dump)
        size_mb = len(dump) / (1024 * 1024)
        _log.info(f"Backup: {key} ({size_mb:.1f} MB) subido a R2")
        # Limpiezas post-backup
        _cleanup_old_backups(s3, _R2_BUCKET, _log)
        _cleanup_old_activity(_log)
        _cleanup_old_planillas(s3, _R2_BUCKET, _log)
    except Exception as e:
        _log.error(f"Backup: error general: {e}")


def _cleanup_old_backups(s3, bucket, _log):
    """Elimina backups con más de 30 días de R2."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        resp = s3.list_objects_v2(Bucket=bucket, Prefix="backups/")
        for obj in resp.get("Contents", []):
            if obj["LastModified"].replace(tzinfo=timezone.utc) < cutoff:
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
                _log.info(f"Backup: eliminado backup antiguo {obj['Key']}")
    except Exception as e:
        _log.warning(f"Backup: error limpiando backups antiguos: {e}")


def _cleanup_old_activity(_log):
    """Elimina registros de actividad con más de 90 días."""
    try:
        db = SessionLocal()
        try:
            result = db.execute(text("DELETE FROM actividad WHERE fecha < NOW() - INTERVAL '90 days'"))
            if result.rowcount > 0:
                db.commit()
                _log.info(f"Backup: limpiados {result.rowcount} registros de actividad > 90 días")
            else:
                db.rollback()
        finally:
            db.close()
    except Exception as e:
        _log.warning(f"Backup: error limpiando actividad antigua: {e}")


def _cleanup_old_planillas(s3, bucket, _log):
    """Elimina planillas anteriores al mes pasado (cliente ya las descargó)."""
    try:
        db = SessionLocal()
        try:
            hoy = datetime.now(timezone.utc)
            if hoy.day < 2:
                return  # Dar margen al inicio de mes
            if hoy.month == 1:
                mes_ant_idx, anio_ant = 12, hoy.year - 1
            else:
                mes_ant_idx, anio_ant = hoy.month - 1, hoy.year
            _MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                      "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
            mes_ant = _MESES[mes_ant_idx - 1]
            mes_act = _MESES[hoy.month - 1]
            # Buscar planillas antiguas (anteriores al mes pasado)
            old_planillas = db.execute(text(
                "SELECT id FROM planillas_pago WHERE NOT (mes = :mes AND anio = :anio) AND NOT (mes = :mes_act AND anio = :anio_act)"
            ), {"mes": mes_ant, "anio": str(anio_ant), "mes_act": mes_act, "anio_act": str(hoy.year)}).fetchall()
            if not old_planillas:
                db.rollback()
                return
            ids = [int(r[0]) for r in old_planillas]
            docs = db.execute(text(
                "SELECT id, ruta FROM documentos WHERE contexto = 'planilla_pago' AND contexto_id = ANY(:ids)"
            ), {"ids": ids}).fetchall()
            for doc_id, ruta in docs:
                if s3 and ruta and not ruta.startswith("uploads/"):
                    try: s3.delete_object(Bucket=bucket, Key=ruta)
                    except Exception: pass
                db.execute(text("DELETE FROM documentos WHERE id = :did"), {"did": doc_id})
            db.execute(text("DELETE FROM planillas_pago WHERE id = ANY(:ids)"), {"ids": ids})
            db.commit()
            _log.info(f"Backup: eliminadas {len(ids)} planillas antiguas y {len(docs)} archivos de R2")
        finally:
            db.close()
    except Exception as e:
        _log.warning(f"Backup: error limpiando planillas antiguas: {e}")


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
def listar_backups(token=Depends(require_admin)):
    """Lista los backups disponibles en R2."""
    try:
        s3, bucket = _get_r2()
        resp = s3.list_objects_v2(Bucket=bucket, Prefix="backups/")
        backups = []
        for obj in sorted(resp.get("Contents", []), key=lambda o: o["LastModified"], reverse=True):
            backups.append({
                "archivo": obj["Key"].replace("backups/", ""),
                "fecha": obj["LastModified"].isoformat(),
                "tamano_mb": round(obj["Size"] / (1024 * 1024), 2),
            })
        return {"total": len(backups), "backups": backups}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error listando backups: {e}")


@router.get("/{nombre}/descargar")
def descargar_backup(nombre: str, token=Depends(require_admin)):
    """Descarga un backup específico desde R2 con streaming real."""
    if "/" in nombre or "\\" in nombre:
        raise HTTPException(400, "Nombre inválido")
    try:
        s3, bucket = _get_r2()
        key = f"backups/{nombre}"
        resp = s3.get_object(Bucket=bucket, Key=key)
        # Streaming directo desde R2 sin cargar todo en RAM
        return StreamingResponse(
            resp["Body"].iter_chunks(chunk_size=64 * 1024),
            media_type="application/json" if nombre.endswith(".json") else "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{nombre}"',
                "Content-Length": str(resp.get("ContentLength", "")),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        if "NoSuchKey" in str(type(e).__name__) or "NoSuchKey" in str(e):
            raise HTTPException(404, "Backup no encontrado")
        raise HTTPException(500, f"Error descargando backup: {e}")


@router.post("/crear")
def crear_backup_manual(token=Depends(require_admin)):
    """Crea un backup manual inmediato."""
    backup_db_to_r2()
    try:
        s3, bucket = _get_r2()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        key = f"backups/{ts}.json"
        s3.head_object(Bucket=bucket, Key=key)
        return {"ok": True, "archivo": f"{ts}.json"}
    except Exception:
        pass
    return {"ok": True, "mensaje": "Backup ejecutado, revisa la lista de backups"}


@router.delete("/{nombre}")
def eliminar_backup(nombre: str, token=Depends(require_admin)):
    """Elimina un backup específico de R2."""
    if "/" in nombre or "\\" in nombre:
        raise HTTPException(400, "Nombre inválido")
    try:
        s3, bucket = _get_r2()
        key = f"backups/{nombre}"
        s3.delete_object(Bucket=bucket, Key=key)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error eliminando backup: {e}")


@router.post("/restaurar")
async def restaurar_backup(
    file: UploadFile = File(...),
    token=Depends(require_admin),
):
    """Restaura la base de datos desde un archivo JSON de backup."""
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Solo se aceptan archivos .json")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "Archivo de backup demasiado grande (máx 50 MB)")
    try:
        backup_data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(400, "Archivo JSON inválido")

    if not isinstance(backup_data, dict):
        raise HTTPException(400, "Formato de backup no reconocido")

    db = SessionLocal()
    restored = []
    errors = []
    try:
        inspector = inspect(db.bind)
        existing_tables = set(inspector.get_table_names())

        # Backup de seguridad antes de restaurar
        backup_db_to_r2()

        # Desactivar foreign keys temporalmente
        db.execute(text("SET session_replication_role = 'replica'"))

        for table_name, table_data in backup_data.items():
            if table_name not in existing_tables:
                errors.append(f"Tabla '{table_name}' no existe, saltada")
                continue
            rows = table_data.get("rows", [])
            columns = table_data.get("columns", [])
            if not rows or not columns:
                continue
            try:
                # Validar nombres de columnas
                for c in columns:
                    if not _COL_RE.match(c):
                        raise ValueError(f"Nombre de columna inválido: {c}")
                db.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
                count = 0
                for row in rows:
                    cols = ", ".join(f'"{c}"' for c in columns)
                    placeholders = ", ".join(f":v{i}" for i in range(len(columns)))
                    params = {f"v{i}": row.get(c) for i, c in enumerate(columns)}
                    db.execute(text(f'INSERT INTO "{table_name}" ({cols}) VALUES ({placeholders})'), params)
                    count += 1
                restored.append({"tabla": table_name, "filas": count})
            except Exception as e:
                errors.append(f"Error en '{table_name}': {str(e)[:200]}")
                db.rollback()
                db.execute(text("SET session_replication_role = 'replica'"))
                continue

        # Reactivar foreign keys
        db.execute(text("SET session_replication_role = 'origin'"))

        # Limpiar duplicados eliminados/afiliados
        db.execute(text("DELETE FROM eliminados WHERE doc IN (SELECT doc FROM afiliados)"))

        db.commit()
    except Exception as e:
        db.rollback()
        try:
            db.execute(text("SET session_replication_role = 'origin'"))
            db.commit()
        except Exception:
            pass
        raise HTTPException(500, f"Error restaurando: {e}")
    finally:
        db.close()

    return {
        "ok": True,
        "restaurado": restored,
        "errores": errors,
        "mensaje": "Se creó un backup de seguridad antes de restaurar",
    }
