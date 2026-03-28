import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import verify_token
import models

router = APIRouter(prefix="/documentos", tags=["documentos"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
ALLOWED_EXT = {'pdf','jpg','jpeg','png','gif','doc','docx','xls','xlsx'}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("")
async def subir_documento(
    file: UploadFile = File(...),
    afiliado_doc: str = Form(''),
    contexto: str = Form("afiliado"),
    contexto_id: int = Form(None),
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    ext = (file.filename or '').rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Formato no permitido. Permitidos: {', '.join(sorted(ALLOWED_EXT))}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "Archivo demasiado grande (máx 10 MB)")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, unique_name)
    with open(filepath, 'wb') as f:
        f.write(content)

    doc = models.Documento(
        afiliado_doc=afiliado_doc,
        nombre=file.filename,
        tipo=ext,
        ruta=unique_name,
        tamano=len(content),
        subido_por=token.get("sub", "sistema"),
        contexto=contexto,
        contexto_id=contexto_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "nombre": doc.nombre, "tipo": doc.tipo, "tamano": doc.tamano, "creado": doc.creado.isoformat() if doc.creado else None}


@router.get("")
def listar_documentos(
    afiliado_doc: str = Query(None),
    contexto: str = Query(None),
    contexto_id: int = Query(None),
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    q = db.query(models.Documento)
    if afiliado_doc:
        q = q.filter_by(afiliado_doc=afiliado_doc)
    if contexto:
        q = q.filter_by(contexto=contexto)
    if contexto_id is not None:
        q = q.filter_by(contexto_id=contexto_id)
    docs = q.order_by(models.Documento.creado.desc()).all()
    return [
        {
            "id": d.id, "afiliado_doc": d.afiliado_doc,
            "nombre": d.nombre, "tipo": d.tipo, "tamano": d.tamano,
            "subido_por": d.subido_por, "contexto": d.contexto,
            "contexto_id": d.contexto_id,
            "creado": d.creado.isoformat() if d.creado else None,
        }
        for d in docs
    ]


@router.get("/{doc_id}/descargar")
def descargar_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    doc = db.query(models.Documento).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    # Clientes solo pueden descargar sus propios documentos
    if token.get("rol") == "cliente":
        cliente_ref = token.get("cliente_ref", "")
        if doc.contexto not in ("novedad_portal", "novedad_resp") or doc.subido_por != token["sub"]:
            # Verificar que el documento pertenezca a un afiliado del cliente
            if doc.afiliado_doc:
                afil = db.query(models.Afiliado).filter_by(doc=doc.afiliado_doc, cliente_txt=cliente_ref).first()
                if not afil:
                    raise HTTPException(403, "No tienes acceso a este documento")
            elif doc.contexto == "novedad_resp":
                pass  # Respuestas del admin son visibles para el cliente destinatario
            else:
                raise HTTPException(403, "No tienes acceso a este documento")
    filepath = os.path.realpath(os.path.join(UPLOAD_DIR, doc.ruta))
    if not filepath.startswith(os.path.realpath(UPLOAD_DIR)):
        raise HTTPException(403, "Ruta de archivo no permitida")
    if not os.path.exists(filepath):
        raise HTTPException(404, "Archivo no encontrado en disco")
    return FileResponse(filepath, filename=doc.nombre, media_type="application/octet-stream")


@router.delete("/{doc_id}")
def eliminar_documento(
    doc_id: int,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    doc = db.query(models.Documento).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    if token.get("rol") != "admin" and doc.subido_por != token.get("sub"):
        raise HTTPException(403, "Solo puedes eliminar tus propios documentos")
    filepath = os.path.realpath(os.path.join(UPLOAD_DIR, doc.ruta))
    if filepath.startswith(os.path.realpath(UPLOAD_DIR)) and os.path.exists(filepath):
        os.remove(filepath)
    db.delete(doc)
    db.commit()
    return {"ok": True}
