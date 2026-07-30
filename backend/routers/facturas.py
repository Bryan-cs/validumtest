"""Router de facturas."""
import io
import os
import json
from datetime import datetime
from models import COL_TZ
from fastapi import APIRouter, HTTPException, Depends
from const import MESES
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, crud
from .deps import verify_token, require_admin, require_admin_or_empleado
from logger import logger

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.get("")
def list_facturas(
    anio: str = "", mes: str = "", cliente: str = "",
    estado: str = "", banco: str = "", doc: str = "",
    skip: int = 0, limit: int = 0,
    exclude_planilla: bool = False,
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    """Lista facturas con paginación opcional.
    Sin limit devuelve todas. Con limit retorna {"total": N, "items": [...]}
    exclude_planilla=true oculta planilla_pagada (usado por defecto desde el frontend).
    """
    if mes and mes not in MESES:
        raise HTTPException(422, f"mes debe ser nombre en español (ej: Abril). Recibido: '{mes}'")
    # Un usuario con rol cliente solo puede ver SUS facturas. Sin esto veia las de
    # todos los clientes de la organizacion, montos incluidos. Mismo criterio que
    # el listado de afiliados.
    if token.get("rol") == "cliente":
        cliente_ref = (token.get("cliente_ref") or "").strip()
        if not cliente_ref:
            return {"total": 0, "items": []} if limit else []
        cliente = cliente_ref
    return crud.get_facturas(db, anio=anio, mes=mes, cliente=cliente,
                              estado=estado, banco=banco, doc=doc,
                              skip=skip, limit=limit,
                              exclude_planilla=exclude_planilla)


@router.post("", status_code=201)
def create_factura(data: schemas.FacturaCreate,
                   db: Session = Depends(get_db), token=Depends(require_admin)):
    data.creado_por = token.get("sub", "sistema")
    if not data.anio:
        data.anio = str(datetime.now(COL_TZ).year)
    return crud.create_factura(db, data)


@router.put("/{id}")
def update_factura(id: int, data: schemas.FacturaUpdate,
                   db: Session = Depends(get_db), token=Depends(require_admin)):
    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    return crud.update_factura(db, id, data, editor=token.get("sub", "sistema"))


@router.patch("/{id}/pagar")
def pagar_factura(id: int, banco: str = "", monto: float = None,
                  db: Session = Depends(get_db), token=Depends(require_admin)):
    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    return crud.pagar_factura(db, id, banco=banco, user=token.get("sub", "sistema"), monto=monto)


@router.get("/calc-planilla")
def calc_planilla(
    afiliado_id: int,
    dias: int = 30,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    """Calcula detalle de planilla SS para un afiliado (fuente única para el frontend)."""
    if dias < 0 or dias > 30:
        raise HTTPException(422, "dias debe estar entre 0 y 30")
    a = db.query(models.Afiliado).filter(models.Afiliado.id == afiliado_id).first()
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")
    result = crud._planilla(db, a, dias)
    return {"detalle": result["detalle"], "total": result["total"], "ibc": result["ibc"]}


@router.patch("/{id}/planilla-pagada")
def planilla_pagada(id: int, db: Session = Depends(get_db), token=Depends(require_admin)):
    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    result = crud.marcar_planilla_pagada(db, id, user=token.get("sub", "sistema"))
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/{id}")
def delete_factura(id: int, force: bool = False,
                   db: Session = Depends(get_db), token=Depends(require_admin)):
    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    if f.estado in ("pagado", "planilla_pagada") and not force:
        raise HTTPException(400,
            "No se puede eliminar una factura pagada. "
            "Use force=true si realmente desea eliminarla.")
    crud.delete_factura(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


@router.get("/{id}/pdf")
def descargar_factura_pdf(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Genera PDF de la factura sobre el membrete corporativo."""
    import pypdf as PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors

    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")

    fact = crud._factura_to_dict(f) if hasattr(f, 'codigo') else f

    # Datos del afiliado (entidades y fecha afiliación)
    doc_fact = (fact.get('doc') or '').strip()
    afil_obj = db.query(models.Afiliado).filter(models.Afiliado.doc == doc_fact).first()
    # Fallback: buscar en eliminados si no está en activos
    if not afil_obj and doc_fact:
        import json as _json
        elim = db.query(models.Eliminado).filter(models.Eliminado.doc == doc_fact).first()
        if elim and elim.datos_completos:
            try:
                _d = _json.loads(elim.datos_completos)
                class _Afil:
                    pass
                afil_obj = _Afil()
                afil_obj.eps = _d.get('eps', '')
                afil_obj.afp = _d.get('afp', '')
                afil_obj.arl = _d.get('arl', '')
                afil_obj.ccf = _d.get('ccf', '')
                afil_obj.fecha_afiliacion = _d.get('fecha_afiliacion', '')
            except Exception:
                afil_obj = None

    plantilla_path = os.path.join(os.path.dirname(__file__), '..', 'plantilla.pdf')
    if not os.path.exists(plantilla_path):
        raise HTTPException(500, "Plantilla no encontrada")

    content_buf = io.BytesIO()
    c = canvas.Canvas(content_buf, pagesize=letter)
    W, H = letter

    def money(v):
        try:
            return f"$ {int(v):,}".replace(",", ".")
        except (ValueError, TypeError):
            return "$ 0"

    def txt(x, y, text, size=10, bold=False, color=colors.black):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(color)
        c.drawString(x, y, str(text or ""))

    y = H - 190
    txt(50, y, "FACTURA DE SERVICIOS", size=13, bold=True, color=colors.HexColor("#1E40AF"))
    txt(400, y, f"N° {fact.get('codigo','')}", size=11, bold=True)

    y -= 18
    fecha_hoy = datetime.now(COL_TZ).strftime("%d/%m/%Y")
    txt(400, y, f"Fecha: {fecha_hoy}", size=9, color=colors.gray)

    y -= 10
    c.setStrokeColor(colors.HexColor("#1E40AF"))
    c.setLineWidth(1.2)
    c.line(50, y, W - 50, y)

    # ── DATOS DEL AFILIADO ────────────────────────────────────────────────────
    y -= 22
    txt(50, y, "DATOS DEL AFILIADO", size=9, bold=True, color=colors.HexColor("#1E40AF"))
    y -= 16
    txt(50,  y, f"Nombre:    {fact.get('nombre_afiliado','')}", size=9)
    txt(340, y, f"Documento: {fact.get('doc','')}", size=9)
    y -= 13
    txt(50,  y, f"Empresa:   {fact.get('cliente','')}", size=9)
    txt(340, y, f"Período:   {fact.get('mes','')} {fact.get('anio','')}", size=9)

    y -= 10
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.7)
    c.line(50, y, W - 50, y)

    # ── SERVICIOS (izquierda) + ENTIDADES (derecha) ───────────────────────────
    SRV_W  = 300   # ancho columna servicios
    ENT_X  = 370   # inicio columna entidades
    MID_X  = 360   # línea divisoria

    eps_val = (afil_obj.eps if afil_obj else '') or ''
    afp_val = (afil_obj.afp if afil_obj else '') or ''
    arl_val = (afil_obj.arl if afil_obj else '') or ''
    ccf_val = (afil_obj.ccf if afil_obj else '') or ''

    y -= 18
    # Encabezado "SERVICIOS CONTRATADOS"
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.rect(50, y - 4, SRV_W, 16, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(55, y, "SERVICIOS CONTRATADOS")

    # Encabezado "ENTIDADES"
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.rect(ENT_X, y - 4, W - ENT_X - 50, 16, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(ENT_X + 5, y, "ENTIDADES")

    srvs_detalle = json.loads(fact.get('servicios_detalle') or '[]') if isinstance(fact.get('servicios_detalle'), str) else (fact.get('servicios_detalle') or [])
    srvs_activos = [s for s in srvs_detalle if s.get('incluido', True) is not False]
    row_color = [colors.HexColor("#F8FAFC"), colors.white]

    # Filas de servicios — si servicios_detalle está vacío, usar servicios del afiliado
    servicios_nombres = [srv.get('servicio', srv.get('nombre', '')) for srv in srvs_activos]
    if not servicios_nombres and afil_obj and afil_obj.servicios:
        try:
            srvs_raw = json.loads(afil_obj.servicios) if isinstance(afil_obj.servicios, str) else (afil_obj.servicios or [])
            servicios_nombres = [s for s in srvs_raw if s]
        except Exception:
            pass
    if not servicios_nombres:
        servicios_nombres = ["Planilla seguridad social"]
    entidades_pares = [
        ("EPS", eps_val or "—"),
        ("AFP", afp_val or "—"),
        ("ARL", arl_val or "—"),
        ("CCF", ccf_val or "—"),
    ]
    n_filas = max(len(servicios_nombres), len(entidades_pares))

    for idx in range(n_filas):
        y -= 16
        # columna servicios
        c.setFillColor(row_color[idx % 2])
        c.rect(50, y - 4, SRV_W, 16, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        if idx < len(servicios_nombres):
            c.drawString(55, y, servicios_nombres[idx])
        # columna entidades
        c.setFillColor(row_color[idx % 2])
        c.rect(ENT_X, y - 4, W - ENT_X - 50, 16, fill=1, stroke=0)
        if idx < len(entidades_pares):
            etiq, valor = entidades_pares[idx]
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(ENT_X + 5, y, etiq + ":")
            c.setFont("Helvetica", 9)
            c.drawString(ENT_X + 35, y, valor)

    y -= 16
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.line(50, y + 8, W - 50, y + 8)

    ingresos = fact.get('ingresos', 0) or 0

    # Fila: Valor a pagar
    y -= 4
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.rect(340, y - 4, W - 390, 18, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(350, y, "VALOR A PAGAR:")
    c.drawRightString(W - 55, y, money(ingresos))

    # ── Fecha de vencimiento ──────────────────────────────────────────────────
    fecha_afil = afil_obj.fecha_afiliacion if afil_obj else ""
    mes_fact   = fact.get('mes', '')
    anio_fact  = fact.get('anio', '')
    fecha_venc = None
    if fecha_afil and mes_fact and anio_fact:
        try:
            dia = int(fecha_afil.split('-')[2])
            if   dia >= 26 or dia <= 4:  fecha_venc = f"05 de {mes_fact} de {anio_fact}"
            elif dia <= 9:               fecha_venc = f"10 de {mes_fact} de {anio_fact}"
            elif dia <= 14:              fecha_venc = f"15 de {mes_fact} de {anio_fact}"
            elif dia <= 19:              fecha_venc = f"20 de {mes_fact} de {anio_fact}"
            elif dia <= 25:              fecha_venc = f"25 de {mes_fact} de {anio_fact}"
        except Exception:
            pass

    # ── Días de mora ──────────────────────────────────────────────────────────
    dias_mora = 0
    if fecha_venc and fact.get('estado') == 'pendiente':
        try:
            meses_es = {'Enero':1,'Febrero':2,'Marzo':3,'Abril':4,'Mayo':5,'Junio':6,
                        'Julio':7,'Agosto':8,'Septiembre':9,'Octubre':10,'Noviembre':11,'Diciembre':12}
            partes_venc = fecha_venc.split(' de ')  # ['05', 'Marzo', '2026']
            d_venc = datetime(int(partes_venc[2]), meses_es[partes_venc[1]], int(partes_venc[0]))
            dias_mora = max(0, (datetime.now(COL_TZ).replace(tzinfo=None) - d_venc).days)
        except Exception:
            pass

    y -= 16
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.7)
    c.line(50, y, W - 50, y)

    # Fecha vencimiento y mora
    if fecha_venc:
        y -= 16
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, "Fecha de vencimiento:")
        c.setFont("Helvetica", 9)
        c.drawString(175, y, fecha_venc)
        if dias_mora > 0:
            c.setFillColor(colors.HexColor("#DC2626"))
            c.setFont("Helvetica-Bold", 9)
            c.drawString(350, y, f"⚠ {dias_mora} día{'s' if dias_mora != 1 else ''} de mora")
            c.setFillColor(colors.black)

    estado_fact = (fact.get('estado') or '').lower()

    if estado_fact == 'pendiente':
        # ── Formas de pago disponibles (solo facturas pendientes) ────────────
        bancos_lista = []
        try:
            lista_bancos = db.query(models.Lista).filter_by(nombre='bancos_cuentas').first()
            if not lista_bancos:
                lista_bancos = db.query(models.Lista).filter_by(nombre='bancos').first()
            if lista_bancos:
                bancos_lista = [b for b in json.loads(lista_bancos.items or "[]")
                                if b.strip()]
        except Exception as e:
            logger.error(f"PDF factura {id}: error cargando lista bancos: {e}")

        if bancos_lista:
            y -= 16
            c.setFillColor(colors.HexColor("#1E40AF"))
            c.setFont("Helvetica-Bold", 8)
            c.drawString(50, y, "FORMAS DE PAGO:")

            y -= 14
            c.setFillColor(colors.HexColor("#1E40AF"))
            c.rect(50, y - 3, W - 100, 14, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(55, y, "Entidad")
            c.drawString(175, y, "Cuenta")
            mid = W / 2 + 5
            c.drawString(mid, y, "Entidad")
            c.drawString(mid + 120, y, "Cuenta")

            ROW_H = 12
            for i in range(0, len(bancos_lista), 2):
                y -= ROW_H
                for col, idx in enumerate([i, i + 1]):
                    if idx >= len(bancos_lista):
                        break
                    banco = bancos_lista[idx]
                    xo = 55 if col == 0 else mid
                    xc = 175 if col == 0 else mid + 120
                    nombre_b, cuenta_b = (banco.split(' - ', 1) + [''])[:2] if ' - ' in banco else (banco, '')
                    c.setFillColor(colors.HexColor("#F8FAFC") if (i // 2) % 2 == 0 else colors.white)
                    col_w = (W - 100) / 2 - 5
                    c.rect(xo - 5, y - 3, col_w, ROW_H, fill=1, stroke=0)
                    c.setFillColor(colors.black)
                    c.setFont("Helvetica", 7)
                    c.drawString(xo, y, nombre_b[:28])
                    c.setFont("Helvetica-Bold", 7)
                    c.drawString(xc, y, cuenta_b[:22])

    elif fact.get('banco'):
        # ── Banco con que se pagó (solo facturas pagadas) ────────────────────
        y -= 14
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor("#1E40AF"))
        c.drawString(50, y, "PAGO REGISTRADO EN:")
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)
        c.drawString(195, y, fact.get('banco', ''))

    c.save()

    content_buf.seek(0)
    content_pdf = PyPDF2.PdfReader(content_buf)

    with open(plantilla_path, 'rb') as plantilla_file:
        plantilla_pdf = PyPDF2.PdfReader(plantilla_file)

        writer = PyPDF2.PdfWriter()
        base_page = plantilla_pdf.pages[0]
        base_page.merge_page(content_pdf.pages[0])
        writer.add_page(base_page)
        if len(plantilla_pdf.pages) > 1:
            writer.add_page(plantilla_pdf.pages[1])

        out_buf = io.BytesIO()
        writer.write(out_buf)
        out_buf.seek(0)

    codigo = fact.get('codigo', str(id))
    return StreamingResponse(
        out_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="factura_{codigo}.pdf"'},
    )
