"""Config global y listas."""
import json
import models, schemas
from crud_cache import _cache_get, _cache_set, cache_invalidar, TTL_CONFIG, TTL_LISTAS
from crud_helpers import _log


def get_config(db):
    cached = _cache_get("config:global")
    if cached is not None:
        return cached
    c = db.query(models.Config).first()
    if not c: return {"ibc_global":1_750_905,"porcentajes":{},"plantilla_whatsapp":"","cargo_adicional":2200,"mes_inicio_cobro":None,"anio_inicio_cobro":None}
    result = {
        "ibc_global": float(c.ibc_global) if c.ibc_global is not None else 1_750_905,
        "porcentajes": json.loads(c.porcentajes or "{}"),
        "plantilla_whatsapp": c.plantilla_whatsapp or "",
        "cargo_adicional": float(c.cargo_adicional) if c.cargo_adicional is not None else 2200,
        "mes_inicio_cobro": c.mes_inicio_cobro,
        "anio_inicio_cobro": c.anio_inicio_cobro,
    }
    _cache_set("config:global", result, ttl=TTL_CONFIG)
    return result

def update_config(db, data: schemas.ConfigUpdate, user="sistema"):
    c = db.query(models.Config).first()
    if not c:
        c = models.Config()
        db.add(c)
    if data.ibc_global is not None: c.ibc_global = data.ibc_global
    if data.porcentajes is not None: c.porcentajes = json.dumps(data.porcentajes)
    if data.plantilla_whatsapp is not None: c.plantilla_whatsapp = data.plantilla_whatsapp
    if data.cargo_adicional is not None: c.cargo_adicional = data.cargo_adicional
    if data.mes_inicio_cobro is not None: c.mes_inicio_cobro = data.mes_inicio_cobro
    if data.anio_inicio_cobro is not None: c.anio_inicio_cobro = data.anio_inicio_cobro
    _log(db, user, "actualizó configuración global", "Config", "")
    cache_invalidar("config:")
    db.commit(); return get_config(db)


def get_listas(db):
    cached = _cache_get("listas:all")
    if cached is not None:
        return cached
    result = {l.nombre: json.loads(l.items or "[]") for l in db.query(models.Lista).all()}
    _cache_set("listas:all", result, ttl=TTL_LISTAS)
    return result

def update_lista(db, nombre, items, user="sistema"):
    l = db.query(models.Lista).filter_by(nombre=nombre).first()
    if not l: l = models.Lista(nombre=nombre); db.add(l)
    l.items = json.dumps(items)
    _log(db, user, "actualizó lista", "Listas", nombre)
    cache_invalidar("listas:")
    db.commit()
    return {"nombre":nombre,"items":items}
