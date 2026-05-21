"""CRUD de retiros y eliminados."""
import json
from datetime import datetime
import models, schemas
from models import COL_TZ
from const import MESES
from crud_cache import cache_invalidar
from crud_helpers import _afiliado_to_dict, _log
from crud_afiliados import get_afiliado_by_doc


def get_retiros(db, anio="", mes="", doc="", skip: int = 0, limit: int = 500):
    q = db.query(models.Retiro)
    if doc:  q = q.filter(models.Retiro.doc == doc)
    if anio: q = q.filter_by(anio=anio)
    if mes:  q = q.filter_by(mes=mes)
    total = q.count()
    rows = q.order_by(models.Retiro.id.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [{"id":r.id,"nombre":r.nombre,"doc":r.doc,"empresa":r.empresa,
                   "fecha":r.fecha,"motivo":r.motivo,"obs":r.obs,"mes":r.mes,
                   "anio":r.anio,"registrado_por":r.registrado_por} for r in rows],
    }

def create_retiro(db, data: schemas.RetiroCreate):
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    afil = get_afiliado_by_doc(db, data.doc)
    if not afil: return None
    retiro_existente = db.query(models.Retiro).filter_by(doc=data.doc).first()
    if retiro_existente:
        raise HTTPException(400,
            f"El afiliado ya tiene un retiro registrado del {retiro_existente.fecha}")
    afil.estado = "RETIRADO"; afil.estado_srv = "RETIRADO"
    anio_actual = str(datetime.now(COL_TZ).year)
    mes_actual  = MESES[datetime.now(COL_TZ).month-1]
    r = models.Retiro(
        nombre=afil.nombre, doc=data.doc, empresa=afil.empresa,
        fecha=data.fecha, motivo=data.motivo, obs=data.obs,
        mes=mes_actual, anio=anio_actual, registrado_por=data.registrado_por,
    )
    db.add(r)
    elim_existente = db.query(models.Eliminado).filter_by(doc=afil.doc).first()
    if not elim_existente:
        db.add(models.Eliminado(
            nombre=afil.nombre, doc=afil.doc, empresa=afil.empresa,
            datos_completos=json.dumps(_afiliado_to_dict(afil)),
            fecha_eliminacion=datetime.now(COL_TZ).strftime("%Y-%m-%d"),
            mes=mes_actual, eliminado_por=data.registrado_por,
        ))
    afil.activo = False
    _log(db, data.registrado_por, "aplicó un retiro y movió a eliminados", "Retiros", afil.nombre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Otro empleado ya registró este retiro. Recargue la página.")
    db.refresh(r)
    return {"id":r.id,"nombre":r.nombre,"doc":r.doc,"fecha":r.fecha,"motivo":r.motivo}

def delete_retiro(db, id, user=""):
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:")
    r = db.query(models.Retiro).filter_by(id=id).first()
    if not r:
        return
    _log(db, user, "eliminó un retiro (→ eliminados)", "Retiros", r.nombre)
    afil = db.query(models.Afiliado).filter_by(doc=r.doc).first()
    if afil:
        elim_existente = db.query(models.Eliminado).filter_by(doc=r.doc).first()
        if not elim_existente:
            elim = models.Eliminado(
                nombre=afil.nombre, doc=afil.doc, empresa=afil.empresa,
                datos_completos=json.dumps(_afiliado_to_dict(afil)),
                fecha_eliminacion=datetime.now(COL_TZ).strftime("%Y-%m-%d"),
                mes=MESES[datetime.now(COL_TZ).month-1], eliminado_por=user,
            )
            db.add(elim)
        afil.activo = False
        _log(db, user, "afiliado movido a eliminados por eliminación de retiro", "Afiliados", afil.nombre)
    db.query(models.Retiro).filter_by(id=id).delete()
    db.commit()


def eliminado_a_retiro(db, eliminado_id, user=""):
    from fastapi import HTTPException
    e = db.query(models.Eliminado).filter_by(id=eliminado_id).first()
    if not e:
        raise HTTPException(404, "Eliminado no encontrado")
    retiro_existente = db.query(models.Retiro).filter_by(doc=e.doc).first()
    if retiro_existente:
        raise HTTPException(400, f"Ya existe un retiro registrado para el documento {e.doc}")
    anio_actual = str(datetime.now(COL_TZ).year)
    mes_actual  = MESES[datetime.now(COL_TZ).month-1]
    r = models.Retiro(
        nombre=e.nombre, doc=e.doc, empresa=e.empresa,
        fecha=e.fecha_eliminacion or datetime.now(COL_TZ).strftime("%Y-%m-%d"),
        motivo="ELIMINADO", obs="",
        mes=mes_actual, anio=anio_actual, registrado_por=user,
    )
    db.add(r)
    _log(db, user, "agregó a historial de retiros desde eliminados", "Retiros", e.nombre)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "nombre": r.nombre, "doc": r.doc}
