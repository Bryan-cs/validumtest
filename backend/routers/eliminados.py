import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models, crud
from .deps import verify_token

router = APIRouter(prefix="/eliminados", tags=["eliminados"])


@router.get("")
def list_eliminados(db: Session = Depends(get_db), token=Depends(verify_token)):
    def _parse_datos(datos_completos):
        try:
            return json.loads(datos_completos or "{}")
        except Exception:
            return {}

    rows = db.query(models.Eliminado).order_by(models.Eliminado.id.desc()).all()
    return [
        {
            "id": r.id,
            "nombre": r.nombre,
            "doc": r.doc,
            "empresa": r.empresa,
            "fecha_eliminacion": r.fecha_eliminacion,
            "mes": r.mes,
            "eliminado_por": r.eliminado_por,
            "estado_planilla": r.estado_planilla,
            **{k: _parse_datos(r.datos_completos).get(k, "") for k in ("eps", "ccf", "fecha_afiliacion", "tipo_doc")},
        }
        for r in rows
    ]


@router.get("/{id}/preview")
def preview_eliminado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Retorna cuántos registros serán borrados junto con el eliminado."""
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e:
        raise HTTPException(404, "No encontrado")
    n_facturas    = db.query(models.Factura).filter_by(doc=e.doc).count()
    n_documentos  = db.query(models.Documento).filter_by(afiliado_doc=e.doc).count()
    n_solicitudes = (
        db.query(models.SolicitudNovedad).filter_by(afiliado_doc=e.doc).count() +
        db.query(models.SolicitudRetiro).filter_by(afiliado_doc=e.doc).count()
    )
    return {
        "nombre": e.nombre,
        "doc": e.doc,
        "facturas": n_facturas,
        "documentos": n_documentos,
        "solicitudes": n_solicitudes,
    }


@router.delete("/{id}")
def delete_eliminado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "No encontrado")
    nombre = e.nombre
    doc = e.doc
    try:
        db.query(models.Afiliado).filter_by(doc=doc).delete()
        db.query(models.Factura).filter_by(doc=doc).delete()
        db.query(models.Documento).filter_by(afiliado_doc=doc).delete()
        db.query(models.SolicitudNovedad).filter_by(afiliado_doc=doc).delete()
        db.query(models.SolicitudRetiro).filter_by(afiliado_doc=doc).delete()
        db.delete(e)
        crud._log(db, token.get("sub", "sistema"), "eliminó permanentemente un afiliado y todos sus registros", "Afiliados", nombre)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Error al eliminar")
    return {"ok": True}


_ESTADOS_PLANILLA_VALIDOS = {"retiro_pendiente", "planilla_hecha", "planilla_pagada", ""}


class BulkEstadoPlanilla(BaseModel):
    ids: list[int]
    estado: str = ""


@router.patch("/bulk/estado-planilla")
def set_estado_planilla_bulk(body: BulkEstadoPlanilla, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Cambia el estado de planilla de varios retirados a la vez."""
    if body.estado not in _ESTADOS_PLANILLA_VALIDOS:
        raise HTTPException(400, "Estado inválido")
    if not body.ids:
        return {"ok": True, "actualizados": 0, "estado_planilla": body.estado or None}
    nuevo = body.estado or None
    n = (db.query(models.Eliminado)
         .filter(models.Eliminado.id.in_(body.ids))
         .update({"estado_planilla": nuevo}, synchronize_session=False))
    db.commit()
    return {"ok": True, "actualizados": n, "estado_planilla": nuevo}


@router.patch("/{id}/estado-planilla")
def set_estado_planilla(id: int, estado: str, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Actualiza el estado de planilla: retiro_pendiente | planilla_hecha | planilla_pagada | null"""
    ESTADOS_VALIDOS = {"retiro_pendiente", "planilla_hecha", "planilla_pagada", ""}
    if estado not in ESTADOS_VALIDOS:
        raise HTTPException(400, f"Estado inválido. Valores: {', '.join(s for s in ESTADOS_VALIDOS if s)}")
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e:
        raise HTTPException(404, "No encontrado")
    e.estado_planilla = estado or None
    db.commit()
    return {"ok": True, "estado_planilla": e.estado_planilla}


@router.post("/{id}/restaurar")
def restaurar_eliminado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    e = db.query(models.Eliminado).filter_by(id=id).first()
    if not e: raise HTTPException(404, "No encontrado")
    existing = db.query(models.Afiliado).filter_by(doc=e.doc, activo=True).first()
    if existing: raise HTTPException(400, f"Ya existe un afiliado activo con documento {e.doc}")

    try:
        datos = json.loads(e.datos_completos or "{}")
        if not datos or not datos.get("nombre") or not datos.get("doc"):
            raise ValueError("Datos incompletos")
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(400, "Los datos del afiliado eliminado están corruptos y no se puede restaurar")

    srvs = datos.get("servicios", [])
    srvs_str = json.dumps(srvs) if isinstance(srvs, list) else (srvs or "[]")
    registrado_original = datos.get("registrado_por", token.get("sub", "sistema"))

    a = db.query(models.Afiliado).filter_by(doc=e.doc).first()
    if a:
        a.activo = True
        a.estado = "ACTIVO"
        a.estado_srv = "ACTIVO"
        a.nombre = datos.get("nombre", a.nombre)
        a.empresa = datos.get("empresa", a.empresa)
        a.servicios = srvs_str
        a.eps = datos.get("eps", "")
        a.arl = datos.get("arl", "")
        a.ccf = datos.get("ccf", "")
        a.afp = datos.get("afp", "")
        a.subtipo = datos.get("subtipo", "0")
        a.cliente_txt = datos.get("cliente_txt", "")
        a.cargo = datos.get("cargo", "")
        a.tel = datos.get("tel", "")
        a.email = datos.get("email", "")
        a.novedades = ""
        a.ibc = datos.get("ibc")
        a.fecha_ingreso = datos.get("fecha_ingreso", "")
        a.fecha_afiliacion = datos.get("fecha_afiliacion", "")
        a.registrado_por = registrado_original
    else:
        a = models.Afiliado(
            nombre=datos.get("nombre", e.nombre), doc=e.doc,
            empresa=datos.get("empresa", e.empresa),
            estado="ACTIVO", estado_srv="ACTIVO", activo=True,
            servicios=srvs_str,
            eps=datos.get("eps", ""), arl=datos.get("arl", ""),
            ccf=datos.get("ccf", ""), afp=datos.get("afp", ""),
            subtipo=datos.get("subtipo", "0"),
            cliente_txt=datos.get("cliente_txt", ""),
            cargo=datos.get("cargo", ""), tel=datos.get("tel", ""),
            email=datos.get("email", ""),
            novedades="",
            ibc=datos.get("ibc"), fecha_ingreso=datos.get("fecha_ingreso", ""),
            fecha_afiliacion=datos.get("fecha_afiliacion", ""),
            registrado_por=registrado_original,
        )
        db.add(a)

    db.query(models.SolicitudRetiro).filter_by(afiliado_doc=e.doc).delete()
    db.query(models.Factura).filter_by(doc=e.doc, afiliado_eliminado=True).update(
        {"afiliado_eliminado": False})

    db.delete(e)
    crud._log(db, token.get("sub", "sistema"), "restauró un afiliado eliminado", "Afiliados", e.nombre)
    crud.cache_invalidar("cobro:")
    crud.cache_invalidar("afiliados:")
    crud.cache_invalidar("dashboard:")
    crud.cache_invalidar("dashboard_clientes:")
    db.commit()

    cliente_txt = datos.get("cliente_txt", "")
    if cliente_txt:
        from .deps import invalidate_user_cache
        usuarios_cliente = db.query(models.Usuario).filter_by(cliente_ref=cliente_txt).all()
        for u in usuarios_cliente:
            invalidate_user_cache(u.username)
            crud.cache_invalidar(f"usuario_rol:{u.username}")
    return {"ok": True, "nombre": e.nombre}

