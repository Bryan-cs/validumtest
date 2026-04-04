import os
import io
import uuid
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from routers.deps import verify_token
import models

CONTEXTOS_VALIDOS = Literal[
    "afiliado", "novedad_pago", "novedad_afil", "novedad_retiro",
    "resp_pago", "resp_afil", "resp_retiro", "planilla_pago",
]

router = APIRouter(prefix="/documentos", tags=["documentos"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
ALLOWED_EXT = {'pdf','jpg','jpeg','png','gif','doc','docx','xls','xlsx'}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB

# ─── Cloudflare R2 ───────────────────────────────────────────────────────────
_s3 = None
_s3_error = None  # Guarda el error de inicialización para diagnóstico
_R2_BUCKET = os.getenv("STORAGE_BUCKET", "")

def _get_s3():
    global _s3, _s3_error
    if _s3 is not None:
        return _s3
    account_id = os.getenv("STORAGE_ACCOUNT", "")
    access_key = os.getenv("STORAGE_KEY", "")
    secret_key = os.getenv("STORAGE_SECRET", "")
    if account_id and access_key and secret_key and _R2_BUCKET:
        try:
            import boto3
            _s3 = boto3.client(
                "s3",
                endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto",
            )
            # Verificar conexión
            _s3.head_bucket(Bucket=_R2_BUCKET)
            from logger import logger
            logger.info(f"R2 conectado: bucket '{_R2_BUCKET}'")
            _s3_error = None
        except Exception as e:
            from logger import logger
            logger.warning(f"R2 no disponible, usando disco local: {e}")
            _s3_error = f"{type(e).__name__}: {e}"
            _s3 = False  # False = intentó pero falló, no reintentar
    else:
        _s3 = False
        _s3_error = f"Missing vars: account={bool(account_id)}, key={bool(access_key)}, secret={bool(secret_key)}, bucket={bool(_R2_BUCKET)}"
    return _s3


def _upload_file(unique_name: str, content: bytes):
    """Sube archivo a R2 o disco local."""
    s3 = _get_s3()
    if s3:
        s3.put_object(Bucket=_R2_BUCKET, Key=unique_name, Body=content)
        return
    # Fallback: disco local
    dest = os.path.join(UPLOAD_DIR, unique_name)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as f:
        f.write(content)


def _download_file(unique_name: str):
    """Descarga archivo de R2 o disco local. Retorna (bytes, found)."""
    s3 = _get_s3()
    if s3:
        try:
            resp = s3.get_object(Bucket=_R2_BUCKET, Key=unique_name)
            return resp["Body"].read(), True
        except Exception:
            return None, False
    # Fallback: disco local
    filepath = os.path.realpath(os.path.join(UPLOAD_DIR, unique_name))
    if not filepath.startswith(os.path.realpath(UPLOAD_DIR)):
        return None, False
    if not os.path.exists(filepath):
        return None, False
    with open(filepath, 'rb') as f:
        return f.read(), True


def _delete_file(unique_name: str):
    """Elimina archivo de R2 o disco local."""
    s3 = _get_s3()
    if s3:
        try:
            s3.delete_object(Bucket=_R2_BUCKET, Key=unique_name)
        except Exception:
            pass
        return
    # Fallback: disco local
    filepath = os.path.realpath(os.path.join(UPLOAD_DIR, unique_name))
    if filepath.startswith(os.path.realpath(UPLOAD_DIR)) and os.path.exists(filepath):
        os.remove(filepath)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("")
async def subir_documento(
    file: UploadFile = File(...),
    afiliado_doc: str = Form(''),
    contexto: CONTEXTOS_VALIDOS = Form("afiliado"),
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

    # Sanitizar nombre: solo alfanuméricos, guiones, puntos y guiones bajos
    import re
    safe_name = re.sub(r'[^\w.\-]', '_', file.filename or 'archivo')
    file_id = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    if afiliado_doc:
        safe_doc = re.sub(r'[^\w\-]', '_', afiliado_doc)
        # Organizar por cliente si el afiliado existe en la DB
        afil = db.query(models.Afiliado).filter_by(doc=afiliado_doc).first()
        if afil and afil.cliente_txt:
            safe_cliente = re.sub(r'[^\w\-]', '_', afil.cliente_txt)
            unique_name = f"afiliados/{safe_cliente}/{safe_doc}/{file_id}"
        else:
            unique_name = f"afiliados/{safe_doc}/{file_id}"
    else:
        unique_name = file_id
    _upload_file(unique_name, content)

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
    # Clientes solo pueden descargar documentos de sus afiliados o respuestas del admin
    if token.get("rol") == "cliente":
        cliente_ref = token.get("cliente_ref", "")
        _ctx_cliente = ('novedad_pago', 'novedad_afil', 'novedad_retiro',
                        'resp_pago', 'resp_afil', 'resp_retiro', 'planilla_pago')
        if doc.contexto in _ctx_cliente or doc.subido_por == token["sub"]:
            pass  # Permitido: novedades del portal o archivos propios
        elif doc.afiliado_doc:
            afil = db.query(models.Afiliado).filter_by(doc=doc.afiliado_doc, cliente_txt=cliente_ref).first()
            if not afil:
                raise HTTPException(403, "No tienes acceso a este documento")
        else:
            raise HTTPException(403, "No tienes acceso a este documento")

    content, found = _download_file(doc.ruta)
    if not found:
        raise HTTPException(404, "Archivo no encontrado")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc.nombre}"'},
    )


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
    _delete_file(doc.ruta)
    db.delete(doc)
    db.commit()
    return {"ok": True}
