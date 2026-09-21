"""CRUD de afiliados."""
import json
from datetime import datetime
from sqlalchemy import or_
import models, schemas
from models import COL_TZ
from const import MESES
from crud_cache import _cache_get, _cache_set, cache_invalidar, TTL_AFILIADOS
from crud_helpers import _afiliado_to_dict, _log


def _split_csv(val: str) -> list:
    return [v.strip() for v in val.split(",") if v.strip()] if val else []


def get_afiliados_filter_options(db):
    cached = _cache_get("afiliados:filtros")
    if cached is not None:
        return cached
    A = models.Afiliado
    rows = db.query(
        A.empresa, A.cliente_txt, A.subtipo, A.estado_srv, A.tipo_doc, A.ccf, A.eps
    ).filter_by(activo=True).distinct().all()
    result = {
        "empresas":  sorted({r.empresa     for r in rows if r.empresa}),
        "clientes":  sorted({r.cliente_txt for r in rows if r.cliente_txt}),
        "subtipos":  sorted({r.subtipo     for r in rows if r.subtipo}),
        "estados":   sorted({r.estado_srv  for r in rows if r.estado_srv}),
        "tipos_doc": sorted({r.tipo_doc    for r in rows if r.tipo_doc}),
        "ccfs":      sorted({r.ccf         for r in rows if r.ccf}),
        "eps":       sorted({r.eps         for r in rows if r.eps}),
    }
    _cache_set("afiliados:filtros", result, ttl=120)
    return result


def get_afiliados(db, q="", estado="", empresa="", cliente="", subtipo="",
                  tipo_doc="", ccf="", eps="", fecha_desde="", fecha_hasta="",
                  skip: int = 0, limit: int = 0):
    sin_filtros = not any([q, estado, empresa, cliente, subtipo, tipo_doc, ccf, eps, fecha_desde, fecha_hasta])
    if sin_filtros and skip == 0 and limit == 0:
        cached = _cache_get("afiliados:all")
        if cached is not None:
            return cached

    query = db.query(models.Afiliado).filter_by(activo=True)
    if q:
        query = query.filter(or_(
            models.Afiliado.nombre.ilike(f"%{q}%"),
            models.Afiliado.doc.ilike(f"%{q}%"),
            models.Afiliado.empresa.ilike(f"%{q}%"),
            models.Afiliado.cliente_txt.ilike(f"%{q}%"),
        ))
    estados = _split_csv(estado)
    if estados:
        query = query.filter(or_(
            models.Afiliado.estado_srv.in_(estados),
            models.Afiliado.estado.in_(estados),
        ))
    empresas = _split_csv(empresa)
    if empresas: query = query.filter(models.Afiliado.empresa.in_(empresas))
    clientes = _split_csv(cliente)
    if clientes: query = query.filter(models.Afiliado.cliente_txt.in_(clientes))
    subtipos = _split_csv(subtipo)
    if subtipos: query = query.filter(models.Afiliado.subtipo.in_(subtipos))
    tipos_doc = _split_csv(tipo_doc)
    if tipos_doc: query = query.filter(models.Afiliado.tipo_doc.in_(tipos_doc))
    ccfs = _split_csv(ccf)
    if ccfs: query = query.filter(models.Afiliado.ccf.in_(ccfs))
    epss = _split_csv(eps)
    if epss: query = query.filter(models.Afiliado.eps.in_(epss))
    if fecha_desde: query = query.filter(models.Afiliado.fecha_afiliacion >= fecha_desde)
    if fecha_hasta: query = query.filter(models.Afiliado.fecha_afiliacion <= fecha_hasta)
    total = query.count()
    query = query.order_by(models.Afiliado.nombre)
    if limit > 0:
        query = query.offset(skip).limit(limit)
    else:
        query = query.limit(50_000)
    result = {"total": total, "items": [_afiliado_to_dict(a) for a in query.all()]}
    if sin_filtros and skip == 0 and limit == 0:
        _cache_set("afiliados:all", result, ttl=TTL_AFILIADOS)
    return result

def get_afiliado(db, id):
    a = db.query(models.Afiliado).filter_by(id=id, activo=True).first()
    return _afiliado_to_dict(a) if a else None

def get_afiliado_by_doc(db, doc):
    return db.query(models.Afiliado).filter_by(doc=doc, activo=True).first()

# Los campos del registro tipo 2 que el afiliado guarda. Van en una sola lista
# porque create y update los recorren los dos: mantenerlos duplicados a mano es
# como se pierden columnas sin que ningun test lo note.
CAMPOS_PILA = (
    "primer_apellido", "segundo_apellido", "primer_nombre", "segundo_nombre",
    "fecha_nacimiento", "sexo", "tipo_cotizante", "subtipo_cotizante",
    "extranjero_no_pension", "colombiano_exterior",
    "cod_depto_labor", "cod_municipio_labor",
    "cod_eps", "cod_afp", "cod_ccf", "cod_arl", "clase_riesgo", "tarifa_arl",
    "actividad_economica",
    "tipo_salario", "salario_basico", "centro_trabajo",
    "cotizante_principal_tipo_doc", "cotizante_principal_doc", "horas_laboradas",
)


def _deducir_codigos_pila(afiliado):
    """Completa el código PILA de cada administradora desde su nombre.

    El formulario guarda el nombre —"Compensar"— y el archivo plano necesita
    el código —"EPS008"—. Son campos distintos y el formulario solo llena el
    primero, asi que quien lo llenaba bien se encontraba con que el campo del
    archivo salía vacío y el operador rechazaba la planilla.

    Solo rellena lo que está vacío: un código puesto a mano manda, porque
    alguien pudo tener una razón para elegir otro.
    """
    from services.pila.catalogos import buscar_codigo
    for tipo, nombre, codigo in (("EPS", "eps", "cod_eps"),
                                 ("AFP", "afp", "cod_afp"),
                                 ("CCF", "ccf", "cod_ccf")):
        if (getattr(afiliado, codigo, "") or "").strip():
            continue
        hallado = buscar_codigo(tipo, getattr(afiliado, nombre, "") or "")
        if hallado:
            setattr(afiliado, codigo, hallado)


def _aplicar_pila(afiliado, data):
    """Escribe solo los campos PILA que el cliente haya mandado.

    El formulario de afiliados no los envia todos, y escribirlos igual dejaria
    en blanco los codigos de quien ya los tiene cargados: un guardado inocente
    romperia su liquidacion.
    """
    enviados = data.model_dump(exclude_unset=True)
    for campo in CAMPOS_PILA:
        if campo in enviados:
            setattr(afiliado, campo, enviados[campo])


def create_afiliado(db, data: schemas.AfiliadoCreate):
    from sqlalchemy.exc import IntegrityError
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:"); cache_invalidar("afiliados:")
    a = models.Afiliado(**{
        "nombre":data.nombre,"tipo_doc":data.tipo_doc,"doc":data.doc,"empresa":data.empresa,
        "cargo":data.cargo,"cliente_txt":data.cliente_txt,
        "eps":data.eps,"arl":data.arl,"ccf":data.ccf,"afp":data.afp,
        "subtipo":data.subtipo,"estado":data.estado,"estado_srv":data.estado_srv,
        "servicios":json.dumps(data.servicios),"tel":data.tel,
        "email":data.email,"dir":data.dir,"ciudad":data.ciudad,"novedades":data.novedades,"detalle":data.detalle,
        "ibc":data.ibc,"fecha_ingreso":data.fecha_ingreso,
        "fecha_afiliacion":data.fecha_afiliacion,"registrado_por":data.registrado_por,
    })
    _aplicar_pila(a, data)
    _deducir_codigos_pila(a)
    db.add(a); _log(db, data.registrado_por, "agregó un afiliado nuevo", "Afiliados", data.nombre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(400, f"Ya existe un afiliado con documento {data.doc}")
    db.refresh(a); return _afiliado_to_dict(a)

def update_afiliado(db, id, data: schemas.AfiliadoCreate, editor=""):
    from sqlalchemy.exc import IntegrityError
    from fastapi import HTTPException
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:"); cache_invalidar("afiliados:")
    a = db.query(models.Afiliado).filter_by(id=id, activo=True).with_for_update().first()
    if not a:
        raise HTTPException(404, "Afiliado no encontrado o fue eliminado por otro usuario")
    if data.estado_srv == "ACTIVO" and a.estado_srv != "ACTIVO":
        db.query(models.SolicitudRetiro).filter_by(afiliado_doc=a.doc).delete()
    nombre_anterior  = a.nombre
    cliente_anterior = a.cliente_txt

    # Solo se escribe lo que el cliente haya mandado de verdad. El formulario
    # los manda todos, asi que vaciar un campo desde la pantalla sigue
    # funcionando: mandar "" es mandarlo. Lo que ya no pasa es que un cliente
    # que envie medio recurso deje en blanco el resto, que es como se borraron
    # la EPS, el cargo y el IBC de trece personas de una sentada.
    enviados = data.model_dump(exclude_unset=True)
    for field, val in [
        ("nombre",data.nombre),("tipo_doc",data.tipo_doc),("doc",data.doc),("empresa",data.empresa),
        ("cargo",data.cargo),("cliente_txt",data.cliente_txt),
        ("eps",data.eps),("arl",data.arl),("ccf",data.ccf),("afp",data.afp),
        ("subtipo",data.subtipo),("estado",data.estado),("estado_srv",data.estado_srv),
        ("servicios",json.dumps(data.servicios)),("tel",data.tel),
        ("email",data.email),("dir",data.dir),("ciudad",data.ciudad),("novedades",data.novedades),("detalle",data.detalle),
        ("ibc",data.ibc),("fecha_ingreso",data.fecha_ingreso),
        ("fecha_afiliacion",data.fecha_afiliacion),
    ]:
        if field in enviados:
            setattr(a, field, val)
    _aplicar_pila(a, data)
    _deducir_codigos_pila(a)
    nombre_cambio  = data.nombre      != nombre_anterior
    cliente_cambio = data.cliente_txt != cliente_anterior
    if nombre_cambio or cliente_cambio:
        q_fact = db.query(models.Factura).filter(
            models.Factura.doc == a.doc,
            models.Factura.estado != "pagado",
        )
        upd = {}
        if nombre_cambio:  upd["nombre_afiliado"] = data.nombre
        if cliente_cambio: upd["cliente"]         = data.cliente_txt or ""
        if upd:
            q_fact.update(upd, synchronize_session=False)
    _log(db, editor, "editó un afiliado", "Afiliados", data.nombre)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, f"Ya existe otro afiliado con documento {data.doc}")
    db.refresh(a); return _afiliado_to_dict(a)

def delete_afiliado(db, id, deleted_by=""):
    cache_invalidar("cobro:"); cache_invalidar("dashboard:"); cache_invalidar("dashboard_clientes:"); cache_invalidar("afiliados:")
    a = db.query(models.Afiliado).filter_by(id=id).first()
    if not a: return
    try:
        nombre = a.nombre
        elim = models.Eliminado(
            nombre=a.nombre, doc=a.doc, empresa=a.empresa,
            datos_completos=json.dumps(_afiliado_to_dict(a)),
            fecha_eliminacion=datetime.now(COL_TZ).strftime("%Y-%m-%d"),
            mes=MESES[datetime.now(COL_TZ).month-1], eliminado_por=deleted_by,
        )
        db.add(elim)
        db.query(models.Factura).filter_by(doc=a.doc).update(
            {"afiliado_eliminado": True})
        a.activo = False
        _log(db, deleted_by, "eliminó un afiliado", "Afiliados", nombre)
        db.commit()
    except Exception:
        db.rollback()
        raise
