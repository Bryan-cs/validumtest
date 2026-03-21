"""Router de afiliados."""
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

router = APIRouter(prefix="/afiliados", tags=["afiliados"])


@router.get("")
def list_afiliados(
    q: str = "", estado: str = "", empresa: str = "",
    cliente: str = "", subtipo: str = "",
    skip: int = 0, limit: int = 0,
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    """Lista afiliados. Con skip/limit activa paginación.
    Sin limit devuelve todos (usado por exportaciones Excel).
    Respuesta: {"total": N, "items": [...]}
    """
    return crud.get_afiliados(db, q=q, estado=estado, empresa=empresa,
                               cliente=cliente, subtipo=subtipo,
                               skip=skip, limit=limit)


@router.get("/{id}/certificado")
def certificado_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Genera un certificado de inicio de afiliación en PDF con membrete corporativo."""
    import PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors

    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")

    plantilla_path = os.path.join(os.path.dirname(__file__), '..', '..', 'plantilla.pdf')
    if not os.path.exists(plantilla_path):
        raise HTTPException(500, "Plantilla no encontrada")

    content_buf = io.BytesIO()
    c = canvas.Canvas(content_buf, pagesize=letter)
    W, H = letter

    def txt(x, y, text, size=10, bold=False, color=colors.black, align="left"):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(color)
        if align == "center":
            c.drawCentredString(x, y, str(text or ""))
        elif align == "right":
            c.drawRightString(x, y, str(text or ""))
        else:
            c.drawString(x, y, str(text or ""))

    fecha_hoy = datetime.now().strftime("%d de %B de %Y").replace(
        "January","enero").replace("February","febrero").replace("March","marzo"
        ).replace("April","abril").replace("May","mayo").replace("June","junio"
        ).replace("July","julio").replace("August","agosto").replace("September","septiembre"
        ).replace("October","octubre").replace("November","noviembre").replace("December","diciembre")

    y = H - 185

    txt(W/2, y, "CERTIFICADO DE INICIO DE AFILIACIÓN", size=14, bold=True,
        color=colors.HexColor("#1E40AF"), align="center")
    y -= 10
    c.setStrokeColor(colors.HexColor("#1E40AF"))
    c.setLineWidth(1.5)
    c.line(80, y, W - 80, y)

    y -= 30
    nombre    = a.get('nombre','')
    tipo_doc  = a.get('tipo_doc','CC')
    doc       = a.get('doc','')
    empresa   = a.get('empresa','')
    cliente   = a.get('cliente_txt','')
    cargo     = a.get('cargo','')
    servicios = a.get('servicios', [])

    parrafo = (
        f"Por medio del presente documento, la Precooperativa Solidaria de Seguros del Caribe "
        f"CARSECOOP certifica que el señor(a):"
    )
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    from reportlab.lib.utils import simpleSplit
    lines = simpleSplit(parrafo, "Helvetica", 10, W - 130)
    for line in lines:
        c.drawString(65, y, line)
        y -= 14

    y -= 10
    c.setFillColor(colors.HexColor("#EFF6FF"))
    c.roundRect(65, y - 66, W - 130, 76, 6, fill=1, stroke=0)

    y -= 6
    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.HexColor("#1E40AF"))
    c.drawString(80, y, nombre)
    y -= 16
    c.setFont("Helvetica", 10); c.setFillColor(colors.black)
    c.drawString(80, y, f"{tipo_doc}:  {doc}")
    if empresa:
        c.drawString(320, y, f"Empresa:  {empresa}")
    y -= 14
    if cargo:
        c.drawString(80, y, f"Cargo:  {cargo}")
    if cliente:
        c.drawString(320, y, f"Cliente:  {cliente}")

    y -= 30
    parrafo2 = (
        "ha iniciado satisfactoriamente su proceso de afiliación al sistema de seguridad social, "
        "quedando vinculado a los siguientes servicios:"
    )
    lines2 = simpleSplit(parrafo2, "Helvetica", 10, W - 130)
    for line in lines2:
        c.drawString(65, y, line)
        y -= 14

    y -= 8
    for srv in servicios:
        c.setFillColor(colors.HexColor("#1E40AF"))
        c.circle(78, y + 3, 3, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(88, y, srv)
        y -= 16

    y -= 14
    parrafo3 = (
        f"Lo anterior, aceptando los términos y condiciones de contratación del servicio. "
        f"Se expide el presente certificado a los {fecha_hoy}, "
        f"para los fines que el interesado estime convenientes."
    )
    lines3 = simpleSplit(parrafo3, "Helvetica", 10, W - 130)
    for line in lines3:
        c.drawString(65, y, line)
        y -= 14

    c.save()

    content_buf.seek(0)
    content_pdf  = PyPDF2.PdfReader(content_buf)
    plantilla_file = open(plantilla_path, 'rb')
    plantilla_pdf  = PyPDF2.PdfReader(plantilla_file)

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

    nombre_archivo = nombre.replace(" ", "_")[:30]
    return StreamingResponse(
        out_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado_{nombre_archivo}.pdf"'},
    )


@router.get("/{id}/estado-cuenta")
def estado_cuenta_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Genera un PDF 'Estado de Cuenta' del afiliado con todas sus facturas."""
    import PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.utils import simpleSplit

    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")

    plantilla_path = os.path.join(os.path.dirname(__file__), '..', '..', 'plantilla.pdf')
    if not os.path.exists(plantilla_path):
        raise HTTPException(500, "Plantilla no encontrada")

    # Obtener todas las facturas del afiliado
    facturas = (
        db.query(models.Factura)
        .filter(models.Factura.doc == a.get('doc'))
        .order_by(models.Factura.anio.desc(), models.Factura.mes)
        .all()
    )

    content_buf = io.BytesIO()
    c = canvas.Canvas(content_buf, pagesize=letter)
    W, H = letter

    def money(v):
        try:
            return f"$ {int(v):,}".replace(",", ".")
        except:
            return "$ 0"

    def txt(x, y, text, size=10, bold=False, color=colors.black, align="left"):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(color)
        if align == "center":
            c.drawCentredString(x, y, str(text or ""))
        elif align == "right":
            c.drawRightString(x, y, str(text or ""))
        else:
            c.drawString(x, y, str(text or ""))

    y = H - 185

    # Título
    txt(W/2, y, "ESTADO DE CUENTA", size=14, bold=True,
        color=colors.HexColor("#1E40AF"), align="center")
    y -= 10
    c.setStrokeColor(colors.HexColor("#1E40AF"))
    c.setLineWidth(1.5)
    c.line(80, y, W - 80, y)

    # Datos del afiliado
    y -= 20
    c.setFillColor(colors.HexColor("#EFF6FF"))
    c.roundRect(65, y - 56, W - 130, 66, 6, fill=1, stroke=0)
    y -= 6

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.drawString(80, y, a.get('nombre', ''))
    y -= 16
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(80, y, f"{a.get('tipo_doc','CC')}:  {a.get('doc','')}")
    c.drawString(320, y, f"Empresa:  {a.get('empresa','—')}")
    y -= 14
    c.drawString(80, y, f"Cliente:  {a.get('cliente_txt','—')}")
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    c.drawString(320, y, f"Fecha:  {fecha_hoy}")

    # Tabla de facturas
    y -= 30
    txt(50, y, "DETALLE DE FACTURAS", size=9, bold=True, color=colors.HexColor("#1E40AF"))
    y -= 6

    # Cabecera de tabla
    y -= 16
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    col_x = [55, 140, 210, 310, 390, 460]
    headers = ["Período", "Código", "Servicios ($)", "Total", "Estado", "Banco"]
    for hdr, cx in zip(headers, col_x):
        c.drawString(cx, y, hdr)

    row_colors = [colors.HexColor("#F8FAFC"), colors.white]
    total_pagado = 0
    total_pendiente = 0

    for idx, f in enumerate(facturas):
        y -= 16
        if y < 80:
            # Si nos quedamos sin espacio, continuar en nueva página no implementado
            # por simplicidad mostramos hasta donde alcance
            break
        c.setFillColor(row_colors[idx % 2])
        c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)

        periodo = f"{f.mes} {f.anio}"
        total_val = f.costos or 0
        estado_color = colors.HexColor("#16A34A") if f.estado == "pagado" else colors.HexColor("#DC2626")

        c.drawString(col_x[0], y, periodo[:18])
        c.drawString(col_x[1], y, str(f.codigo or '')[:14])
        c.drawString(col_x[2], y, money(f.ingresos or 0))
        c.drawString(col_x[3], y, money(total_val))
        c.setFillColor(estado_color)
        c.drawString(col_x[4], y, str(f.estado or '').upper()[:10])
        c.setFillColor(colors.black)
        c.drawString(col_x[5], y, str(f.banco or '')[:12])

        if f.estado == "pagado":
            total_pagado += total_val
        else:
            total_pendiente += total_val

    # Resumen
    y -= 24
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.line(50, y + 8, W - 50, y + 8)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#16A34A"))
    c.drawString(50, y, f"Total pagado: {money(total_pagado)}")
    c.setFillColor(colors.HexColor("#DC2626"))
    c.drawString(230, y, f"Total pendiente: {money(total_pendiente)}")
    c.setFillColor(colors.HexColor("#1E40AF"))
    c.drawString(430, y, f"Total general: {money(total_pagado + total_pendiente)}")

    c.save()

    # Combinar con plantilla
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

    nombre_archivo = a.get('nombre', '').replace(" ", "_")[:30]
    return StreamingResponse(
        out_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="estado_cuenta_{nombre_archivo}.pdf"'},
    )


@router.get("/{id}")
def get_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")
    return a


@router.post("", status_code=201)
def create_afiliado(data: schemas.AfiliadoCreate,
                    db: Session = Depends(get_db), token=Depends(verify_token)):
    existing = crud.get_afiliado_by_doc(db, data.doc)
    if existing:
        raise HTTPException(400, f"Ya existe un afiliado con documento {data.doc}: {existing.nombre}")
    data.registrado_por = token.get("sub", "sistema")
    return crud.create_afiliado(db, data)


@router.put("/{id}")
def update_afiliado(id: int, data: schemas.AfiliadoCreate,
                    db: Session = Depends(get_db), token=Depends(verify_token)):
    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")
    existing = crud.get_afiliado_by_doc(db, data.doc)
    if existing and existing.id != id:
        raise HTTPException(400, f"Otro afiliado ya tiene el documento {data.doc}")
    return crud.update_afiliado(db, id, data, editor=token.get("sub", "sistema"))


@router.delete("/{id}")
def delete_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    a = db.query(models.Afiliado).filter_by(id=id, activo=True).first()
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")
    pendientes = crud.get_facturas_pendientes_by_doc(db, a.doc)
    crud.delete_afiliado(db, id, deleted_by=token.get("sub", "sistema"))
    return {"ok": True, "facturas_pendientes": len(pendientes),
            "codigos": [f.codigo for f in pendientes]}
