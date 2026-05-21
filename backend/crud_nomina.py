"""Nómina mensual."""
import models
from crud_helpers import _log


def get_nomina_mensual(db, mes: int, anio: int):
    empleados = db.query(models.Empleado).filter_by(activo=True).order_by(models.Empleado.nombre).all()
    if not empleados:
        return []
    registros = {r.empleado_id: r.valor for r in
                 db.query(models.NominaMensual).filter_by(mes=mes, anio=anio).all()}
    if not registros:
        mes_ant = mes - 1 if mes > 1 else 12
        anio_ant = anio if mes > 1 else anio - 1
        registros_ant = {r.empleado_id: r.valor for r in
                         db.query(models.NominaMensual).filter_by(mes=mes_ant, anio=anio_ant).all()}
        try:
            for e in empleados:
                valor = registros_ant.get(e.id, e.nomina or 0.0)
                registros[e.id] = valor
                db.add(models.NominaMensual(empleado_id=e.id, mes=mes, anio=anio, valor=valor))
            db.commit()
        except Exception:
            db.rollback()
            registros = {r.empleado_id: r.valor for r in
                         db.query(models.NominaMensual).filter_by(mes=mes, anio=anio).all()}
    return [{"empleado_id": e.id, "nombre": e.nombre, "cargo": e.cargo,
             "valor": registros.get(e.id, e.nomina or 0.0)} for e in empleados]

def upsert_nomina_mensual(db, empleado_id: int, mes: int, anio: int, valor: float, user: str = ""):
    r = db.query(models.NominaMensual).filter_by(empleado_id=empleado_id, mes=mes, anio=anio).first()
    if r:
        r.valor = valor
    else:
        db.add(models.NominaMensual(empleado_id=empleado_id, mes=mes, anio=anio, valor=valor))
    db.commit()
    e = db.query(models.Empleado).filter_by(id=empleado_id).first()
    nombre = e.nombre if e else str(empleado_id)
    _log(db, user, "actualizó nómina mensual", "Nómina", f"{nombre} {mes}/{anio}")
    return {"empleado_id": empleado_id, "mes": mes, "anio": anio, "valor": valor}

def copiar_nomina_mes_anterior(db, origen_mes: int, origen_anio: int, dest_mes: int, dest_anio: int, user: str = ""):
    empleados = db.query(models.Empleado).filter_by(activo=True).all()
    registros_origen = {r.empleado_id: r.valor for r in
                        db.query(models.NominaMensual).filter_by(mes=origen_mes, anio=origen_anio).all()}
    db.query(models.NominaMensual).filter_by(mes=dest_mes, anio=dest_anio).delete()
    for e in empleados:
        valor = registros_origen.get(e.id, e.nomina)
        db.add(models.NominaMensual(empleado_id=e.id, mes=dest_mes, anio=dest_anio, valor=valor))
    db.commit()
    _log(db, user, "copió nómina", "Nómina", f"{origen_mes}/{origen_anio} → {dest_mes}/{dest_anio}")
    return get_nomina_mensual(db, dest_mes, dest_anio)
