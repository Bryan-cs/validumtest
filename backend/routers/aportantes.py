"""Aportantes PILA — la empresa que paga los aportes.

Hasta ahora el aportante vivía como texto libre en `Afiliado.empresa` /
`Afiliado.cliente_txt`. El encabezado de una planilla (registro tipo 1 del
Anexo Técnico 2) necesita NIT con dígito de verificación, tipo y clase de
aportante, código de ARL y sucursal: de un string no sale nada de eso.

`cliente_ref` es el puente con lo que ya existe — coincide con el `cliente_txt`
de los afiliados, así que un aportante agrupa a los mismos trabajadores que ya
se ven en el módulo de Afiliados.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from routers.deps import require_admin, require_admin_or_empleado
import models, schemas
from crud_helpers import _log

router = APIRouter(prefix="/aportantes", tags=["aportantes"])

TIPOS_DOC = {"NI", "CC", "CE", "TI", "PA"}
TIPOS_PERSONA = {"J", "N"}
CLASES_RIESGO = {"1", "2", "3", "4", "5"}

# Pesos del algoritmo oficial de la DIAN, aplicados de derecha a izquierda.
_PESOS_DV = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]


def calcular_dv(nit: str) -> str:
    """Dígito de verificación de un NIT colombiano (algoritmo DIAN).

    Suma cada dígito por su peso posicional empezando por la derecha; el residuo
    módulo 11 es el DV cuando es 0 o 1, y 11 menos el residuo en cualquier otro caso.
    """
    digitos = [int(d) for d in str(nit) if d.isdigit()]
    suma = sum(d * _PESOS_DV[i] for i, d in enumerate(reversed(digitos)))
    residuo = suma % 11
    return str(residuo) if residuo in (0, 1) else str(11 - residuo)


def _codigo_valido(db: Session, tipo: str, codigo: str) -> bool:
    """¿El código existe y está vigente en el catálogo PILA?

    Si el catálogo de ese tipo está vacío (todavía no se sembró) no se bloquea
    nada: es preferible dejar guardar a impedir trabajar por un dato de
    referencia que falta.
    """
    if not codigo:
        return True
    hay_catalogo = db.query(models.PilaCodigo).filter_by(tipo=tipo).first() is not None
    if not hay_catalogo:
        return True
    return db.query(models.PilaCodigo).filter_by(tipo=tipo, codigo=codigo, vigente=True).first() is not None


def _to_dict(a: models.AportantePila) -> dict:
    from models import COL_TZ
    from datetime import timezone

    def _fmt(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(COL_TZ).strftime("%d/%m/%Y")

    return {
        "id":                     a.id,
        "cliente_ref":            a.cliente_ref,
        "razon_social":           a.razon_social,
        "tipo_doc":               a.tipo_doc,
        "num_doc":                a.num_doc,
        "dv":                     a.dv,
        "nit_completo":           f"{a.num_doc}-{a.dv}" if a.dv else a.num_doc,
        "tipo_persona":           a.tipo_persona,
        "tipo_aportante":         a.tipo_aportante,
        "clase_aportante":        a.clase_aportante,
        "cod_arl":                a.cod_arl,
        "clase_riesgo":           a.clase_riesgo,
        "actividad_economica":    a.actividad_economica,
        "cod_depto":              a.cod_depto,
        "cod_municipio":          a.cod_municipio,
        "cod_sucursal":           a.cod_sucursal,
        "nombre_sucursal":        a.nombre_sucursal,
        "exonerado_parafiscales": bool(a.exonerado_parafiscales),
        "direccion":              a.direccion,
        "telefono":               a.telefono,
        "email":                  a.email,
        "activo":                 bool(a.activo),
        "creado":                 _fmt(a.creado),
        "actualizado":            _fmt(a.actualizado),
    }


def _validar(db: Session, data, actual: Optional[models.AportantePila] = None):
    """Valida los campos que el archivo plano rechaza después, cuando ya es tarde."""
    tipo_doc = getattr(data, "tipo_doc", None) or (actual.tipo_doc if actual else "NI")
    if tipo_doc and tipo_doc not in TIPOS_DOC:
        raise HTTPException(400, f"tipo_doc debe ser: {', '.join(sorted(TIPOS_DOC))}")

    tipo_persona = getattr(data, "tipo_persona", None) or (actual.tipo_persona if actual else "J")
    if tipo_persona and tipo_persona not in TIPOS_PERSONA:
        raise HTTPException(400, "tipo_persona debe ser J (jurídica) o N (natural)")

    clase_riesgo = getattr(data, "clase_riesgo", None)
    if clase_riesgo and clase_riesgo not in CLASES_RIESGO:
        raise HTTPException(400, "clase_riesgo debe estar entre 1 y 5")

    for campo, largo in (("cod_depto", 2), ("cod_municipio", 3)):
        valor = getattr(data, campo, None)
        if valor and (not valor.isdigit() or len(valor) != largo):
            raise HTTPException(400, f"{campo} debe ser un código DANE de {largo} dígitos")

    # Contra el catálogo: un código de ARL o un tipo de aportante inventado pasa
    # la validación de formato y lo rechaza el operador días después.
    tipo_aportante = getattr(data, "tipo_aportante", None)
    if tipo_aportante and not _codigo_valido(db, "TIPO_APORTANTE", tipo_aportante):
        raise HTTPException(400, f"tipo_aportante '{tipo_aportante}' no existe en el catálogo PILA vigente")

    cod_arl = getattr(data, "cod_arl", None)
    if cod_arl and not _codigo_valido(db, "ARL", cod_arl):
        raise HTTPException(400, f"cod_arl '{cod_arl}' no existe en el catálogo de ARL vigente")

    # El municipio se valida junto con su departamento: el código DANE de
    # municipio solo es único dentro del departamento al que pertenece.
    cod_depto = getattr(data, "cod_depto", None) or (actual.cod_depto if actual else None)
    cod_mun = getattr(data, "cod_municipio", None)
    if cod_depto and cod_mun:
        completo = f"{cod_depto}{cod_mun}"
        if not _codigo_valido(db, "MUNICIPIO", completo):
            raise HTTPException(400, f"El municipio {cod_mun} no pertenece al departamento {cod_depto}")


def _resolver_dv(num_doc: str, dv: Optional[str], tipo_doc: str) -> Optional[str]:
    """Calcula el DV si no viene; si viene, exige que coincida.

    Solo aplica a NIT: una cédula no lleva dígito de verificación.
    """
    if tipo_doc != "NI":
        return None
    esperado = calcular_dv(num_doc)
    if dv in (None, ""):
        return esperado
    if str(dv).strip() != esperado:
        raise HTTPException(400, f"El dígito de verificación no corresponde al NIT {num_doc}: "
                                 f"debería ser {esperado}")
    return esperado


@router.get("/dv/{nit}")
def obtener_dv(nit: str, token=Depends(require_admin_or_empleado)):
    """Calcula el DV de un NIT — lo usa el formulario mientras se escribe."""
    limpio = "".join(d for d in nit if d.isdigit())
    if not limpio:
        raise HTTPException(400, "NIT inválido")
    return {"num_doc": limpio, "dv": calcular_dv(limpio)}


@router.get("")
def listar(q: str = "", activo: Optional[bool] = None,
           db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    query = db.query(models.AportantePila)
    if activo is not None:
        query = query.filter(models.AportantePila.activo == activo)
    if q:
        patron = f"%{q}%"
        query = query.filter(or_(models.AportantePila.razon_social.ilike(patron),
                                 models.AportantePila.cliente_ref.ilike(patron),
                                 models.AportantePila.num_doc.ilike(patron)))
    rows = query.order_by(models.AportantePila.razon_social).all()
    return [_to_dict(a) for a in rows]


@router.get("/{aportante_id}")
def obtener(aportante_id: int, db: Session = Depends(get_db),
            token=Depends(require_admin_or_empleado)):
    a = db.query(models.AportantePila).filter_by(id=aportante_id).first()
    if not a:
        raise HTTPException(404, "Aportante no encontrado")
    datos = _to_dict(a)
    # Cuántos afiliados quedarían cubiertos por este aportante al liquidar.
    datos["afiliados"] = (db.query(models.Afiliado)
                            .filter(models.Afiliado.cliente_txt == a.cliente_ref,
                                    models.Afiliado.activo == True)  # noqa: E712
                            .count())
    return datos


@router.post("", status_code=201)
def crear(data: schemas.AportanteCreate, db: Session = Depends(get_db),
          token=Depends(require_admin_or_empleado)):
    _validar(db, data)
    if db.query(models.AportantePila).filter_by(cliente_ref=data.cliente_ref).first():
        raise HTTPException(409, f"Ya existe un aportante para el cliente '{data.cliente_ref}'")

    a = models.AportantePila(
        cliente_ref=data.cliente_ref,
        razon_social=data.razon_social,
        tipo_doc=data.tipo_doc,
        num_doc=data.num_doc,
        dv=_resolver_dv(data.num_doc, data.dv, data.tipo_doc),
        tipo_persona=data.tipo_persona,
        tipo_aportante=data.tipo_aportante,
        clase_aportante=data.clase_aportante,
        cod_arl=data.cod_arl,
        clase_riesgo=data.clase_riesgo,
        actividad_economica=data.actividad_economica,
        cod_depto=data.cod_depto,
        cod_municipio=data.cod_municipio,
        cod_sucursal=data.cod_sucursal,
        nombre_sucursal=data.nombre_sucursal,
        exonerado_parafiscales=data.exonerado_parafiscales,
        direccion=data.direccion,
        telefono=data.telefono,
        email=data.email,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    _log(db, token.get("sub", ""), "registró aportante PILA", "Aportantes",
         f"{a.razon_social} ({a.num_doc})")
    db.commit()
    return _to_dict(a)


@router.put("/{aportante_id}")
def actualizar(aportante_id: int, data: schemas.AportanteUpdate,
               db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    a = db.query(models.AportantePila).filter_by(id=aportante_id).first()
    if not a:
        raise HTTPException(404, "Aportante no encontrado")
    _validar(db, data, a)

    if data.cliente_ref is not None and data.cliente_ref != a.cliente_ref:
        if db.query(models.AportantePila).filter_by(cliente_ref=data.cliente_ref).first():
            raise HTTPException(409, f"Ya existe un aportante para el cliente '{data.cliente_ref}'")
        a.cliente_ref = data.cliente_ref

    for campo in ("razon_social", "tipo_doc", "tipo_persona", "tipo_aportante",
                  "clase_aportante", "cod_arl", "clase_riesgo", "actividad_economica",
                  "cod_depto", "cod_municipio", "cod_sucursal", "nombre_sucursal",
                  "exonerado_parafiscales", "direccion", "telefono", "email", "activo"):
        valor = getattr(data, campo)
        if valor is not None:
            setattr(a, campo, valor)

    # El DV se recalcula si cambia el número o el tipo de documento.
    if data.num_doc is not None:
        a.num_doc = data.num_doc
    if data.num_doc is not None or data.dv is not None or data.tipo_doc is not None:
        a.dv = _resolver_dv(a.num_doc, data.dv, a.tipo_doc)

    db.commit()
    _log(db, token.get("sub", ""), "editó aportante PILA", "Aportantes",
         f"{a.razon_social} ({a.num_doc})")
    db.commit()
    return _to_dict(a)


@router.delete("/{aportante_id}")
def eliminar(aportante_id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    a = db.query(models.AportantePila).filter_by(id=aportante_id).first()
    if not a:
        raise HTTPException(404, "Aportante no encontrado")

    # Borrar un aportante con planillas destruiría el historial de lo que se pagó.
    # La FK es RESTRICT, pero el 409 explica el motivo en vez de reventar en la base.
    planillas = (db.query(models.PlanillaLiquidacion)
                   .filter_by(aportante_id=aportante_id).count())
    if planillas:
        raise HTTPException(409, f"El aportante tiene {planillas} planilla(s) liquidada(s). "
                                 f"Desactívalo en vez de borrarlo.")

    desc = f"{a.razon_social} ({a.num_doc})"
    db.delete(a)
    db.commit()
    _log(db, token.get("sub", ""), "eliminó aportante PILA", "Aportantes", desc)
    db.commit()
    return {"ok": True}
