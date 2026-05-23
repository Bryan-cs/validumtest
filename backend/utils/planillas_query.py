"""Consultas compartidas de planillas SS con documentos adjuntos."""
from sqlalchemy.orm import Session
import models


def docs_by_planilla_map(db: Session, planilla_ids: list[int]) -> dict:
    if not planilla_ids:
        return {}
    all_docs = db.query(models.Documento).filter(
        models.Documento.contexto == "planilla_pago",
        models.Documento.contexto_id.in_(planilla_ids),
    ).all()
    out = {}
    for d in all_docs:
        out.setdefault(d.contexto_id, []).append(d)
    return out


def planilla_to_dict(p: models.PlanillaPago, docs: list) -> dict:
    return {
        "id": p.id,
        "cliente_ref": p.cliente_ref,
        "mes": p.mes,
        "anio": p.anio,
        "observaciones": p.observaciones,
        "subido_por": getattr(p, "subido_por", None),
        "creado": p.creado.isoformat() if p.creado else None,
        "archivos": [{"id": d.id, "nombre": d.nombre, "tamano": d.tamano} for d in docs],
    }


def list_planillas_with_docs(db: Session, rows: list) -> list[dict]:
    if not rows:
        return []
    docs_map = docs_by_planilla_map(db, [p.id for p in rows])
    return [planilla_to_dict(p, docs_map.get(p.id, [])) for p in rows]
