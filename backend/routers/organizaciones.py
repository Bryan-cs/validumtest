"""Panel del superadmin: gestión de organizaciones (tenants) y sus usuarios.

Todas las rutas requieren rol superadmin. No usa tenant_scope: el superadmin opera a través de
todas las organizaciones, por lo que el ContextVar queda en None y las consultas no se auto-filtran.
"""
import re
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, provision_organizacion
import models, schemas, crud
from .deps import require_superadmin

router = APIRouter(prefix="/organizaciones", tags=["organizaciones"])


def _slugify(texto: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-')
    return s or "org"


def _slug_unico(db: Session, base: str) -> str:
    slug = base
    i = 2
    while db.query(models.Organizacion).filter_by(slug=slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


def _org_out(db: Session, org: models.Organizacion) -> dict:
    total_u = db.query(func.count(models.Usuario.id)).filter_by(organizacion_id=org.id).scalar()
    total_a = db.query(func.count(models.Afiliado.id)).filter(
        models.Afiliado.organizacion_id == org.id).scalar()
    return {"id": org.id, "nombre": org.nombre, "slug": org.slug, "activo": bool(org.activo),
            "total_usuarios": total_u or 0, "total_afiliados": total_a or 0}


@router.get("")
def list_organizaciones(db: Session = Depends(get_db), token=Depends(require_superadmin)):
    orgs = db.query(models.Organizacion).order_by(models.Organizacion.creado.desc()).all()
    return [_org_out(db, o) for o in orgs]


def _bucket_estado(estado: str) -> str:
    """Normaliza estado_srv a bucket del dashboard. Datos reales mezclan formatos
    ('NO_ENCONTRADO', 'NO ENCONTRADO', 'NO AFILIADO', etc.)."""
    e = (estado or "").upper().replace("_", " ").strip()
    if e == "ACTIVO":
        return "activos"
    if e == "SUSPENDIDO":
        return "suspendidos"
    if e.startswith("NO "):          # NO ENCONTRADO | NO AFILIADO
        return "no_encontrados"
    return "otros"


@router.get("/dashboard")
def dashboard_organizaciones(db: Session = Depends(get_db), token=Depends(require_superadmin)):
    """Dashboard consolidado del superadmin: estados de afiliados por organización.
    Superadmin no tiene organización activa → las consultas NO se auto-filtran (ve todas)."""
    orgs = db.query(models.Organizacion).order_by(models.Organizacion.creado.desc()).all()
    # Conteo por (organización, estado_srv) de afiliados vigentes, en una sola query
    rows = (db.query(models.Afiliado.organizacion_id, models.Afiliado.estado_srv,
                     func.count(models.Afiliado.id))
            .filter(models.Afiliado.activo == True)
            .group_by(models.Afiliado.organizacion_id, models.Afiliado.estado_srv)
            .all())
    stats = {}   # org_id -> buckets
    for org_id, estado, n in rows:
        b = stats.setdefault(org_id, {"total": 0, "activos": 0, "suspendidos": 0,
                                      "no_encontrados": 0, "otros": 0, "detalle": {}})
        b["total"] += n
        b[_bucket_estado(estado)] += n
        clave = (estado or "SIN ESTADO").upper().replace("_", " ").strip()
        b["detalle"][clave] = b["detalle"].get(clave, 0) + n
    usuarios = dict(db.query(models.Usuario.organizacion_id, func.count(models.Usuario.id))
                    .filter(models.Usuario.organizacion_id.isnot(None))
                    .group_by(models.Usuario.organizacion_id).all())
    vacio = {"total": 0, "activos": 0, "suspendidos": 0, "no_encontrados": 0, "otros": 0, "detalle": {}}
    items = [{
        "id": o.id, "nombre": o.nombre, "slug": o.slug, "activo": bool(o.activo),
        "usuarios": usuarios.get(o.id, 0),
        **stats.get(o.id, vacio),
    } for o in orgs]
    totales = {k: sum(i[k] for i in items) for k in
               ("total", "activos", "suspendidos", "no_encontrados", "otros", "usuarios")}
    return {"organizaciones": items, "totales": totales}


@router.post("", status_code=201)
def create_organizacion(data: schemas.OrganizacionCreate,
                        db: Session = Depends(get_db), token=Depends(require_superadmin)):
    # username admin único global (login sin selector de organización)
    if crud.get_user_by_username(db, data.admin_username):
        raise HTTPException(400, f"El usuario '{data.admin_username}' ya existe")
    slug = _slug_unico(db, _slugify(data.slug or data.nombre))
    org = provision_organizacion(
        db, nombre=data.nombre, slug=slug,
        admin_username=data.admin_username.lower(),
        admin_password=data.admin_password,
        admin_nombre=data.admin_nombre,
    )
    return _org_out(db, org)


@router.patch("/{org_id}")
def update_organizacion(org_id: int, data: schemas.OrganizacionUpdate,
                        db: Session = Depends(get_db), token=Depends(require_superadmin)):
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    if data.nombre is not None:
        org.nombre = data.nombre
    if data.slug is not None:
        org.slug = _slug_unico(db, _slugify(data.slug))
    if data.activo is not None:
        org.activo = data.activo
    if data.precio_afiliado is not None:
        org.precio_afiliado = data.precio_afiliado
    db.commit()
    return _org_out(db, org)


PRECIO_AFILIADO_DEFAULT = 30_000   # COP por afiliado activo/mes


def _calc_items_ingresos(db: Session) -> list:
    """Calcula la facturación en vivo por organización (afiliados activos × precio)."""
    orgs = db.query(models.Organizacion).order_by(models.Organizacion.creado.desc()).all()
    counts = dict(db.query(models.Afiliado.organizacion_id, func.count(models.Afiliado.id))
                  .filter(models.Afiliado.activo == True)
                  .group_by(models.Afiliado.organizacion_id).all())
    items = []
    for o in orgs:
        precio = float(o.precio_afiliado) if o.precio_afiliado is not None else PRECIO_AFILIADO_DEFAULT
        n = counts.get(o.id, 0)
        items.append({
            "id": o.id, "nombre": o.nombre, "slug": o.slug, "activo": bool(o.activo),
            "afiliados": n,
            "precio_afiliado": precio,
            "ingreso_mensual": n * precio,
            "ingreso_anual": n * precio * 12,
        })
    return items


@router.get("/ingresos")
def ingresos_organizaciones(db: Session = Depends(get_db), token=Depends(require_superadmin)):
    """Resumen de ingresos del SaaS: cada organización paga precio_afiliado (COP) por
    afiliado activo al mes. El precio es editable por organización (PATCH /organizaciones/{id})."""
    items = _calc_items_ingresos(db)
    totales = {
        "afiliados": sum(i["afiliados"] for i in items),
        "ingreso_mensual": sum(i["ingreso_mensual"] for i in items),
        "ingreso_anual": sum(i["ingreso_anual"] for i in items),
        "organizaciones_activas": sum(1 for i in items if i["activo"]),
    }
    # Refrescar el snapshot del mes en curso (los meses pasados quedan congelados)
    _snapshot_mes_actual(db, items)
    return {"organizaciones": items, "totales": totales, "precio_default": PRECIO_AFILIADO_DEFAULT}


MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _snapshot_mes_actual(db: Session, items: list):
    """Upsert del snapshot de facturación del mes en curso para cada organización."""
    from models import COL_TZ
    from datetime import datetime
    hoy = datetime.now(COL_TZ)
    for it in items:
        row = db.query(models.IngresoMensualOrg).filter_by(
            organizacion_id=it["id"], anio=hoy.year, mes=hoy.month).first()
        if not row:
            row = models.IngresoMensualOrg(organizacion_id=it["id"], anio=hoy.year, mes=hoy.month)
            db.add(row)
        row.afiliados = it["afiliados"]
        row.precio = it["precio_afiliado"]
        row.ingreso = it["ingreso_mensual"]
    db.commit()


@router.get("/ingresos-mensuales")
def ingresos_mensuales(anio: int = 0, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    """Resumen mensual de facturación: afiliados facturados e ingreso por mes (con desglose por
    organización). El mes en curso se refresca en cada consulta; los anteriores están congelados."""
    from models import COL_TZ
    from datetime import datetime
    hoy = datetime.now(COL_TZ)
    if not anio:
        anio = hoy.year
    # Asegurar snapshot fresco del mes en curso
    _snapshot_mes_actual(db, _calc_items_ingresos(db))

    nombres_org = {o.id: {"nombre": o.nombre, "slug": o.slug}
                   for o in db.query(models.Organizacion).all()}
    rows = (db.query(models.IngresoMensualOrg)
            .filter(models.IngresoMensualOrg.anio == anio)
            .order_by(models.IngresoMensualOrg.mes).all())
    anios = sorted({r[0] for r in db.query(models.IngresoMensualOrg.anio).distinct().all()}, reverse=True)

    meses = {}
    for r in rows:
        m = meses.setdefault(r.mes, {"mes": r.mes, "nombre": MESES_ES[r.mes],
                                     "afiliados": 0, "ingreso": 0.0, "organizaciones": []})
        m["afiliados"] += r.afiliados or 0
        m["ingreso"] += float(r.ingreso or 0)
        org_info = nombres_org.get(r.organizacion_id, {"nombre": f"Org {r.organizacion_id}", "slug": ""})
        m["organizaciones"].append({
            "id": r.organizacion_id, "nombre": org_info["nombre"], "slug": org_info["slug"],
            "afiliados": r.afiliados or 0, "precio": float(r.precio or 0), "ingreso": float(r.ingreso or 0),
        })
    lista_meses = [meses[k] for k in sorted(meses.keys())]
    return {
        "anio": anio,
        "anios_disponibles": anios or [anio],
        "meses": lista_meses,
        "totales": {
            "afiliados_prom": round(sum(m["afiliados"] for m in lista_meses) / len(lista_meses), 1) if lista_meses else 0,
            "ingreso_total": sum(m["ingreso"] for m in lista_meses),
        },
    }


@router.delete("/{org_id}")
def delete_organizacion(org_id: int, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    # Borrado explícito de TODOS los datos de la organización. No dependemos de ON DELETE CASCADE:
    # SQLite no lo aplica por defecto (dejaría filas huérfanas → colisiones de unicidad al recrear).
    from tenant import _tenant_models
    for modelo in _tenant_models():
        db.query(modelo).filter(modelo.organizacion_id == org_id).delete(synchronize_session=False)
    db.query(models.Usuario).filter_by(organizacion_id=org_id).delete(synchronize_session=False)
    db.query(models.IngresoMensualOrg).filter_by(organizacion_id=org_id).delete(synchronize_session=False)
    db.query(models.FacturaOrg).filter_by(organizacion_id=org_id).delete(synchronize_session=False)
    db.delete(org)
    db.commit()
    return {"ok": True}


# ─── Facturación del SaaS a las organizaciones ────────────────────────────────

def _factura_out(f: models.FacturaOrg, nombre_org: str = "", slug: str = "") -> dict:
    return {
        "id": f.id, "organizacion_id": f.organizacion_id,
        "nombre": nombre_org, "slug": slug,
        "anio": f.anio, "mes": f.mes, "periodo": f"{MESES_ES[f.mes]} {f.anio}",
        "afiliados": f.afiliados, "precio": float(f.precio or 0), "monto": float(f.monto or 0),
        "estado": f.estado,
        "creado": f.creado.isoformat() if f.creado else None,
        "pagada_en": f.pagada_en.isoformat() if f.pagada_en else None,
    }


@router.post("/{org_id}/facturar", status_code=201)
def facturar_organizacion(org_id: int, mes: int = 0, anio: int = 0,
                          db: Session = Depends(get_db), token=Depends(require_superadmin)):
    """Emite la factura del período (por defecto el mes en curso) para una organización:
    afiliados activos × precio vigente. Una sola factura por organización/mes."""
    from models import COL_TZ
    from datetime import datetime
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    hoy = datetime.now(COL_TZ)
    mes = mes or hoy.month
    anio = anio or hoy.year
    if not 1 <= mes <= 12:
        raise HTTPException(422, "mes debe estar entre 1 y 12")
    if db.query(models.FacturaOrg).filter_by(organizacion_id=org_id, anio=anio, mes=mes).first():
        raise HTTPException(400, f"{org.nombre} ya tiene factura de {MESES_ES[mes]} {anio}")
    n = db.query(func.count(models.Afiliado.id)).filter(
        models.Afiliado.organizacion_id == org_id,
        models.Afiliado.activo == True).scalar() or 0
    precio = float(org.precio_afiliado) if org.precio_afiliado is not None else PRECIO_AFILIADO_DEFAULT
    f = models.FacturaOrg(organizacion_id=org_id, anio=anio, mes=mes,
                          afiliados=n, precio=precio, monto=n * precio)
    db.add(f); db.commit(); db.refresh(f)
    return _factura_out(f, org.nombre, org.slug)


@router.get("/facturas")
def facturas_organizaciones(anio: int = 0, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    """Facturas emitidas a las organizaciones, más recientes primero."""
    q = db.query(models.FacturaOrg)
    if anio:
        q = q.filter(models.FacturaOrg.anio == anio)
    rows = q.order_by(models.FacturaOrg.anio.desc(), models.FacturaOrg.mes.desc(),
                      models.FacturaOrg.id.desc()).all()
    orgs = {o.id: o for o in db.query(models.Organizacion).all()}
    items = [_factura_out(f, orgs[f.organizacion_id].nombre if f.organizacion_id in orgs else "",
                          orgs[f.organizacion_id].slug if f.organizacion_id in orgs else "")
             for f in rows]
    return {
        "facturas": items,
        "totales": {
            "pendiente": sum(i["monto"] for i in items if i["estado"] == "pendiente"),
            "pagado": sum(i["monto"] for i in items if i["estado"] == "pagada"),
        },
    }


@router.patch("/facturas/{factura_id}/pagar")
def pagar_factura_org(factura_id: int, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    from datetime import datetime, timezone as _tz
    f = db.query(models.FacturaOrg).filter_by(id=factura_id).first()
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    f.estado = "pagada"
    f.pagada_en = datetime.now(_tz.utc)
    db.commit()
    return {"ok": True, "estado": f.estado}


@router.delete("/facturas/{factura_id}")
def anular_factura_org(factura_id: int, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    f = db.query(models.FacturaOrg).filter_by(id=factura_id).first()
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    db.delete(f); db.commit()
    return {"ok": True}


@router.get("/{org_id}/usuarios")
def list_org_usuarios(org_id: int, db: Session = Depends(get_db), token=Depends(require_superadmin)):
    us = db.query(models.Usuario).filter_by(organizacion_id=org_id).all()
    return [{"id": u.id, "nombre": u.nombre, "username": u.username, "rol": u.rol,
             "activo": u.activo, "cliente_ref": u.cliente_ref, "ver_detalle": bool(u.ver_detalle)}
            for u in us]


@router.post("/{org_id}/usuarios", status_code=201)
def create_org_usuario(org_id: int, data: schemas.UsuarioCreate,
                       db: Session = Depends(get_db), token=Depends(require_superadmin)):
    org = db.query(models.Organizacion).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(404, "Organización no encontrada")
    if crud.get_user_by_username(db, data.username):
        raise HTTPException(400, f"El usuario '{data.username}' ya existe")
    u = models.Usuario(
        nombre=data.nombre, username=data.username.lower(),
        password=crud.hash_password(data.password), rol=data.rol,
        organizacion_id=org_id, cliente_ref=data.cliente_ref,
    )
    db.add(u); db.commit(); db.refresh(u)
    return {"id": u.id, "nombre": u.nombre, "username": u.username, "rol": u.rol}
