"""Helpers compartidos — password, audit log, cálculos SS."""
import json, math
import bcrypt
from sqlalchemy.orm import Session
import models, schemas
from models import COL_TZ
from datetime import datetime
from const import MESES
from crud_cache import _cache_get, _cache_set


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    if not hashed or not hashed.startswith("$2"):
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _get_rol_usuario(db: Session, username: str) -> str:
    key = f"usuario_rol:{username}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    u = db.query(models.Usuario.rol).filter_by(username=username).first()
    rol = u.rol if u else "empleado"
    _cache_set(key, rol, ttl=600)
    return rol

def _log(db: Session, usuario: str, accion: str, modulo: str, detalle: str = ""):
    try:
        from logger import logger as _logger
        _logger.info(f"[AUDIT] {usuario} | {modulo} | {accion} | {detalle}")
    except Exception:
        pass
    if _get_rol_usuario(db, usuario) == "admin":
        return
    db.add(models.Actividad(usuario=usuario, accion=accion, modulo=modulo, detalle=detalle))

def _get_ibc(db: Session, afiliado: models.Afiliado = None) -> float:
    if afiliado and afiliado.ibc and afiliado.ibc > 0:
        return float(afiliado.ibc)
    cfg = db.query(models.Config).first()
    return float(cfg.ibc_global) if cfg else 1_750_905

def _get_pct(db: Session, servicio: str) -> float:
    cfg = db.query(models.Config).first()
    if not cfg: return 0.0
    pcts = json.loads(cfg.porcentajes or "{}")
    key = servicio.upper().strip()
    if "ARL" in key:
        for n in ["1","2","3","4","5"]:
            if n in key: return pcts.get(f"ARL {n}", 0.0)
    return pcts.get(key, 0.0)

def _ceil100(valor: float) -> int:
    return int(math.ceil(valor / 100)) * 100

def _servicios_afiliado(afiliado: models.Afiliado) -> list:
    raw = json.loads(afiliado.servicios or "[]")
    result = []
    for s in raw:
        su = s.strip().upper()
        if "EPS" in su and "EPS" not in result:
            result.append("EPS")
        elif ("CCF" in su or "CAJA" in su) and "CCF" not in result:
            result.append("CCF")
        elif ("AFP" in su or "PENSION" in su) and not any("AFP" in r for r in result):
            result.append("AFP")
        elif "ARL" in su:
            for n in ["1","2","3","4","5"]:
                if n in su and f"ARL {n}" not in result:
                    result.append(f"ARL {n}"); break
    arl = (afiliado.arl or "").strip()
    if arl and arl not in ("N/A","") and not any("ARL" in r for r in result):
        for n in ["1","2","3","4","5"]:
            if n in arl and f"ARL {n}" not in result:
                result.append(f"ARL {n}"); break
    return list(dict.fromkeys(result))

def _planilla(db: Session, afiliado: models.Afiliado, dias: int = 30) -> dict:
    ibc = _get_ibc(db, afiliado)
    servicios = _servicios_afiliado(afiliado)
    detalle = []
    total = 0
    for srv in servicios:
        pct = _get_pct(db, srv)
        val30 = _ceil100(ibc * pct)
        valor = _ceil100(val30 * dias / 30) if dias > 0 else 0
        total += valor
        detalle.append({"servicio": srv, "pct": pct, "valor": valor, "val30": val30})
    return {"detalle": detalle, "total": total, "ibc": ibc}

def _afiliado_to_dict(a: models.Afiliado) -> dict:
    return {
        "id": a.id, "nombre": a.nombre, "tipo_doc": a.tipo_doc, "doc": a.doc,
        "empresa": a.empresa, "cargo": a.cargo,
        "cliente_txt": a.cliente_txt, "eps": a.eps, "arl": a.arl,
        "ccf": a.ccf, "afp": a.afp, "subtipo": a.subtipo,
        "estado": a.estado, "estado_srv": a.estado_srv,
        "servicios": json.loads(a.servicios or "[]"),
        "tel": a.tel, "email": a.email, "dir": a.dir, "ciudad": a.ciudad or "", "novedades": a.novedades, "detalle": a.detalle or "",
        "ibc": float(a.ibc) if a.ibc is not None else None, "fecha_ingreso": a.fecha_ingreso,
        "fecha_afiliacion": a.fecha_afiliacion,
        "registrado_por": a.registrado_por, "activo": a.activo,
    }

def _factura_to_dict(f: models.Factura) -> dict:
    try:
        srv = json.loads(f.servicios_detalle or "[]")
        if not isinstance(srv, list): srv = []
    except (json.JSONDecodeError, TypeError):
        srv = []
    try:
        conc = json.loads(f.conceptos_detalle or "[]")
        if not isinstance(conc, list): conc = []
    except (json.JSONDecodeError, TypeError):
        conc = []
    return {
        "id": f.id, "codigo": f.codigo,
        "nombre_afiliado": f.nombre_afiliado, "doc": f.doc,
        "cliente": f.cliente, "anio": f.anio, "mes": f.mes,
        "periodo": f.periodo, "estado": f.estado, "banco": f.banco,
        "ingresos": float(f.ingresos or 0), "costos": float(f.costos or 0),
        "costo_adm": float(f.costo_adm or 0), "conceptos_extra": float(f.conceptos_extra or 0),
        "utilidad": float(f.utilidad or 0), "novedades": f.novedades,
        "servicios_detalle": srv,
        "conceptos_detalle": conc,
        "afiliado_eliminado": f.afiliado_eliminado,
        "pagado_en": f.pagado_en.isoformat() if f.pagado_en else None,
        "monto_pagado": float(f.monto_pagado or 0),
        "saldo_pendiente": max(0.0, float(f.ingresos or 0) - float(f.monto_pagado or 0)),
        "creado_por": f.creado_por,
        "creado": f.creado.isoformat() if f.creado else None,
    }
