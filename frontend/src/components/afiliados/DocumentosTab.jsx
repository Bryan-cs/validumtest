import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { buildUploadForm } from '../../utils/api';
import { C, Btn, ConfirmModal } from '../../components/UI';

const tdc = { padding:'10px 12px',fontSize:13,color:C.text,verticalAlign:'middle' };
const PREVIEWABLE = ['pdf','jpg','jpeg','png','gif'];

export default function DocumentosTab({ todos, api, qc, docBusqDoc, setDocBusqDoc, docDocSel, setDocDocSel, uploading, setUploading }) {
  const [docConfirm, setDocConfirm] = React.useState({ open: false, title: '', message: '', onConfirm: null });
  // { doc, url, esBlob } — esBlob=true cuando la URL es un objectURL local (dev) y hay que revocarla al cerrar
  const [preview, setPreview] = React.useState(null);
  const [previewLoading, setPreviewLoading] = React.useState(false);
  const sugerencias = docBusqDoc.length >= 2 && !docDocSel
    ? todos.filter(a => `${a.nombre} ${a.doc}`.toLowerCase().includes(docBusqDoc.toLowerCase())).slice(0,8)
    : [];

  const { data: docs=[], isLoading } = useQuery({
    queryKey: ['documentos', docDocSel],
    queryFn: () => api.get('/documentos', { params: { afiliado_doc: docDocSel } }).then(r=>r.data),
    enabled: !!docDocSel,
  });
  const afilSel = todos.find(a=>a.doc===docDocSel);

  const handleUpload = async (files) => {
    if (!docDocSel || !files.length || uploading) return;  // guard doble click/drop
    setUploading(true);
    // Generar upload_id por archivo ANTES de la petición para que los reintentos sean idempotentes
    const uploads = files.map(file => ({
      file,
      ...buildUploadForm(file, { afiliado_doc: docDocSel, contexto: 'afiliado' }),
    }));
    const resultados = await Promise.allSettled(
      uploads.map(({ fd }) => api.post('/documentos', fd))
    );
    await qc.refetchQueries({ queryKey: ['documentos', docDocSel] });
    setUploading(false);
    const errores = resultados
      .map((r, i) => r.status === 'rejected' ? `${files[i].name}: ${r.reason?.response?.data?.detail || 'Error'}` : null)
      .filter(Boolean);
    if (errores.length) toast.error(`Error al subir ${errores.length} archivo(s)`);
  };

  const handleDelete = (id) => {
    setDocConfirm({
      open: true,
      title: 'Eliminar documento',
      message: '¿Eliminar este documento? Esta acción no se puede deshacer.',
      onConfirm: async () => {
        setDocConfirm(s => ({ ...s, open: false }));
        try {
          await api.delete(`/documentos/${id}`);
          qc.invalidateQueries({ queryKey: ['documentos', docDocSel] });
        } catch (e) {
          toast.error(e.response?.data?.detail || 'Error eliminando documento');
        }
      },
    });
  };

  const handleDownload = async (doc) => {
    try {
      const res = await api.get(`/documentos/${doc.id}/descargar`);
      if (res.data?.url) {
        window.open(res.data.url, '_blank');
        return;
      }
      // Fallback local (dev): refetch como blob
      const res2 = await api.get(`/documentos/${doc.id}/descargar`, { responseType: 'blob' });
      const objUrl = URL.createObjectURL(res2.data);
      const a = document.createElement('a');
      a.href = objUrl;
      a.download = doc.nombre;
      a.click();
      URL.revokeObjectURL(objUrl);
    } catch (e) {
      const det = e.response?.data?.detail;
      toast.error(typeof det === 'string' ? det : 'Error descargando archivo');
    }
  };

  const handlePreview = async (doc) => {
    if (previewLoading) return;
    setPreviewLoading(true);
    try {
      const res = await api.get(`/documentos/${doc.id}/descargar`, { params: { inline: true } });
      if (res.data?.url) {
        setPreview({ doc, url: res.data.url, esBlob: false });
        return;
      }
      // Fallback local (dev): blob con content-type real → objectURL
      const res2 = await api.get(`/documentos/${doc.id}/descargar`, { params: { inline: true }, responseType: 'blob' });
      setPreview({ doc, url: URL.createObjectURL(res2.data), esBlob: true });
    } catch (e) {
      const det = e.response?.data?.detail;
      toast.error(typeof det === 'string' ? det : 'Error cargando la vista previa');
    } finally {
      setPreviewLoading(false);
    }
  };

  const cerrarPreview = () => {
    setPreview(p => {
      if (p?.esBlob) URL.revokeObjectURL(p.url);
      return null;
    });
  };

  const fmtSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes/1024).toFixed(1)} KB`;
    return `${(bytes/1048576).toFixed(1)} MB`;
  };

  const iconByType = (tipo) => {
    if (['jpg','jpeg','png','gif'].includes(tipo)) return '🖼️';
    if (tipo === 'pdf') return '📕';
    if (['doc','docx'].includes(tipo)) return '📝';
    if (['xls','xlsx'].includes(tipo)) return '📊';
    return '📄';
  };

  return (
    <div>
      <div style={{ display:'flex',alignItems:'flex-start',gap:12,marginBottom:16,flexWrap:'wrap' }}>
        <div style={{ position:'relative',flex:'0 0 340px' }}>
          <input placeholder="🔍 Buscar afiliado por nombre o documento..."
            value={docBusqDoc}
            onChange={e=>{ setDocBusqDoc(e.target.value); if(!e.target.value) setDocDocSel(''); }}
            style={{ width:'100%',padding:'10px 14px',border:`1px solid ${C.border}`,borderRadius:8,
              fontSize:14,outline:'none',boxSizing:'border-box',background:C.surface,color:C.text }} />
          {sugerencias.length > 0 && (
            <div style={{ position:'absolute',top:'100%',left:0,right:0,background:C.surface,
              border:`1px solid ${C.border}`,borderRadius:8,boxShadow:'0 4px 12px rgba(0,0,0,.1)',
              zIndex:100,maxHeight:200,overflowY:'auto' }}>
              {sugerencias.map(a => (
                <div key={a.id} onClick={()=>{ setDocDocSel(a.doc); setDocBusqDoc(a.nombre); }}
                  style={{ padding:'9px 14px',cursor:'pointer',fontSize:13,borderBottom:`1px solid ${C.border}` }}
                  onMouseEnter={e=>e.currentTarget.style.background=C.surface2}
                  onMouseLeave={e=>e.currentTarget.style.background=''}>
                  <strong>{a.nombre}</strong>
                  <span style={{ marginLeft:8,color:C.text2,fontSize:11 }}>{a.doc} · {a.empresa||''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        {docDocSel && (
          <Btn size="sm" variant="secondary" onClick={()=>{ setDocDocSel(''); setDocBusqDoc(''); }}>✕ Limpiar</Btn>
        )}
      </div>

      {!docDocSel && (
        <div style={{ padding:'40px 20px',textAlign:'center',color:C.text2,fontSize:13 }}>
          📎 Busca un afiliado para ver y gestionar sus documentos
        </div>
      )}

      {docDocSel && afilSel && (
        <>
          <div style={{ background:C.blueBg,border:`1px solid ${C.blue}`,borderRadius:8,
            padding:'10px 16px',marginBottom:14,display:'flex',gap:24,flexWrap:'wrap',fontSize:13 }}>
            <div><strong style={{ color:C.blue }}>{afilSel.nombre}</strong></div>
            <div style={{ color:C.text2 }}>Doc: <strong>{afilSel.doc}</strong></div>
            <div style={{ color:C.text2 }}>Empresa: <strong>{afilSel.empresa||'—'}</strong></div>
          </div>

          {/* Zona de upload */}
          <div style={{ border:`2px dashed ${uploading ? C.text2 : C.border}`,borderRadius:10,padding:'20px',
            textAlign:'center',marginBottom:14,background:C.surface2,
            cursor: uploading ? 'not-allowed' : 'pointer',
            opacity: uploading ? 0.7 : 1, position:'relative' }}
            onClick={()=>{ if (!uploading) document.getElementById('doc-file-input')?.click(); }}
            onDragOver={e=>{ if (uploading) return; e.preventDefault();e.currentTarget.style.borderColor=C.blue;}}
            onDragLeave={e=>{e.currentTarget.style.borderColor=uploading ? C.text2 : C.border;}}
            onDrop={e=>{ if (uploading) return; e.preventDefault();e.currentTarget.style.borderColor=C.border;handleUpload(Array.from(e.dataTransfer.files));}}>
            <input id="doc-file-input" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
              style={{ display:'none' }} disabled={uploading}
              onChange={e=>{ if(!uploading && e.target.files.length) handleUpload(Array.from(e.target.files)); e.target.value=''; }} />
            <div style={{ fontSize:28,marginBottom:6 }}>📂</div>
            <div style={{ fontSize:13,color:C.text2 }}>
              {uploading ? 'Subiendo...' : 'Click o arrastra archivos aquí (PDF, imágenes, Word, Excel — máx 10 MB)'}
            </div>
          </div>

          {/* Lista de documentos */}
          {isLoading && <div style={{ textAlign:'center',color:C.text2,padding:20 }}>Cargando...</div>}
          {!isLoading && docs.length === 0 && (
            <div style={{ textAlign:'center',color:C.text2,padding:20,fontSize:13 }}>
              Sin documentos. Sube el primer archivo arriba.
            </div>
          )}
          {docs.length > 0 && (
            <div style={{ overflowX:'auto',borderRadius:10,border:`1px solid ${C.border}` }}>
              <table style={{ width:'100%',borderCollapse:'collapse',background:C.surface }}>
                <thead>
                  <tr style={{ background:C.surface2 }}>
                    {['','Nombre','Tipo','Tamaño','Subido por','Fecha','Acciones'].map(h=>(
                      <th key={h} style={{ padding:'10px 12px',textAlign:'left',fontSize:11,fontWeight:600,
                        color:C.text2,borderBottom:`1px solid ${C.border}`,whiteSpace:'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {docs.map(d=>(
                    <tr key={d.id} style={{ borderBottom:`1px solid ${C.border}` }}>
                      <td style={{ ...tdc,fontSize:20,width:30,textAlign:'center' }}>{iconByType(d.tipo)}</td>
                      <td style={{ ...tdc,fontWeight:500 }}>{d.nombre}</td>
                      <td style={{ ...tdc,fontSize:11,textTransform:'uppercase' }}>{d.tipo}</td>
                      <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{fmtSize(d.tamano)}</td>
                      <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{d.subido_por||'—'}</td>
                      <td style={{ ...tdc,fontSize:12,color:C.text2 }}>{d.creado ? new Date(d.creado).toLocaleDateString('es-CO') : '—'}</td>
                      <td style={tdc}>
                        <div style={{ display:'flex',gap:5 }}>
                          {PREVIEWABLE.includes((d.tipo||'').toLowerCase()) && (
                            <Btn size="sm" variant="secondary" disabled={previewLoading}
                              onClick={()=>handlePreview(d)}>👁 Vista previa</Btn>
                          )}
                          <Btn size="sm" variant="secondary" onClick={()=>handleDownload(d)}>⬇ Descargar</Btn>
                          <Btn size="sm" variant="danger" onClick={()=>handleDelete(d.id)}>×</Btn>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <ConfirmModal
        open={docConfirm.open}
        title={docConfirm.title}
        message={docConfirm.message}
        onConfirm={docConfirm.onConfirm}
        onCancel={() => setDocConfirm(s => ({ ...s, open: false }))}
      />

      {/* Modal vista previa — overlay nativo (patrón del proyecto, sin Radix) */}
      {preview && (
        <div onClick={cerrarPreview}
          style={{ position:'fixed',inset:0,background:'rgba(11,27,43,0.72)',zIndex:1000,
            display:'flex',alignItems:'center',justifyContent:'center',padding:20 }}>
          <div onClick={e=>e.stopPropagation()}
            style={{ background:C.surface,borderRadius:12,width:'min(960px, 96vw)',height:'min(85vh, 900px)',
              display:'flex',flexDirection:'column',overflow:'hidden',boxShadow:'0 20px 60px rgba(0,0,0,.35)' }}>
            <div style={{ display:'flex',alignItems:'center',gap:10,padding:'12px 16px',
              borderBottom:`1px solid ${C.border}` }}>
              <span style={{ fontSize:18 }}>{iconByType(preview.doc.tipo)}</span>
              <div style={{ flex:1,minWidth:0,fontWeight:600,fontSize:14,color:C.text,
                overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap' }}>
                {preview.doc.nombre}
              </div>
              <Btn size="sm" variant="secondary" onClick={()=>handleDownload(preview.doc)}>⬇ Descargar</Btn>
              <Btn size="sm" variant="danger" onClick={cerrarPreview}>✕ Cerrar</Btn>
            </div>
            <div style={{ flex:1,background:C.surface2,display:'flex',
              alignItems:'center',justifyContent:'center',overflow:'auto' }}>
              {preview.doc.tipo === 'pdf'
                ? <iframe src={preview.url} title={preview.doc.nombre}
                    style={{ width:'100%',height:'100%',border:'none' }} />
                : <img src={preview.url} alt={preview.doc.nombre}
                    style={{ maxWidth:'100%',maxHeight:'100%',objectFit:'contain' }} />}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
