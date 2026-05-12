"""Router de afiliados."""
import io
import os
import json
from datetime import datetime
from models import COL_TZ
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, crud
from .deps import verify_token, require_admin, require_admin_or_empleado

router = APIRouter(prefix="/afiliados", tags=["afiliados"])


@router.get("/filter-options")
def filter_options(db: Session = Depends(get_db), token=Depends(verify_token)):
    """Retorna opciones únicas para cada filtro de afiliados (ligero, cacheado)."""
    return crud.get_afiliados_filter_options(db)


@router.get("/recientes")
def afiliados_recientes(db: Session = Depends(get_db), token=Depends(verify_token)):
    """Últimos 5 afiliados activos por fecha de creación."""
    rows = (
        db.query(models.Afiliado)
        .filter(models.Afiliado.activo == True)
        .order_by(models.Afiliado.creado.desc())
        .limit(5)
        .all()
    )
    return [
        {
            "id": a.id,
            "nombre": a.nombre,
            "doc": a.doc,
            "empresa": a.empresa,
            "eps": a.eps,
            "creado": a.creado.isoformat() if a.creado else None,
        }
        for a in rows
    ]


@router.get("")
def list_afiliados(
    q: str = "", estado: str = "", empresa: str = "",
    cliente: str = "", subtipo: str = "",
    tipo_doc: str = "", ccf: str = "", eps: str = "",
    fecha_desde: str = "", fecha_hasta: str = "",
    skip: int = 0, limit: int = 0,
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    """Lista afiliados con filtros multi-valor (CSV) y paginación.

    Cada filtro acepta valores separados por coma: ?empresa=A,B&estado=ACTIVO,SUSPENDIDO
    Con skip/limit activa paginación. Sin limit devuelve todos (exportaciones Excel).
    """
    # Clientes solo ven sus propios afiliados
    if token.get("rol") == "cliente":
        cliente_ref = (token.get("cliente_ref") or "").strip()
        if not cliente_ref:
            return {"total": 0, "items": []}
        cliente = cliente_ref
    return crud.get_afiliados(db, q=q, estado=estado, empresa=empresa,
                               cliente=cliente, subtipo=subtipo,
                               tipo_doc=tipo_doc, ccf=ccf, eps=eps,
                               fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
                               skip=skip, limit=limit)


@router.get("/{id}/certificado")
def certificado_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Genera un certificado de inicio de afiliación en PDF con membrete corporativo."""
    import pypdf as PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors

    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")

    plantilla_path = os.path.join(os.path.dirname(__file__), '..', 'plantilla.pdf')
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

    fecha_hoy = datetime.now(COL_TZ).strftime("%d de %B de %Y").replace(
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

    nombre_archivo = nombre.replace(" ", "_")[:30]
    return StreamingResponse(
        out_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado_{nombre_archivo}.pdf"'},
    )


@router.get("/{id}/estado-cuenta")
def estado_cuenta_afiliado(id: int, db: Session = Depends(get_db), token=Depends(verify_token)):
    """Genera un PDF 'Estado de Cuenta' del afiliado con todas sus facturas."""
    import pypdf as PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.utils import simpleSplit

    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")

    plantilla_path = os.path.join(os.path.dirname(__file__), '..', 'plantilla.pdf')
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
        except (ValueError, TypeError):
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
    fecha_hoy = datetime.now(COL_TZ).strftime("%d/%m/%Y")
    c.drawString(320, y, f"Fecha:  {fecha_hoy}")

    # Tabla de facturas
    col_x  = [55, 140, 210, 310, 390, 460]
    hdrs   = ["Período", "Código", "Servicios", "Total", "Estado", "Banco"]
    row_bg = [colors.HexColor("#F8FAFC"), colors.white]

    def cabecera(yy):
        c.setFillColor(colors.HexColor("#1E40AF"))
        c.rect(50, yy - 4, W - 100, 16, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        for hdr, cx in zip(hdrs, col_x):
            c.drawString(cx, yy, hdr)
        return yy - 16

    y -= 30
    txt(50, y, "DETALLE DE FACTURAS", size=9, bold=True, color=colors.HexColor("#1E40AF"))
    y -= 22
    y = cabecera(y)

    total_pagado   = 0
    total_pendiente = 0

    for idx, fac in enumerate(facturas):
        if y < 80:
            c.showPage()
            y = H - 120
            txt(W/2, y, "ESTADO DE CUENTA (continuación)", size=11, bold=True,
                color=colors.HexColor("#1E40AF"), align="center")
            y -= 10
            c.setStrokeColor(colors.HexColor("#1E40AF"))
            c.setLineWidth(1.5)
            c.line(80, y, W - 80, y)
            y -= 20
            y = cabecera(y)

        # Parsear servicios
        try:
            srvs = json.loads(fac.servicios_detalle or "[]")
            if not isinstance(srvs, list):
                srvs = []
        except (json.JSONDecodeError, TypeError):
            srvs = []
        nombres_srvs = ", ".join(s.get("servicio", "") for s in srvs if s.get("incluido", True))
        # Si no hay servicios_detalle, usar servicios del afiliado como fallback
        if not nombres_srvs:
            try:
                srvs_afil = json.loads(a.get('servicios') or "[]") if isinstance(a.get('servicios'), str) else (a.get('servicios') or [])
                nombres_srvs = ", ".join(str(s) for s in srvs_afil if s)
            except Exception:
                pass

        total_val    = fac.ingresos or 0
        es_pagada    = fac.estado in ("pagado", "planilla_pagada")
        estado_color = colors.HexColor("#16A34A") if es_pagada else colors.HexColor("#DC2626")
        estado_label = "PAGADA" if es_pagada else "PENDIENTE"

        c.setFillColor(row_bg[idx % 2])
        c.rect(50, y - 4, W - 100, 16, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        c.drawString(col_x[0], y, str(fac.mes or '') + " " + str(fac.anio or ''))
        c.drawString(col_x[1], y, str(fac.codigo or '')[:14])
        c.setFont("Helvetica", 7)
        c.drawString(col_x[2], y, nombres_srvs[:30] if nombres_srvs else "")
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.black)
        c.drawString(col_x[3], y, money(total_val))
        c.setFillColor(estado_color)
        c.drawString(col_x[4], y, estado_label)
        c.setFillColor(colors.black)
        c.drawString(col_x[5], y, str(fac.banco or '')[:12])

        if es_pagada:
            total_pagado += total_val
        else:
            total_pendiente += total_val

        y -= 16

    # Resumen — nueva página si no hay espacio
    if y < 60:
        c.showPage()
        y = H - 120

    y -= 8
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.line(50, y + 8, W - 50, y + 8)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#16A34A"))
    c.drawString(50, y, f"Total pagado: {money(total_pagado)}")
    c.setFillColor(colors.HexColor("#DC2626"))
    c.drawString(230, y, f"Total pendiente: {money(total_pendiente)}")

    c.save()

    # Combinar con plantilla — cada página de contenido se fusiona con la plantilla
    content_buf.seek(0)
    content_pdf = PyPDF2.PdfReader(content_buf)

    with open(plantilla_path, 'rb') as plantilla_file:
        plantilla_bytes = plantilla_file.read()

    writer = PyPDF2.PdfWriter()
    for content_page in content_pdf.pages:
        plantilla_buf = io.BytesIO(plantilla_bytes)
        plantilla_pdf = PyPDF2.PdfReader(plantilla_buf)
        base_page = plantilla_pdf.pages[0]
        base_page.merge_page(content_page)
        writer.add_page(base_page)

    out_buf = io.BytesIO()
    writer.write(out_buf)
    out_buf.seek(0)

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
                    db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    registrado_por = token.get("sub", "sistema")
    # Si existe un afiliado activo sin registro de eliminado → bloquear (afiliado real)
    activo = crud.get_afiliado_by_doc(db, data.doc)
    eliminado_reg = db.query(models.Eliminado).filter_by(doc=data.doc).first()
    if activo and not eliminado_reg:
        raise HTTPException(400, f"Ya existe un afiliado activo con documento {data.doc}: {activo.nombre}")
    # Limpiar cualquier rastro anterior del doc (fila inactiva, eliminado, retiro, facturas)
    db.query(models.Afiliado).filter_by(doc=data.doc).delete()
    db.query(models.Factura).filter_by(doc=data.doc).delete()
    db.query(models.Retiro).filter_by(doc=data.doc).delete()
    if eliminado_reg:
        db.delete(eliminado_reg)
    db.flush()
    crud._log(db, registrado_por, "reingresó un afiliado (historial limpiado)", "Afiliados", data.nombre)
    data.registrado_por = registrado_por
    return crud.create_afiliado(db, data)


@router.put("/{id}")
def update_afiliado(id: int, data: schemas.AfiliadoCreate,
                    db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    a = crud.get_afiliado(db, id)
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")
    existing = crud.get_afiliado_by_doc(db, data.doc)
    if existing and existing.id != id:
        raise HTTPException(400, f"Otro afiliado ya tiene el documento {data.doc}")
    return crud.update_afiliado(db, id, data, editor=token.get("sub", "sistema"))


@router.delete("/{id}")
def delete_afiliado(id: int, db: Session = Depends(get_db), token=Depends(require_admin_or_empleado)):
    a = db.query(models.Afiliado).filter_by(id=id, activo=True).first()
    if not a:
        raise HTTPException(404, "Afiliado no encontrado")
    pendientes = crud.get_facturas_pendientes_by_doc(db, a.doc)
    crud.delete_afiliado(db, id, deleted_by=token.get("sub", "sistema"))
    return {"ok": True, "facturas_pendientes": len(pendientes),
            "codigos": [f.codigo for f in pendientes]}
