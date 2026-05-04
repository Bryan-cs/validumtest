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
    "resp_pago", "resp_afil", "resp_retiro", "planilla_pago", "tarea", "aviso",
]

router = APIRouter(prefix="/documentos", tags=["documentos"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
ALLOWED_EXT = {'pdf','jpg','jpeg','png','gif','doc','docx','xls','xlsx'}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic bytes por grupo de extensiones
_MAGIC = {
    'pdf':              b'%PDF',
    'jpg':              b'\xFF\xD8\xFF',
    'jpeg':             b'\xFF\xD8\xFF',
    'png':              b'\x89PNG',
    'gif':              b'GIF8',
    'docx':             b'PK\x03\x04',  # ZIP-based (Office Open XML)
    'xlsx':             b'PK\x03\x04',
    'doc':              b'\xD0\xCF\x11\xE0',  # OLE2 (Office legacy)
    'xls':              b'\xD0\xCF\x11\xE0',
}

def _validar_magic(ext: str, content: bytes) -> bool:
    magic = _MAGIC.get(ext)
    if magic is None:
        return True  # extensión sin firma conocida — pasar
    return content[:len(magic)] == magic

# ─── Cloudflare R2 ───────────────────────────────────────────────────────────
_s3 = None
_s3_error = None  # Guarda el error de inicialización para diagnóstico
_R2_BUCKET = os.getenv("STORAGE_BUCKET", "")

# En producción (PostgreSQL), R2 es obligatorio — disco Railway es efímero
_DB_URL = os.getenv("DATABASE_URL", "")
if _DB_URL.startswith("postgresql") and not all([
    os.getenv("STORAGE_ACCOUNT"),
    os.getenv("STORAGE_KEY"),
    os.getenv("STORAGE_SECRET"),
    _R2_BUCKET,
]):
    raise RuntimeError(
        "Producción requiere almacenamiento R2 configurado. "
        "Faltan una o más variables: STORAGE_ACCOUNT, STORAGE_KEY, STORAGE_SECRET, STORAGE_BUCKET"
    )

def _get_s3():
    global _s3, _s3_error
    if _s3 is not None:
        return _s3
    account_id = os.getenv("STORAGE_ACCOUNT", "")
    access_key = os.getenv("STORAGE_KEY", "")
    secret_key = os.getenv("STORAGE_SECRET", "")
    if account_id and access_key and secret_key and _R2_BUCKET:
        try:
            import boto3  # optional dependency; install boto3 to enable R2 storage
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
    """Sube archivo a R2 (con reintentos) o disco local como fallback."""
    import time as _t
    s3 = _get_s3()
    if s3:
        last_err = None
        for intento in range(3):
            try:
                s3.put_object(Bucket=_R2_BUCKET, Key=unique_name, Body=content)
                return
            except Exception as e:
                last_err = e
                if intento < 2:
                    _t.sleep(0.5 * (intento + 1))  # 0.5s, luego 1s
        from logger import logger
        logger.error(f"R2 upload falló tras 3 intentos ({unique_name}): {last_err}")
        raise RuntimeError(f"No se pudo subir el archivo a R2 tras 3 intentos")
    # Fallback: disco local
    dest = os.path.join(UPLOAD_DIR, unique_name)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as f:
        f.write(content)


def _get_presigned_url(unique_name: str, filename: str, expires: int = 300) -> str | None:
    """Genera URL firmada de R2 para descarga directa (evita proxying por el backend)."""
    s3 = _get_s3()
    if not s3:
        return None
    try:
        return s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': _R2_BUCKET,
                'Key': unique_name,
                'ResponseContentDisposition': f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires,
        )
    except Exception:
        return None


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

@router.get("/r2/cliente/{cliente}")
def listar_r2_cliente(
    cliente: str,
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    """Lista todos los archivos en R2 bajo afiliados/{cliente}/. Solo admin."""
    if token.get("rol") != "admin":
        raise HTTPException(403, "Solo admin")
    s3 = _get_s3()
    if not s3:
        raise HTTPException(503, f"R2 no disponible. {_s3_error or ''}")
    import re
    safe_cliente = re.sub(r'[^\w\-]', '_', cliente)
    prefix = f"afiliados/{safe_cliente}/"
    archivos = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=_R2_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            archivos.append({
                "ruta": obj["Key"],
                "tamano": obj["Size"],
                "modificado": obj["LastModified"].isoformat(),
            })
    return {"cliente": cliente, "prefix": prefix, "total": len(archivos), "archivos": archivos}

def _doc_to_dict(doc: models.Documento) -> dict:
    return {
        "id": doc.id, "nombre": doc.nombre, "tipo": doc.tipo,
        "tamano": doc.tamano, "creado": doc.creado.isoformat() if doc.creado else None,
    }


@router.post("")
async def subir_documento(
    file: UploadFile = File(...),
    afiliado_doc: str = Form(''),
    contexto: CONTEXTOS_VALIDOS = Form("afiliado"),
    contexto_id: int = Form(None),
    upload_id: str = Form(None),   # UUID generado por el cliente — permite idempotencia en reintentos
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    # ── Idempotencia: si este upload_id ya existe, retornar el registro existente ──
    # Esto cubre el caso en que el cliente reintenta porque su conexión falló
    # pero el backend ya procesó la petición exitosamente.
    if upload_id:
        existing = db.query(models.Documento).filter_by(upload_id=upload_id).first()
        if existing:
            from logger import logger
            logger.info(f"upload_idempotente: upload_id={upload_id} doc_id={existing.id}")
            return _doc_to_dict(existing)

    ext = (file.filename or '').rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Formato no permitido. Permitidos: {', '.join(sorted(ALLOWED_EXT))}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "Archivo demasiado grande (máx 10 MB)")
    if not _validar_magic(ext, content):
        raise HTTPException(400, f"El contenido del archivo no corresponde a un {ext.upper()} válido")

    import re
    safe_name = re.sub(r'[^\w.\-]', '_', file.filename or 'archivo')
    file_id = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    if afiliado_doc:
        safe_doc = re.sub(r'[^\w\-]', '_', afiliado_doc)
        afil = db.query(models.Afiliado).filter_by(doc=afiliado_doc).first()
        if afil and afil.cliente_txt:
            safe_cliente = re.sub(r'[^\w\-]', '_', afil.cliente_txt)
            unique_name = f"afiliados/{safe_cliente}/{safe_doc}/{file_id}"
        else:
            unique_name = f"afiliados/{safe_doc}/{file_id}"
    elif contexto == "tarea":
        unique_name = f"tareas/{contexto_id}/{file_id}" if contexto_id else f"tareas/{file_id}"
    elif contexto == "aviso":
        unique_name = f"avisos/{contexto_id}/{file_id}" if contexto_id else f"avisos/{file_id}"
    elif contexto in ("novedad_pago", "novedad_afil", "novedad_retiro",
                      "resp_pago", "resp_afil", "resp_retiro"):
        unique_name = f"novedades/{contexto_id}/{file_id}" if contexto_id else f"novedades/{file_id}"
    else:
        unique_name = file_id

    # ── Subir a R2 / disco ──
    _upload_file(unique_name, content)

    # ── Guardar en DB — si falla, limpiar el archivo ya subido ──
    doc = models.Documento(
        upload_id=upload_id or None,
        afiliado_doc=afiliado_doc,
        nombre=file.filename,
        tipo=ext,
        ruta=unique_name,
        tamano=len(content),
        subido_por=token.get("sub", "sistema"),
        contexto=contexto,
        contexto_id=contexto_id,
    )
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception as e:
        db.rollback()
        _delete_file(unique_name)   # Evitar archivo huérfano en R2
        from logger import logger
        logger.error(f"upload_db_fail: {unique_name} — {e}")
        raise HTTPException(500, "Error al registrar el documento. El archivo no fue guardado.")

    return _doc_to_dict(doc)


@router.get("")
def listar_documentos(
    afiliado_doc: str = Query(None),
    contexto: str = Query(None),
    contexto_id: int = Query(None),
    db: Session = Depends(get_db),
    token=Depends(verify_token),
):
    # SEC2-M1: si es cliente, verificar que el afiliado pertenece a su cliente_ref
    if token.get("rol") == "cliente" and afiliado_doc:
        cliente_ref = token.get("cliente_ref", "")
        afil = db.query(models.Afiliado).filter_by(doc=afiliado_doc).first()
        if not afil or afil.cliente_txt != cliente_ref:
            raise HTTPException(403, "Acceso denegado")

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
        if doc.contexto == "aviso":
            # Verificar que el aviso pertenece al cliente
            aviso = db.query(models.AvisoCliente).filter_by(id=doc.contexto_id, cliente_ref=cliente_ref).first()
            if not aviso:
                raise HTTPException(403, "No tienes acceso a este documento")
        elif doc.subido_por == token["sub"]:
            pass  # Permitido: archivos propios del cliente
        elif doc.contexto in _ctx_cliente:
            # SEC2-A4: verificar que el contexto_id pertenece al cliente autenticado
            if doc.contexto in ("novedad_pago", "resp_pago"):
                novedad = db.query(models.NovedadPago).filter_by(
                    id=doc.contexto_id, cliente_ref=cliente_ref
                ).first()
                if not novedad:
                    raise HTTPException(403, "No tienes acceso a este documento")
            elif doc.contexto in ("novedad_afil", "resp_afil",
                                  "novedad_retiro", "resp_retiro"):
                # SolicitudNovedad y SolicitudRetiro usan username_cliente
                sol = None
                if doc.contexto in ("novedad_afil", "resp_afil"):
                    sol = db.query(models.SolicitudNovedad).filter_by(
                        id=doc.contexto_id, cliente_ref=cliente_ref
                    ).first()
                else:
                    sol = db.query(models.SolicitudRetiro).filter_by(
                        id=doc.contexto_id, cliente_ref=cliente_ref
                    ).first()
                if not sol:
                    raise HTTPException(403, "No tienes acceso a este documento")
            elif doc.contexto == "planilla_pago":
                planilla = db.query(models.PlanillaPago).filter_by(
                    id=doc.contexto_id, cliente_ref=cliente_ref
                ).first()
                if not planilla:
                    raise HTTPException(403, "No tienes acceso a este documento")
        elif doc.afiliado_doc:
            afil = db.query(models.Afiliado).filter_by(doc=doc.afiliado_doc, cliente_txt=cliente_ref).first()
            if not afil:
                raise HTTPException(403, "No tienes acceso a este documento")
        else:
            raise HTTPException(403, "No tienes acceso a este documento")

    # R2: URL presignada → descarga directa desde Cloudflare, sin proxying por backend
    presigned = _get_presigned_url(doc.ruta, doc.nombre)
    if presigned:
        return {"url": presigned, "nombre": doc.nombre}

    # Fallback: disco local (dev)
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
