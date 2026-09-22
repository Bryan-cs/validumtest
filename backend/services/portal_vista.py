"""Fila que ve el portal. El router solo decide quién puede entrar."""
import json


def fila_afiliado(afiliado, ver_detalle: bool) -> dict:
    try:
        servicios = json.loads(afiliado.servicios or "[]")
    except Exception:
        servicios = []
    return {
        "id": afiliado.id,
        "nombre": afiliado.nombre,
        "doc": afiliado.doc,
        "tipo_doc": afiliado.tipo_doc,
        "empresa": afiliado.empresa,
        "cargo": afiliado.cargo,
        "eps": afiliado.eps,
        "afp": afiliado.afp,
        "ccf": afiliado.ccf,
        "arl": afiliado.arl,
        "estado": afiliado.estado,
        "estado_srv": afiliado.estado_srv,
        "servicios": servicios,
        "tel": afiliado.tel,
        "email": afiliado.email,
        "fecha_ingreso": afiliado.fecha_ingreso,
        "fecha_afiliacion": afiliado.fecha_afiliacion,
        "novedades": afiliado.novedades or "",
        "detalle": (afiliado.detalle or "") if ver_detalle else "",
    }
