"""Arma el archivo plano a partir de líneas ya liquidadas.

El router solo recibe la petición. El encabezado se reconstruye al enviar
porque la sucursal puede haber cambiado; el tipo 2 sale de `linea_plana`.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from services.pila import perfiles, plano

TIPOS_DOC_COTIZANTE = {"CC", "CE", "TI", "PA", "CD", "SC", "PE", "PT", "PC"}


def documento_del_afiliado(db: Session, liquidacion) -> str:
    """Con qué documento sale esta persona, si su subtipo pide uno distinto."""
    if not liquidacion.afiliado_id:
        return ""
    af = db.query(models.Afiliado).filter_by(id=liquidacion.afiliado_id).first()
    return perfiles.documento_sugerido(af.subtipo, af.tipo_doc) if af else ""


def cambiar_documento(linea: str, tipo_doc: str) -> str:
    """El campo 3 son las posiciones 8 y 9. Se cambian esas dos y nada más."""
    return linea[:7] + tipo_doc.ljust(2)[:2] + linea[9:]


def renumerar(linea: str, secuencia: int) -> str:
    """El campo 2 es la secuencia del cotizante dentro del archivo."""
    return linea[:2] + f"{secuencia:05d}" + linea[7:]


def documentos_pedidos(docs: str) -> dict:
    """Interpreta "12:CE,13:CC" como {12: "CE", 13: "CC"}."""
    elegidos = {}
    for parte in str(docs or "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        if ":" not in parte:
            raise HTTPException(400, f"'{parte}' no tiene la forma id:DOCUMENTO")
        crudo_id, crudo_doc = parte.split(":", 1)
        try:
            elegidos[int(crudo_id)] = crudo_doc.strip().upper()
        except ValueError:
            raise HTTPException(400, f"'{crudo_id}' no es un id de liquidación")
    return elegidos


def armar_plano(db: Session, liquidaciones, tipo_doc: str = "",
                docs: dict = None) -> tuple:
    """El archivo plano de una o varias liquidaciones, y su nombre sugerido."""
    if not isinstance(liquidaciones, (list, tuple)):
        liquidaciones = [liquidaciones]
    if not liquidaciones:
        raise HTTPException(400, "No hay liquidaciones para armar el archivo")

    if len({l.aportante_id for l in liquidaciones}) > 1:
        raise HTTPException(409, "Un archivo plano lleva un solo aportante en el "
                                 "encabezado: no se pueden juntar personas de "
                                 "empresas distintas")
    periodos = {l.periodo_cotizacion for l in liquidaciones}
    if len(periodos) > 1:
        raise HTTPException(409, "Un archivo plano lleva un solo período: "
                                 f"llegaron {', '.join(sorted(periodos))}")
    if len({l.tipo_planilla for l in liquidaciones}) > 1:
        raise HTTPException(409, "Todas las planillas del archivo tienen que ser "
                                 "del mismo tipo")

    primera = liquidaciones[0]
    ap = db.query(models.AportantePila).filter_by(id=primera.aportante_id).first()

    lineas, detalles_todos = [], []
    for l in liquidaciones:
        detalles = (db.query(models.PlanillaDetalle)
                      .filter_by(liquidacion_id=l.id)
                      .order_by(models.PlanillaDetalle.secuencia).all())
        detalles_todos.extend(detalles)

        doc = ((docs or {}).get(l.id) or tipo_doc
               or documento_del_afiliado(db, l)).strip().upper()
        if doc and doc not in TIPOS_DOC_COTIZANTE:
            raise HTTPException(400, f"tipo_doc debe ser uno de: "
                                     f"{', '.join(sorted(TIPOS_DOC_COTIZANTE))}")
        for d in detalles:
            if not d.linea_plana:
                continue
            linea = renumerar(d.linea_plana, len(lineas) + 1)
            lineas.append(cambiar_documento(linea, doc) if doc else linea)

    forma, cod_sucursal, nombre_sucursal = plano.datos_sucursal(ap)
    periodo_otros, periodo_salud = plano.periodos_del_encabezado(primera.periodo_cotizacion)

    encabezado = plano.registro_tipo_1({
        "modalidad_planilla": 1, "secuencia": 1,
        "razon_social": ap.razon_social,
        "tipo_doc_aportante": ap.tipo_doc or "NI", "num_doc_aportante": ap.num_doc,
        "dv_aportante": ap.dv or 0, "tipo_planilla": primera.tipo_planilla,
        "planilla_asociada": 0, "fecha_planilla_asociada": "",
        "forma_presentacion": forma,
        "cod_sucursal": cod_sucursal, "nombre_sucursal": nombre_sucursal,
        "cod_arl": ap.cod_arl or "",
        "periodo_pago_otros": periodo_otros, "periodo_pago_salud": periodo_salud,
        "numero_planilla": (primera.numero_planilla or 0) if len(liquidaciones) == 1 else 0,
        "fecha_pago": primera.fecha_limite_pago or "",
        "total_cotizantes": len(lineas),
        "valor_total_nomina": plano.suma_ibc_parafiscales(detalles_todos),
        "tipo_aportante": ap.tipo_aportante or 1, "cod_operador": 0,
    })

    if len(liquidaciones) == 1:
        pedido = (docs or {}).get(primera.id) or tipo_doc
        sufijo = f"_{pedido.strip().upper()}" if pedido else ""
        nombre = (f"PILA_{primera.afiliado_doc or ap.num_doc}_"
                  f"{primera.periodo_cotizacion}_{primera.tipo_planilla}{sufijo}.txt")
    else:
        nombre = (f"PILA_{ap.num_doc}_{primera.periodo_cotizacion}_"
                  f"{primera.tipo_planilla}_{len(lineas)}cotizantes.txt")

    salto = chr(13) + chr(10)
    return salto.join([encabezado] + lineas) + salto, nombre, ap
