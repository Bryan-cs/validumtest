"""
Funciones de tareas programadas — compartidas por main.py (dev) y worker.py (prod).
Cada función es independiente: abre su propia sesión DB y la cierra al terminar.
"""
from datetime import datetime, timezone, timedelta
from const import MESES as _MESES


def limpiar_notificaciones_diario():
    """Elimina todas las notificaciones del día anterior al iniciar un nuevo día."""
    from database import SessionLocal
    from logger import logger as _log
    import models
    db = SessionLocal()
    try:
        hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = db.query(models.Notificacion).filter(models.Notificacion.creado < hoy).delete()
        db.commit()
        if count:
            _log.info(f"Limpieza: {count} notificaciones antiguas eliminadas")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza notificaciones: {e}")
    finally:
        db.close()


def limpiar_actividad_antigua():
    """Elimina registros de actividad con más de 90 días."""
    from database import SessionLocal
    from logger import logger as _log
    import models
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=7)
        count = db.query(models.Actividad).filter(models.Actividad.fecha < limite).delete()
        db.commit()
        if count:
            _log.info(f"Limpieza: {count} registros de actividad antiguos eliminados")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza actividad: {e}")
    finally:
        db.close()


def limpiar_novedades_antiguas():
    """Elimina novedades/solicitudes de portal con más de 30 días y sus documentos."""
    from database import SessionLocal
    from logger import logger as _log
    import models
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=30)
        total = 0
        for Model, ctx in [
            (models.NovedadPago, ['novedad_pago', 'resp_pago']),
            (models.SolicitudRetiro, ['novedad_retiro', 'resp_retiro']),
            (models.SolicitudNovedad, ['novedad_afil', 'resp_afil']),
        ]:
            viejos = db.query(Model).filter(Model.creado < limite).all()
            for item in viejos:
                from routers.documentos import _delete_file
                docs = db.query(models.Documento).filter(
                    models.Documento.contexto.in_(ctx),
                    models.Documento.contexto_id == item.id,
                ).all()
                for d in docs:
                    _delete_file(d.ruta)
                    db.delete(d)
                db.delete(item)
                total += 1
        db.commit()
        if total:
            _log.info(f"Limpieza: {total} novedades/solicitudes antiguas eliminadas (+docs)")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza novedades: {e}")
    finally:
        db.close()


def limpiar_token_blacklist():
    """Elimina tokens expirados de la blacklist."""
    from database import SessionLocal
    from logger import logger as _log
    import models
    db = SessionLocal()
    try:
        ahora = datetime.now(timezone.utc)
        count = db.query(models.TokenBlacklist).filter(models.TokenBlacklist.expires_at < ahora).delete()
        db.commit()
        if count:
            _log.info(f"Limpieza: {count} tokens expirados removidos de blacklist")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza token_blacklist: {e}")
    finally:
        db.close()


def limpiar_tareas_mensuales():
    """Elimina tareas finalizadas con más de 30 días para liberar espacio."""
    from database import SessionLocal
    from logger import logger as _log
    import models
    db = SessionLocal()
    try:
        limite = datetime.now(timezone.utc) - timedelta(days=30)
        count = db.query(models.Tarea).filter(
            models.Tarea.estado == "finalizada",
            models.Tarea.finalizado_en < limite,
        ).delete()
        db.commit()
        if count:
            _log.info(f"Limpieza: {count} tareas finalizadas antiguas eliminadas")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza tareas: {e}")
    finally:
        db.close()


def limpiar_login_attempts():
    """Elimina intentos de login con más de 24h — evita crecimiento indefinido de la tabla."""
    from database import SessionLocal
    from logger import logger as _log
    import models
    db = SessionLocal()
    try:
        import time
        limite = time.time() - 86400  # 24h en unix timestamp float
        count = db.query(models.LoginAttempt).filter(
            models.LoginAttempt.last_attempt < limite
        ).delete()
        db.commit()
        if count:
            _log.info(f"Limpieza: {count} registros de LoginAttempt antiguos eliminados")
    except Exception as e:
        db.rollback()
        _log.error(f"Error limpieza login_attempts: {e}")
    finally:
        db.close()


def limpiar_planillas_antiguas():
    """Elimina planillas anteriores al mes pasado de DB y R2 (cliente ya las descargó)."""
    from database import SessionLocal
    from logger import logger as _log
    from sqlalchemy import text
    db = SessionLocal()
    try:
        hoy = datetime.now(timezone.utc)
        if hoy.day < 2:
            return  # margen al inicio de mes
        if hoy.month == 1:
            mes_ant_idx, anio_ant = 12, hoy.year - 1
        else:
            mes_ant_idx, anio_ant = hoy.month - 1, hoy.year
        mes_ant = _MESES[mes_ant_idx - 1]
        mes_act = _MESES[hoy.month - 1]
        old_planillas = db.execute(text(
            "SELECT id FROM planillas_pago "
            "WHERE NOT (mes = :mes AND anio = :anio) "
            "AND NOT (mes = :mes_act AND anio = :anio_act)"
        ), {"mes": mes_ant, "anio": str(anio_ant),
            "mes_act": mes_act, "anio_act": str(hoy.year)}).fetchall()
        if not old_planillas:
            db.rollback()
            return
        ids = [int(r[0]) for r in old_planillas]
        docs = db.execute(text(
            "SELECT id, ruta FROM documentos "
            "WHERE contexto = 'planilla_pago' AND contexto_id = ANY(:ids)"
        ), {"ids": ids}).fetchall()
        # Eliminar archivos de R2 si está disponible
        try:
            from routers.documentos import _get_s3, _R2_BUCKET
            s3 = _get_s3()
            for doc_id, ruta in docs:
                if s3 and ruta and not ruta.startswith("uploads/"):
                    try:
                        s3.delete_object(Bucket=_R2_BUCKET, Key=ruta)
                    except Exception:
                        pass
        except Exception:
            pass
        for doc_id, _ in docs:
            db.execute(text("DELETE FROM documentos WHERE id = :did"), {"did": doc_id})
        db.execute(text("DELETE FROM planillas_pago WHERE id = ANY(:ids)"), {"ids": ids})
        db.commit()
        _log.info(f"Limpieza: {len(ids)} planillas antiguas y {len(docs)} archivos de R2 eliminados")
    except Exception as e:
        db.rollback()
        _log.warning(f"Error limpiando planillas antiguas: {e}")
    finally:
        db.close()
