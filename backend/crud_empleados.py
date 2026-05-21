"""CRUD de empleados."""
import models, schemas
from crud_helpers import _log


def get_empleados(db):
    return [{"id":e.id,"nombre":e.nombre,"doc":e.doc,"cargo":e.cargo,
             "tel":e.tel,"email":e.email,"usuario":e.usuario,
             "nomina":e.nomina,"activo":e.activo,"fecha_ingreso":e.fecha_ingreso}
            for e in db.query(models.Empleado).all()]

def create_empleado(db, data: schemas.EmpleadoCreate):
    e = models.Empleado(**data.model_dump())
    db.add(e); db.commit(); db.refresh(e)
    return {"id":e.id,"nombre":e.nombre,"nomina":e.nomina}

def update_empleado(db, id, data: schemas.EmpleadoCreate):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if not e: return None
    for k,v in data.model_dump().items(): setattr(e,k,v)
    db.commit(); db.refresh(e)
    return {"id":e.id,"nombre":e.nombre,"nomina":e.nomina}

def delete_empleado(db, id, user=""):
    e = db.query(models.Empleado).filter_by(id=id).first()
    if e:
        _log(db, user, "eliminó un empleado", "Empleados", e.nombre)
        db.delete(e)
        db.commit()
