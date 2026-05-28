"""Historial de actividad."""
from datetime import timezone, timedelta
import models
from models import COL_TZ


def get_actividad(db, modulo="", usuario="", desde="", hasta="",
                  skip: int = 0, limit: int = 200):
    from datetime import datetime as _dt
    q = db.query(models.Actividad)
    if modulo:  q = q.filter_by(modulo=modulo)
    if usuario: q = q.filter_by(usuario=usuario)
    if desde:
        try:
            # Medianoche Colombia → UTC para filtrar correctamente
            desde_col = _dt.fromisoformat(desde).replace(hour=0, minute=0, second=0, tzinfo=COL_TZ)
            q = q.filter(models.Actividad.fecha >= desde_col.astimezone(timezone.utc))
        except ValueError:
            pass
    if hasta:
        try:
            hasta_col = _dt.fromisoformat(hasta).replace(hour=23, minute=59, second=59, tzinfo=COL_TZ)
            q = q.filter(models.Actividad.fecha <= hasta_col.astimezone(timezone.utc))
        except ValueError:
            pass
    total = q.count()
    q = q.order_by(models.Actividad.id.desc())
    if limit > 0:
        q = q.offset(skip).limit(limit)
    rows = q.all()
    return {"total": total, "items": [
        {"id":r.id,"usuario":r.usuario,"accion":r.accion,"modulo":r.modulo,
         "detalle":r.detalle,"fecha":r.fecha.replace(tzinfo=timezone.utc).astimezone(COL_TZ).strftime("%d/%m/%Y %H:%M:%S") if r.fecha else ""}
        for r in rows
    ]}

def clear_actividad(db, user=""):
    db.query(models.Actividad).delete()
    db.add(models.Actividad(usuario=user, accion="limpió el historial de actividad",
                            modulo="Sistema", detalle="Historial borrado"))
    db.commit()
