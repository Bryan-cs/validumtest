"""Tareas, comentarios y notificaciones."""
from datetime import datetime, timezone
from sqlalchemy import or_
import models, schemas


_ESTADO_LABEL = {
    "pendiente":   "Pendiente",
    "en_proceso":  "En proceso",
    "completada":  "Completada",
    "finalizada":  "Finalizada",
}

def _tarea_to_dict(t, comentarios_map=None):
    coms = comentarios_map.get(t.id, []) if comentarios_map else []
    return {
        "id": t.id, "titulo": t.titulo, "descripcion": t.descripcion,
        "asignado_a": t.asignado_a, "creado_por": t.creado_por,
        "estado": t.estado,
        "fecha_limite": t.fecha_limite or "",
        "privada": bool(t.privada),
        "creado": t.creado.isoformat(),
        "completado_en": t.completado_en.isoformat() if t.completado_en else None,
        "finalizado_en": t.finalizado_en.isoformat() if t.finalizado_en else None,
        "finalizado_por": t.finalizado_por or "",
        "comentarios": [{"id": c.id, "usuario": c.usuario, "texto": c.texto,
                         "creado": c.creado.isoformat()} for c in coms]
    }

def _load_comments_map(db, task_ids):
    if not task_ids:
        return {}
    comments = db.query(models.TareaComentario)\
        .filter(models.TareaComentario.tarea_id.in_(task_ids))\
        .order_by(models.TareaComentario.creado).all()
    m = {}
    for c in comments:
        m.setdefault(c.tarea_id, []).append(c)
    return m

def create_tarea(db, data: schemas.TareaCreate):
    t = models.Tarea(**data.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    if not data.privada:
        db.add(models.Notificacion(
            usuario=data.asignado_a,
            mensaje=f"Nueva tarea asignada: {data.titulo}",
            tarea_id=t.id
        ))
        db.commit()
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def update_tarea(db, tarea_id: int, data: schemas.TareaUpdate, username: str, rol: str):
    t = db.query(models.Tarea).filter_by(id=tarea_id).first()
    if not t:
        return None
    if t.estado == "finalizada":
        return {"error": "no_editar_finalizada"}
    es_admin = rol == "admin"
    if not es_admin:
        if t.creado_por != username:
            return {"error": "unauthorized"}
        if t.estado != "pendiente":
            return {"error": "solo_pendiente"}
    patch = data.model_dump(exclude_none=True)
    if not es_admin:
        patch.pop("asignado_a", None)
    for k, v in patch.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def get_tareas(db, username: str, rol: str, skip: int = 0, limit: int = 200):
    q = db.query(models.Tarea)
    if rol != "admin":
        q = q.filter_by(asignado_a=username)
    q = q.filter(or_(models.Tarea.privada == False, models.Tarea.creado_por == username))
    total = q.count()
    tareas = q.order_by(models.Tarea.creado.desc()).offset(skip).limit(limit).all()
    cmap = _load_comments_map(db, [t.id for t in tareas])
    return {
        "total": total,
        "items": [_tarea_to_dict(t, cmap) for t in tareas],
    }

def cambiar_estado_tarea(db, tarea_id: int, nuevo_estado: str, usuario: str, nota: str = "", rol: str = ""):
    estados_validos = ["pendiente", "en_proceso", "completada"]
    if nuevo_estado not in estados_validos:
        return None
    t = db.query(models.Tarea).filter_by(id=tarea_id).with_for_update().first()
    if not t:
        return {"error": "not_found"}
    if rol != "admin" and t.asignado_a != usuario:
        return {"error": "unauthorized"}
    t.estado = nuevo_estado
    if nuevo_estado == "completada":
        t.completado_en = datetime.now(timezone.utc)
    if nota:
        db.add(models.TareaComentario(tarea_id=tarea_id, usuario=usuario, texto=nota))
    label_nuevo = _ESTADO_LABEL.get(nuevo_estado, nuevo_estado)
    db.add(models.Notificacion(
        usuario=t.creado_por,
        mensaje=f"{usuario} cambió la tarea '{t.titulo}' a: {label_nuevo}",
        tarea_id=tarea_id
    ))
    db.commit()
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def finalizar_tarea(db, tarea_id: int, admin_username: str):
    t = db.query(models.Tarea).filter_by(id=tarea_id).with_for_update().first()
    if not t: return None
    if t.estado != "completada":
        return {"error": "Solo se pueden finalizar tareas en estado 'completada'"}
    t.estado = "finalizada"
    t.finalizado_en = datetime.now(timezone.utc)
    t.finalizado_por = admin_username
    db.add(models.Notificacion(
        usuario=t.asignado_a,
        mensaje=f"Tu tarea '{t.titulo}' fue finalizada por {admin_username}",
        tarea_id=tarea_id
    ))
    db.commit()
    return _tarea_to_dict(t, _load_comments_map(db, [t.id]))

def add_comentario(db, tarea_id: int, data: schemas.TareaComentarioCreate):
    t = db.query(models.Tarea).filter_by(id=tarea_id).first()
    if not t: return None
    c = models.TareaComentario(tarea_id=tarea_id, **data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return {"id": c.id, "tarea_id": c.tarea_id, "usuario": c.usuario,
            "texto": c.texto, "creado": c.creado.isoformat()}

def get_notificaciones(db, username: str):
    items = db.query(models.Notificacion).filter_by(usuario=username)\
               .order_by(models.Notificacion.creado.desc()).limit(50).all()
    return [{"id": n.id, "mensaje": n.mensaje, "leida": n.leida,
             "tarea_id": n.tarea_id, "creado": n.creado.isoformat()} for n in items]

def marcar_notificaciones_leidas(db, username: str):
    db.query(models.Notificacion).filter_by(usuario=username, leida=False)\
      .update({"leida": True})
    db.commit()
