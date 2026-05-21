"""CRUD de gastos e ingresos adicionales."""
import models, schemas
from crud_cache import cache_invalidar
from crud_helpers import _log


def get_ingresos_adicionales(db, mes: int = None, anio: int = None):
    q = db.query(models.IngresoAdicional)
    if mes:  q = q.filter_by(mes=mes)
    if anio: q = q.filter_by(anio=anio)
    return [{"id": i.id, "concepto": i.concepto, "descripcion": i.descripcion,
             "valor": i.valor, "mes": i.mes, "anio": i.anio, "creado_por": i.creado_por,
             "creado": i.creado.isoformat() if i.creado else None}
            for i in q.order_by(models.IngresoAdicional.creado.desc()).all()]

def create_ingreso_adicional(db, data, user=""):
    cache_invalidar("dashboard:")
    i = models.IngresoAdicional(concepto=data.concepto, descripcion=data.descripcion,
                                 valor=data.valor, mes=data.mes, anio=data.anio, creado_por=user)
    db.add(i); db.commit(); db.refresh(i)
    _log(db, user, "agregó ingreso adicional", "Facturación", f"{data.concepto} ${data.valor:,.0f}")
    return {"id": i.id, "concepto": i.concepto, "descripcion": i.descripcion,
            "valor": i.valor, "mes": i.mes, "anio": i.anio, "creado_por": i.creado_por,
            "creado": i.creado.isoformat() if i.creado else None}

def update_ingreso_adicional(db, id, data, user=""):
    i = db.query(models.IngresoAdicional).filter_by(id=id).first()
    if not i: return None
    i.concepto = data.concepto; i.descripcion = data.descripcion
    i.valor = data.valor; i.mes = data.mes; i.anio = data.anio
    db.commit(); db.refresh(i)
    cache_invalidar("dashboard:")
    _log(db, user, "editó ingreso adicional", "Facturación", f"{i.concepto} ${i.valor:,.0f}")
    return {"id": i.id, "concepto": i.concepto, "descripcion": i.descripcion,
            "valor": i.valor, "mes": i.mes, "anio": i.anio, "creado_por": i.creado_por,
            "creado": i.creado.isoformat() if i.creado else None}

def delete_ingreso_adicional(db, id, user=""):
    cache_invalidar("dashboard:")
    i = db.query(models.IngresoAdicional).filter_by(id=id).first()
    if not i: return False
    _log(db, user, "eliminó ingreso adicional", "Facturación", f"{i.concepto} ${i.valor:,.0f}")
    db.delete(i); db.commit(); return True


def get_gastos(db, mes: int, anio: int):
    return [{"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio,
             "creado": g.creado.isoformat() if g.creado else None}
            for g in db.query(models.Gasto).filter_by(mes=mes, anio=anio).order_by(models.Gasto.nombre).all()]

def create_gasto(db, data: schemas.GastoCreate):
    g = models.Gasto(nombre=data.nombre, valor=data.valor, mes=data.mes, anio=data.anio)
    db.add(g); db.commit(); db.refresh(g)
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio,
            "creado": g.creado.isoformat() if g.creado else None}

def update_gasto(db, id: int, data: schemas.GastoUpdate):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if not g: return None
    if data.nombre is not None: g.nombre = data.nombre
    if data.valor is not None: g.valor = data.valor
    if data.mes is not None: g.mes = data.mes
    if data.anio is not None: g.anio = data.anio
    db.commit(); db.refresh(g)
    return {"id":g.id,"nombre":g.nombre,"valor":g.valor,"mes":g.mes,"anio":g.anio}

def delete_gasto(db, id, user=""):
    g = db.query(models.Gasto).filter_by(id=id).first()
    if g:
        _log(db, user, "eliminó un gasto", "Gastos", g.nombre)
        db.delete(g)
        db.commit()

def copiar_gastos_mes_anterior(db, origen_mes: int, origen_anio: int, dest_mes: int, dest_anio: int, user: str = ""):
    db.query(models.Gasto).filter_by(mes=dest_mes, anio=dest_anio).delete()
    origen = db.query(models.Gasto).filter_by(mes=origen_mes, anio=origen_anio).all()
    for g in origen:
        db.add(models.Gasto(nombre=g.nombre, valor=g.valor, mes=dest_mes, anio=dest_anio))
    db.commit()
    _log(db, user, "copió gastos", "Gastos", f"{origen_mes}/{origen_anio} → {dest_mes}/{dest_anio}")
    return get_gastos(db, dest_mes, dest_anio)
