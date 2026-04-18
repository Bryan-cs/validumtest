"""Router de reportes Excel."""
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import crud
import models
from .deps import verify_token

router = APIRouter(prefix="/reportes", tags=["reportes"])


def _hdr_style(ws, cols: list, row: int = 1):
    fill = PatternFill("solid", fgColor="1E40AF")
    font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(bottom=Side(style="medium", color="FFFFFF"))
    for i, col in enumerate(cols, 1):
        c = ws.cell(row=row, column=i, value=col)
        c.fill = fill
        c.font = font
        c.alignment = Alignment(horizontal="center")
        c.border = border


def _xlsx_response(wb: openpyxl.Workbook, filename: str):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cobro")
def reporte_cobro(
    empresa: str = "", cliente: str = "", tipo: str = "",
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    items = crud.get_cobro(db, empresa=empresa, cliente=cliente, tipo=tipo)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cobro"
    cols = ["#", "Nombre", "Tipo Doc", "Documento", "Empresa", "Cliente", "Día cobro", "Servicios", "Planilla ($)", "Estado"]
    _hdr_style(ws, cols)
    for i, r in enumerate(items, 1):
        srvs = r.get("servicios") or []
        srvs_str = ", ".join(srvs) if isinstance(srvs, list) else str(srvs)
        ws.append([i, r.get("nombre"), r.get("tipo_doc", ""), r.get("doc"), r.get("empresa"), r.get("cliente"),
                   r.get("dia_cobro"), srvs_str, r.get("planilla", 0), r.get("estado")])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or "")), 12)
    return _xlsx_response(wb, "cobro.xlsx")


@router.get("/afiliados")
def reporte_afiliados(
    q: str = "", estado: str = "", empresa: str = "",
    cliente: str = "", subtipo: str = "",
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    result = crud.get_afiliados(db, q=q, estado=estado, empresa=empresa,
                                cliente=cliente, subtipo=subtipo, skip=0, limit=0)
    items = result.get("items", [])
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Afiliados"
    cols = ["#", "Nombre", "Tipo Doc", "Documento", "Empresa", "Cliente", "Cargo", "EPS", "ARL", "AFP", "CCF",
            "Subtipo", "Estado", "Estado Servicio", "Servicios", "IBC", "Tel", "Email", "Fecha Ingreso", "Fecha Afiliación", "Obs"]
    _hdr_style(ws, cols)
    for i, a in enumerate(items, 1):
        srvs = a.get("servicios") or []
        srvs_str = ", ".join(srvs) if isinstance(srvs, list) else str(srvs)
        ws.append([i, a.get("nombre"), a.get("tipo_doc", ""), a.get("doc"), a.get("empresa"), a.get("cliente_txt"),
                   a.get("cargo"), a.get("eps"), a.get("arl"), a.get("afp"), a.get("ccf"),
                   a.get("subtipo"), a.get("estado"), a.get("estado_srv"), srvs_str,
                   a.get("ibc"), a.get("tel"), a.get("email"),
                   a.get("fecha_ingreso"), a.get("fecha_afiliacion"), a.get("obs")])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or "")), 12)
    return _xlsx_response(wb, "afiliados.xlsx")


@router.get("/retiros")
def reporte_retiros(
    anio: str = "", mes: str = "",
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    result = crud.get_retiros(db, anio=anio, mes=mes)
    items = result.get("items", []) if isinstance(result, dict) else result
    # Batch lookup tipo_doc desde afiliados (retiro no guarda tipo_doc)
    docs_ret = list({r.get("doc") for r in items if r.get("doc")})
    tipo_doc_map = {}
    if docs_ret:
        afils = db.query(models.Afiliado.doc, models.Afiliado.tipo_doc)\
                  .filter(models.Afiliado.doc.in_(docs_ret)).all()
        tipo_doc_map = {a.doc: (a.tipo_doc or "") for a in afils}
        # también buscar en eliminados por si el afiliado ya no existe
        from models import Eliminado
        eliminados_docs = [d for d in docs_ret if d not in tipo_doc_map]
        if eliminados_docs:
            for e in db.query(models.Eliminado).filter(models.Eliminado.doc.in_(eliminados_docs)).all():
                import json as _j
                try:
                    datos = _j.loads(e.datos_completos or "{}")
                    tipo_doc_map[e.doc] = datos.get("tipo_doc", "")
                except Exception:
                    pass
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Retiros"
    cols = ["#", "Nombre", "Tipo Doc", "Documento", "Empresa", "Fecha", "Motivo", "Mes", "Año", "Observaciones", "Registrado por"]
    _hdr_style(ws, cols)
    for i, r in enumerate(items, 1):
        ws.append([i, r.get("nombre"), tipo_doc_map.get(r.get("doc"), ""), r.get("doc"),
                   r.get("empresa"), r.get("fecha"), r.get("motivo"),
                   r.get("mes"), r.get("anio"), r.get("obs"), r.get("registrado_por")])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or "")), 12)
    return _xlsx_response(wb, f"retiros{'_'+anio if anio else ''}{'_'+mes if mes else ''}.xlsx")


@router.get("/financiero")
def reporte_financiero(
    anio: str = "", mes: str = "", cliente: str = "", estado: str = "", banco: str = "",
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    result = crud.get_facturas(db, anio=anio, mes=mes, cliente=cliente,
                               estado=estado, banco=banco, skip=0, limit=0)
    items = result.get("items", []) if isinstance(result, dict) else result

    # Mapa doc → (empresa, subtipo) para enriquecer el reporte
    docs = list({f.get("doc") for f in items if f.get("doc")})
    afil_map = {}
    if docs:
        afils = db.query(models.Afiliado.doc, models.Afiliado.empresa,
                         models.Afiliado.subtipo, models.Afiliado.tipo_doc)\
                  .filter(models.Afiliado.doc.in_(docs)).all()
        afil_map = {a.doc: (a.empresa or "", a.subtipo or "", a.tipo_doc or "") for a in afils}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Facturación"
    cols = ["#", "Código", "Afiliado", "Tipo Doc", "Documento", "Empresa", "Subtipo", "Servicios",
            "Cliente", "Mes", "Año", "Período (días)", "Ingresos", "Planilla", "Costo Adm.",
            "Utilidad", "Banco", "Estado", "Fecha pago"]
    _hdr_style(ws, cols)
    tot_ing = tot_plan = tot_util = 0
    docs_con_factura = set()
    for i, f in enumerate(items, 1):
        emp, sub, tipo_doc = afil_map.get(f.get("doc"), ("", "", ""))
        servicios_txt = ", ".join(s["servicio"] for s in (f.get("servicios_detalle") or []) if s.get("servicio"))
        _fp = f.get("pagado_en") or ""
        if _fp and len(_fp) >= 10:
            _d = _fp[:10].split("-")  # YYYY-MM-DD → DD/MM/YYYY
            fecha_pago = f"{_d[2]}/{_d[1]}/{_d[0]}" if len(_d) == 3 else _fp[:10]
        else:
            fecha_pago = ""
        ws.append([i, f.get("codigo"), f.get("nombre_afiliado"), tipo_doc, f.get("doc"),
                   emp, sub, servicios_txt,
                   f.get("cliente"), f.get("mes"), f.get("anio"), f.get("periodo"),
                   f.get("ingresos", 0), f.get("costos", 0), f.get("costo_adm", 0),
                   f.get("utilidad", 0), f.get("banco"), f.get("estado"), fecha_pago])
        tot_ing += f.get("ingresos", 0) or 0
        tot_plan += f.get("costos", 0) or 0
        tot_util += f.get("utilidad", 0) or 0
        if f.get("doc"):
            docs_con_factura.add(f["doc"])
    last = ws.max_row + 1
    ws.cell(last, 1, "TOTAL")
    ws.cell(last, 1).font = Font(bold=True)
    ws.cell(last, 13, tot_ing).font = Font(bold=True)
    ws.cell(last, 14, tot_plan).font = Font(bold=True)
    ws.cell(last, 16, tot_util).font = Font(bold=True)

    # ── Sección: Afiliados sin factura en el período ──
    afiliados_activos = db.query(models.Afiliado).filter_by(activo=True).order_by(models.Afiliado.nombre).all()
    sin_factura = [a for a in afiliados_activos if a.doc not in docs_con_factura]
    if sin_factura:
        periodo_label = f"{mes} {anio}".strip() if (mes or anio) else "el período"
        sep_row = ws.max_row + 2
        ws.cell(sep_row, 1, f"AFILIADOS SIN FACTURA EN {periodo_label.upper()}").font = Font(bold=True, size=12, color="DC2626")
        hdr_row = sep_row + 1
        sin_cols = ["#", "Nombre", "Tipo Doc", "Documento", "Empresa", "Subtipo", "EPS", "ARL", "Estado"]
        _hdr_style(ws, sin_cols, row=hdr_row)
        for j, a in enumerate(sin_factura, 1):
            ws.append([j, a.nombre, a.tipo_doc or "", a.doc, a.empresa or "", a.subtipo or "",
                       a.eps or "", a.arl or "", a.estado_srv or a.estado or ""])

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or "")), 14)
    return _xlsx_response(wb, f"financiero{'_'+anio if anio else ''}{'_'+mes if mes else ''}.xlsx")


@router.get("/consolidado")
def reporte_consolidado(
    anio: str = "", mes: str = "",
    db: Session = Depends(get_db), token=Depends(verify_token)
):
    dash = crud.get_dashboard(db, anio=anio, mes=mes)
    afil_result = crud.get_afiliados(db, skip=0, limit=0)
    afiliados = afil_result.get("items", [])
    facturas_result = crud.get_facturas(db, anio=anio, mes=mes, skip=0, limit=0)
    facturas = facturas_result.get("items", []) if isinstance(facturas_result, dict) else facturas_result

    wb = openpyxl.Workbook()

    ws1 = wb.active
    ws1.title = "Resumen"
    ws1.append(["BBC FILE — Reporte Consolidado"])
    ws1["A1"].font = Font(bold=True, size=14, color="1E40AF")
    ws1.append([f"Período: {mes or 'Todos'} {anio or 'Todos los años'}"])
    ws1.append([])
    ws1.append(["AFILIADOS"])
    ws1["A4"].font = Font(bold=True)
    ws1.append(["Activos", dash.get("activos", 0)])
    ws1.append(["Retirados", dash.get("retirados", 0)])
    ws1.append(["Suspendidos", dash.get("suspendidos", 0)])
    ws1.append(["Total", dash.get("total_afiliados", 0)])
    ws1.append([])
    ws1.append(["FINANCIERO"])
    ws1["A10"].font = Font(bold=True)
    ws1.append(["Facturas emitidas", dash.get("facturas", 0)])
    ws1.append(["Ingresos", dash.get("ingresos", 0)])
    ws1.append(["Pendiente cobro", dash.get("pendiente_cobro", 0)])
    ws1.append(["Nóminas empleados", dash.get("nominas", 0)])
    ws1.append(["Gastos fijos", dash.get("gastos_fijos", 0)])
    ws1.append(["Utilidad neta", dash.get("utilidad_neta", 0)])
    ws1.column_dimensions["A"].width = 22
    ws1.column_dimensions["B"].width = 18

    ws2 = wb.create_sheet("Afiliados")
    cols2 = ["#", "Nombre", "Tipo Doc", "Documento", "Empresa", "Cliente", "EPS", "ARL", "AFP", "CCF", "Estado", "Servicios", "IBC"]
    _hdr_style(ws2, cols2)
    for i, a in enumerate(afiliados, 1):
        srvs = a.get("servicios") or []
        srvs_str = ", ".join(srvs) if isinstance(srvs, list) else str(srvs)
        ws2.append([i, a.get("nombre"), a.get("tipo_doc", ""), a.get("doc"), a.get("empresa"), a.get("cliente_txt"),
                    a.get("eps"), a.get("arl"), a.get("afp"), a.get("ccf"),
                    a.get("estado_srv") or a.get("estado"), srvs_str, a.get("ibc")])
    for col in ws2.columns:
        ws2.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or "")), 12)

    ws3 = wb.create_sheet("Facturas")
    # Mapa doc → tipo_doc para la hoja de facturas del consolidado
    _docs_f = list({f.get("doc") for f in facturas if f.get("doc")})
    _tdoc_map = {}
    if _docs_f:
        _afils3 = db.query(models.Afiliado.doc, models.Afiliado.tipo_doc)\
                    .filter(models.Afiliado.doc.in_(_docs_f)).all()
        _tdoc_map = {a.doc: (a.tipo_doc or "") for a in _afils3}
    cols3 = ["#", "Código", "Afiliado", "Tipo Doc", "Documento", "Cliente", "Mes", "Año", "Ingresos", "Planilla", "Utilidad", "Estado"]
    _hdr_style(ws3, cols3)
    for i, f in enumerate(facturas, 1):
        ws3.append([i, f.get("codigo"), f.get("nombre_afiliado"),
                    _tdoc_map.get(f.get("doc"), ""), f.get("doc"),
                    f.get("cliente"), f.get("mes"), f.get("anio"), f.get("ingresos", 0),
                    f.get("costos", 0), f.get("utilidad", 0), f.get("estado")])
    for col in ws3.columns:
        ws3.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or "")), 12)

    return _xlsx_response(wb, f"consolidado_bbcfile{'_'+anio if anio else ''}.xlsx")
