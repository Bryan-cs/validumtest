"""Router de facturas."""
import io
import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, crud
from .deps import verify_token, require_admin

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.get("")
def list_facturas(
    anio: str = "", mes: str = "", cliente: str = "",
    estado: str = "", banco: str = "",
    skip: int = 0, limit: int = 0,
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    """Lista facturas con paginación opcional.
    Sin limit devuelve todas. Con limit retorna {"total": N, "items": [...]}
    """
    return crud.get_facturas(db, anio=anio, mes=mes, cliente=cliente,
                              estado=estado, banco=banco,
                              skip=skip, limit=limit)


@router.post("", status_code=201)
def create_factura(data: schemas.FacturaCreate,
                   db: Session = Depends(get_db), token=Depends(verify_token)):
    data.creado_por = token.get("sub", "sistema")
    if not data.anio:
        data.anio = str(datetime.now().year)
    return crud.create_factura(db, data)


@router.put("/{id}")
def update_factura(id: int, data: schemas.FacturaUpdate,
                   db: Session = Depends(get_db), token=Depends(verify_token)):
    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    return crud.update_factura(db, id, data, editor=token.get("sub", "sistema"))


@router.patch("/{id}/pagar")
def pagar_factura(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")
    return crud.pagar_factura(db, id, user=token.get("sub", "sistema"))


@router.delete("/{id}")
def delete_factura(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    if not crud.get_factura(db, id):
        raise HTTPException(404, "Factura no encontrada")
    crud.delete_factura(db, id, user=token.get("sub", "sistema"))
    return {"ok": True}


@router.get("/{id}/pdf")
def descargar_factura_pdf(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Genera PDF de la factura sobre el membrete corporativo."""
    import PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors

    f = crud.get_factura(db, id)
    if not f:
        raise HTTPException(404, "Factura no encontrada")

    fact = crud._factura_to_dict(f) if hasattr(f, 'codigo') else f

    plantilla_path = os.path.join(os.path.dirname(__file__), '..', '..', 'plantilla.pdf')
    if not os.path.exists(plantilla_path):
        raise HTTPException(500, "Plantilla no encontrada")

    content_buf = io.BytesIO()
    c = canvas.Canvas(content_buf, pagesize=letter)
    W, H = letter

    def money(v):
        try:
            return f"$ {int(v):,}".replace(",", ".")
        except:
            return "$ 0"

    def txt(x, y, text, size=10, bold=False, color=colors.black):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(color)
        c.drawString(x, y, str(text or ""))

    y = H - 190
    txt(50, y, "FACTURA DE SERVICIOS", size=13, bold=True, color=colors.HexColor("#1E40AF"))
    txt(400, y, f"N° {fact.get('codigo','')}", size=11, bold=True)

    y -= 18
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    txt(400, y, f"Fecha: {fecha_hoy}", size=9, color=colors.gray)

    y -= 10
    c.setStrokeColor(colors.HexColor("#1E40AF"))
    c.setLineWidth(1.2)
    c.line(50, y, W - 50, y)

    y -= 22
    txt(50, y, "DATOS DEL AFILIADO", size=9, bold=True, color=colors.HexColor("#1E40AF"))
    y -= 16
    txt(50,  y, f"Nombre:  {fact.get('nombre_afiliado','')}", size=10)
    txt(340, y, f"Documento: {fact.get('doc','')}", size=10)
    y -= 14
    txt(50,  y, f"Empresa:  {fact.get('cliente','')}", size=10)
    txt(340, y, f"Período: {fact.get('mes','')} {fact.get('anio','')}", size=10)

    y -= 14
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(0.7)
    c.line(50, y, W - 50, y)

    y -= 20
    txt(50, y, "SERVICIOS CONTRATADOS", size=9, bold=True, color=colors.HexColor("#1E40AF"))
    y -= 6

    srvs_detalle = json.loads(fact.get('servicios_detalle') or '[]') if isinstance(fact.get('servicios_detalle'), str) else (fact.get('servicios_detalle') or [])
    srvs_activos = [s for s in srvs_detalle if s.get('incluido', True) is not False]
    row_color = [colors.HexColor("#F8FAFC"), colors.white]

    # Encabezado tabla solo con nombre de servicio
    y -= 16
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(55, y, "Servicio")

    if srvs_activos:
        for idx, srv in enumerate(srvs_activos):
            y -= 16
            c.setFillColor(row_color[idx % 2])
            c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 9)
            c.drawString(55, y, srv.get('servicio', srv.get('nombre', '')))
    else:
        y -= 16
        c.setFillColor(row_color[0])
        c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        c.drawString(55, y, "Planilla seguridad social")

    y -= 24
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
    afil_obj = db.query(models.Afiliado).filter_by(doc=fact.get('doc')).first()
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
            dias_mora = max(0, (datetime.now() - d_venc).days)
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

    # Novedades
    if fact.get('novedades'):
        y -= 16
        c.setFillColor(colors.HexColor("#FFFBEB"))
        c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#92400E"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(55, y, f"Novedades: {fact.get('novedades','')}")
        c.setFillColor(colors.black)

    # ── Formas de pago ────────────────────────────────────────────────────────
    bancos_lista = []
    try:
        lista_bancos = db.query(models.Lista).filter_by(nombre='bancos').first()
        if lista_bancos:
            bancos_lista = [b for b in json.loads(lista_bancos.items or "[]")
                            if b.strip().lower() not in ('efectivo', 'cash')]
    except Exception:
        pass

    if bancos_lista:
        y -= 22
        c.setFillColor(colors.HexColor("#1E40AF"))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, "Formas de pago:")

        # Encabezado de columnas
        y -= 18
        c.setFillColor(colors.HexColor("#1E40AF"))
        c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(58, y, "Entidad")
        c.drawString(280, y, "N° Cuenta / Referencia")

        for banco in bancos_lista:
            y -= 18
            if ' - ' in banco:
                nombre_b, cuenta_b = banco.split(' - ', 1)
            else:
                nombre_b, cuenta_b = banco, ''
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 8)
            c.drawString(58, y, nombre_b)
            if cuenta_b:
                c.setFont("Helvetica-Bold", 8)
                c.drawString(280, y, cuenta_b)
            # Línea separadora
            c.setStrokeColor(colors.HexColor("#E2E8F0"))
            c.setLineWidth(0.4)
            c.line(50, y - 6, W - 50, y - 6)

    # Banco seleccionado en la factura
    if fact.get('banco'):
        y -= 18
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#374151"))
        c.drawString(50, y, f"Pago registrado en: {fact.get('banco','')}")

    c.save()

    content_buf.seek(0)
    content_pdf = PyPDF2.PdfReader(content_buf)
    plantilla_file = open(plantilla_path, 'rb')
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
    plantilla_file.close()

    codigo = fact.get('codigo', str(id))
    return StreamingResponse(
        out_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="factura_{codigo}.pdf"'},
    )
