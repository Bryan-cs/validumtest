import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Card, Btn, ConfirmModal, ErrorMsg } from '../components/UI';
import useAuthStore from '../hooks/useAuth';

const MESES = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const anioActual = new Date().getFullYear();
const ANIOS = ['', String(anioActual - 1), String(anioActual), String(anioActual + 1)];


const SORT_OPTS = [
  { value: 'fecha_desc', label: 'Más recientes' },
  { value: 'fecha_asc',  label: 'Más antiguos' },
  { value: 'cliente',    label: 'Cliente A-Z' },
];

const sel = { padding: '8px 12px', border: `1px solid ${C.border}`, borderRadius: 7,
  fontSize: 13, outline: 'none', background: C.surface, color: C.text };

function fileIcon(nombre) {
  const ext = (nombre || '').split('.').pop().toLowerCase();
  if (['pdf'].includes(ext)) return '📕';
  if (['jpg','jpeg','png','gif','webp','bmp'].includes(ext)) return '🖼️';
  if (['xls','xlsx','csv'].includes(ext)) return '📊';
  if (['doc','docx'].includes(ext)) return '📝';
  return '📄';
}

function isImagen(nombre) {
  const ext = (nombre || '').split('.').pop().toLowerCase();
  return ['jpg','jpeg','png','gif','webp'].includes(ext);
}

function fmtTam(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

export default function PlanillasSS() {
  const qc = useQueryClient();
  const rol = useAuthStore(s => s.user?.rol);
  const puedeGestionar = rol === 'admin' || rol === 'empleado';  // adjuntar / quitar archivo

  const [filtroCliente, setFiltroCliente] = useState(() => {
    try { return JSON.parse(localStorage.getItem('bbc_planillas_filtros'))?.filtroCliente ?? ''; } catch { return ''; }
  });
  // Mes/año siempre arrancan en el periodo actual (no se persisten)
  const [filtroMes, setFiltroMes] = useState(MESES[new Date().getMonth() + 1]);
  const [filtroAnio, setFiltroAnio] = useState(String(anioActual));
  const [sortBy, setSortBy] = useState('fecha_desc');

  useEffect(() => {
    try { localStorage.setItem('bbc_planillas_filtros', JSON.stringify({ filtroCliente })); } catch {}
  }, [filtroCliente]);

  const [showModal, setShowModal] = useState(false);
  const [adjuntarPlanillaId, setAdjuntarPlanillaId] = useState(null);
  const [detalleId, setDetalleId] = useState(null);          // planilla_id abierta en el panel
  const [confirmDel, setConfirmDel] = useState(null);        // planilla_id
  const [confirmDelDoc, setConfirmDelDoc] = useState(null);  // { planilla_id, doc_id, nombre }
  const [previewImg, setPreviewImg] = useState(null);        // { url, nombre }

  const { data: planillas = [], isLoading, isError: isErrorPlanillas, refetch: refetchPlanillas } = useQuery({
    queryKey: ['planillas', filtroCliente, filtroMes, filtroAnio],
    queryFn: () => api.get('/planillas', { params: { cliente: filtroCliente, mes: filtroMes, anio: filtroAnio } }).then(r => r.data.items || []),
  });

  const { data: clientes = [] } = useQuery({
    queryKey: ['clientes-lista'],
    queryFn: () => api.get('/clientes').then(r => r.data),
    staleTime: 300_000,
  });

  // Planillas del periodo sin filtro de cliente — para el checklist de faltantes
  const { data: planillasMes = [] } = useQuery({
    queryKey: ['planillas', '', filtroMes, filtroAnio],
    queryFn: () => api.get('/planillas', { params: { cliente: '', mes: filtroMes, anio: filtroAnio } }).then(r => r.data.items || []),
    enabled: !!(filtroMes && filtroAnio),
  });
  const clientesConPlanilla = useMemo(() => new Set(planillasMes.map(p => p.cliente_ref)), [planillasMes]);
  const clientesFaltantes = useMemo(
    () => clientes.filter(c => !clientesConPlanilla.has(c)),
    [clientes, clientesConPlanilla]
  );

  const planillasOrdenadas = useMemo(() => {
    const arr = [...planillas];
    if (sortBy === 'fecha_asc') arr.sort((a, b) => new Date(a.creado) - new Date(b.creado));
    else if (sortBy === 'cliente') arr.sort((a, b) => (a.cliente_ref || '').localeCompare(b.cliente_ref || ''));
    else arr.sort((a, b) => new Date(b.creado) - new Date(a.creado));
    return arr;
  }, [planillas, sortBy]);

  // Planilla abierta en el panel de detalle — se re-deriva tras cada refetch
  const detalle = useMemo(() => planillas.find(p => p.id === detalleId) || null, [planillas, detalleId]);

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await api.delete(`/planillas/${confirmDel}`);
      qc.invalidateQueries({ queryKey: ['planillas'] });
      toast.success('Planilla eliminada');
      if (detalleId === confirmDel) setDetalleId(null);
    } catch { toast.error('Error al eliminar'); }
    setConfirmDel(null);
  };

  const handleDeleteDoc = async () => {
    if (!confirmDelDoc) return;
    try {
      await api.delete(`/planillas/${confirmDelDoc.planilla_id}/archivos/${confirmDelDoc.doc_id}`);
      qc.invalidateQueries({ queryKey: ['planillas'] });
      toast.success('Archivo eliminado');
    } catch { toast.error('Error al eliminar archivo'); }
    setConfirmDelDoc(null);
  };


  const descargarArchivo = async (docId, nombre) => {
    try {
      const res = await api.get(`/documentos/${docId}/descargar`);
      const presigned = res.data?.url;
      if (presigned) {
        const a = document.createElement('a'); a.href = presigned; a.download = nombre; a.click();
      } else {
        const r2 = await api.get(`/documentos/${docId}/descargar`, { responseType: 'blob' });
        const url = URL.createObjectURL(r2.data);
        const a = document.createElement('a'); a.href = url; a.download = nombre; a.click();
        URL.revokeObjectURL(url);
      }
    } catch { toast.error('Error al descargar'); }
  };

  const abrirPreview = async (docId, nombre) => {
    try {
      const res = await api.get(`/documentos/${docId}/descargar`);
      const url = res.data?.url;
      if (url) { setPreviewImg({ url, nombre }); return; }
      const r2 = await api.get(`/documentos/${docId}/descargar`, { responseType: 'blob' });
      const blobUrl = URL.createObjectURL(r2.data);
      setPreviewImg({ url: blobUrl, nombre, isBlob: true });
    } catch { toast.error('Error al previsualizar'); }
  };

  const limpiarFiltros = () => { setFiltroCliente(''); setFiltroMes(''); setFiltroAnio(''); };
  const hayFiltros = filtroCliente || filtroMes || filtroAnio;
  const mesActual = MESES[new Date().getMonth() + 1];
  const enMesActual = filtroMes === mesActual && filtroAnio === String(anioActual);
  const irMesActual = () => { setFiltroMes(mesActual); setFiltroAnio(String(anioActual)); };

  return (
    <div>
      <PageHeader
        title="Planillas de Seguridad Social"
        subtitle="Adjunta y gestiona las planillas de pago SS por cliente"
        action={<Btn onClick={() => setShowModal(true)}>+ Subir planilla</Btn>}
      />

      {/* Filtros + ordenamiento */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>CLIENTE</label>
            <select style={{ ...sel, minWidth: 180 }} value={filtroCliente} onChange={e => setFiltroCliente(e.target.value)}>
              <option value="">Todos los clientes</option>
              {clientes.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>MES</label>
            <select style={sel} value={filtroMes} onChange={e => setFiltroMes(e.target.value)}>
              {MESES.map(m => <option key={m} value={m}>{m || 'Todos'}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>AÑO</label>
            <select style={sel} value={filtroAnio} onChange={e => setFiltroAnio(e.target.value)}>
              {ANIOS.map(a => <option key={a} value={a}>{a || 'Todos'}</option>)}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: C.text2, fontWeight: 600, marginBottom: 4 }}>ORDENAR</label>
            <select style={sel} value={sortBy} onChange={e => setSortBy(e.target.value)}>
              {SORT_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {!enMesActual && (
            <Btn variant="secondary" onClick={irMesActual}>📅 Mes actual</Btn>
          )}
          {hayFiltros && (
            <Btn variant="secondary" onClick={limpiarFiltros}>↺ Limpiar</Btn>
          )}
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: C.text2 }}>
          {isLoading ? 'Cargando...' : <><strong style={{ color: C.primary }}>{planillas.length}</strong> planilla{planillas.length !== 1 ? 's' : ''}</>}
        </div>
      </Card>

      {/* Checklist: clientes sin planilla en el periodo */}
      {filtroMes && filtroAnio && clientes.length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
              {clientesFaltantes.length === 0 ? '✅' : '📋'} {clientes.length - clientesFaltantes.length} de {clientes.length} clientes con planilla en {filtroMes} {filtroAnio}
            </span>
            <div style={{ flex: 1, minWidth: 120, height: 6, background: C.surface2, borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ width: `${clientes.length ? ((clientes.length - clientesFaltantes.length) / clientes.length) * 100 : 0}%`, height: '100%', background: clientesFaltantes.length === 0 ? C.green : C.amber, transition: 'width .3s' }} />
            </div>
          </div>
          {clientesFaltantes.length > 0 && (
            <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
              {clientesFaltantes.map(c => (
                <button key={c} onClick={() => setShowModal({ cliente: c })}
                  title={`Subir planilla de ${c}`}
                  style={{ background: C.amberBg, color: C.amber, border: `1px solid ${C.amber}`, borderRadius: 20, padding: '3px 12px', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                  {c} +
                </button>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Lista */}
      {isErrorPlanillas && <ErrorMsg message="Error al cargar planillas" onRetry={refetchPlanillas} />}
      {!isErrorPlanillas && planillas.length === 0 && !isLoading ? (
        <Card style={{ textAlign: 'center', padding: 40, color: C.text2 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>📋</div>
          No hay planillas para los filtros seleccionados
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 14 }}>
          {planillasOrdenadas.map(p => {
            const archivos = p.archivos || [];
            const totalTam = archivos.reduce((s, a) => s + (a.tamano || 0), 0);
            return (
              <Card key={p.id} style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {/* Header compacto */}
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15, color: C.primary, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.cliente_ref}</div>
                  <span style={{ background: C.blueBg, color: C.blue, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                    {p.mes} {p.anio}
                  </span>
                </div>

                {p.observaciones && (
                  <div style={{ fontSize: 12, color: C.text2, fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={p.observaciones}>
                    {p.observaciones}
                  </div>
                )}

                {/* Resumen de archivos */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: C.surface2, padding: '10px 12px', borderRadius: 8 }}>
                  <span style={{ fontSize: 20 }}>📎</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>
                      {archivos.length} archivo{archivos.length !== 1 ? 's' : ''}
                    </div>
                    <div style={{ fontSize: 11, color: C.text2 }}>{fmtTam(totalTam)}</div>
                  </div>
                </div>

                <Btn variant="secondary" size="sm" onClick={() => setDetalleId(p.id)} style={{ width: '100%' }}>
                  📂 Ver y gestionar archivos
                </Btn>

                {/* Footer */}
                <div style={{ fontSize: 11, color: C.text2, textAlign: 'right' }}>
                  {p.subido_por} · {new Date(p.creado).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal subir nueva planilla */}
      {showModal && (
        <ModalSubirPlanilla
          clientes={clientes}
          clienteInicial={showModal?.cliente || ''}
          mesInicial={filtroMes}
          anioInicial={filtroAnio}
          onClose={() => setShowModal(false)}
          onSuccess={() => { qc.invalidateQueries({ queryKey: ['planillas'] }); setShowModal(false); }}
        />
      )}

      {/* Modal adjuntar archivos a planilla existente */}
      {adjuntarPlanillaId && (
        <ModalAdjuntar
          planillaId={adjuntarPlanillaId}
          onClose={() => setAdjuntarPlanillaId(null)}
          onSuccess={() => { qc.invalidateQueries({ queryKey: ['planillas'] }); setAdjuntarPlanillaId(null); }}
        />
      )}

      {/* Panel de detalle: ver / gestionar archivos de una planilla */}
      {detalle && (
        <ModalDetallePlanilla
          planilla={detalle}
          rol={rol}
          puedeGestionar={puedeGestionar}
          onClose={() => setDetalleId(null)}
          onDescargar={descargarArchivo}
          onPreview={abrirPreview}
          onEliminarArchivo={(a) => setConfirmDelDoc({ planilla_id: detalle.id, doc_id: a.id, nombre: a.nombre })}
          onAdjuntar={() => setAdjuntarPlanillaId(detalle.id)}
          onEliminarPlanilla={() => setConfirmDel(detalle.id)}
        />
      )}

      {/* Preview imagen */}
      {previewImg && (
        <div
          onClick={() => { if (previewImg.isBlob) URL.revokeObjectURL(previewImg.url); setPreviewImg(null); }}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.82)', zIndex: 2000, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div style={{ color: '#fff', fontSize: 13, marginBottom: 10, opacity: .7 }}>{previewImg.nombre} — clic para cerrar</div>
          <img
            src={previewImg.url}
            alt={previewImg.nombre}
            style={{ maxWidth: '90vw', maxHeight: '80vh', borderRadius: 8, boxShadow: '0 8px 40px rgba(0,0,0,.6)', objectFit: 'contain' }}
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}

      <ConfirmModal
        open={!!confirmDel}
        title="Eliminar planilla"
        message="Se eliminará esta planilla y todos sus archivos. No se puede deshacer."
        confirmLabel="Eliminar"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />

      <ConfirmModal
        open={!!confirmDelDoc}
        title="Eliminar archivo"
        message={`¿Eliminar "${confirmDelDoc?.nombre}"? Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        variant="danger"
        onConfirm={handleDeleteDoc}
        onCancel={() => setConfirmDelDoc(null)}
      />
    </div>
  );
}

function ModalDetallePlanilla({ planilla, rol, puedeGestionar, onClose, onDescargar, onPreview, onEliminarArchivo, onAdjuntar, onEliminarPlanilla }) {
  const archivos = planilla.archivos || [];
  const totalTam = archivos.reduce((s, a) => s + (a.tamano || 0), 0);
  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div onClick={e => e.stopPropagation()}
        style={{ background: C.surface, borderRadius: 14, width: 560, maxWidth: '100%', maxHeight: '88vh', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 60px rgba(0,0,0,.3)' }}>
        {/* Cabecera */}
        <div style={{ padding: '20px 24px', borderBottom: `1px solid ${C.border}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
            <div style={{ minWidth: 0 }}>
              <h3 style={{ margin: 0, color: C.primary, fontSize: 17, overflow: 'hidden', textOverflow: 'ellipsis' }}>{planilla.cliente_ref}</h3>
              <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ background: C.blueBg, color: C.blue, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                  {planilla.mes} {planilla.anio}
                </span>
                <span style={{ fontSize: 12, color: C.text2 }}>
                  {archivos.length} archivo{archivos.length !== 1 ? 's' : ''} · {fmtTam(totalTam)}
                </span>
              </div>
            </div>
            <button onClick={onClose} title="Cerrar"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.text2, fontSize: 22, lineHeight: 1, padding: 0, flexShrink: 0 }}>×</button>
          </div>
          {planilla.observaciones && (
            <div style={{ marginTop: 10, fontSize: 13, color: C.text2, fontStyle: 'italic', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {planilla.observaciones}
            </div>
          )}
        </div>

        {/* Lista de archivos (scroll) */}
        <div style={{ padding: '14px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
          {archivos.length === 0 && (
            <div style={{ textAlign: 'center', color: C.text2, fontSize: 13, padding: 20 }}>Sin archivos en esta planilla.</div>
          )}
          {archivos.map(a => (
            <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, background: C.surface2, padding: '8px 10px', borderRadius: 6 }}>
              {isImagen(a.nombre) ? (
                <span style={{ fontSize: 16, cursor: 'pointer', flexShrink: 0 }} onClick={() => onPreview(a.id, a.nombre)} title="Ver imagen">🖼️</span>
              ) : (
                <span style={{ fontSize: 16, flexShrink: 0 }}>{fileIcon(a.nombre)}</span>
              )}
              <span style={{ color: C.blue, cursor: 'pointer', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}
                onClick={() => onDescargar(a.id, a.nombre)} title={a.nombre}>
                {a.nombre}
              </span>
              <span style={{ color: C.text2, fontSize: 11, flexShrink: 0, whiteSpace: 'nowrap' }}>{fmtTam(a.tamano)}</span>
              {puedeGestionar && (
                <button onClick={() => onEliminarArchivo(a)} title="Eliminar archivo"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.red, fontSize: 17, fontWeight: 700, padding: '0 4px', lineHeight: 1, flexShrink: 0 }}>×</button>
              )}
            </div>
          ))}
        </div>

        {/* Pie con acciones */}
        <div style={{ padding: '16px 24px', borderTop: `1px solid ${C.border}`, display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            {puedeGestionar && <Btn size="sm" onClick={onAdjuntar}>+ Agregar archivos</Btn>}
            {rol === 'admin' && <Btn variant="danger" size="sm" onClick={onEliminarPlanilla}>Eliminar planilla</Btn>}
          </div>
          <Btn variant="secondary" size="sm" onClick={onClose}>Cerrar</Btn>
        </div>
      </div>
    </div>
  );
}

function ModalSubirPlanilla({ clientes, clienteInicial = '', mesInicial = '', anioInicial = '', onClose, onSuccess }) {
  const [cliente, setCliente] = useState(clienteInicial);
  const [mes, setMes] = useState(mesInicial || MESES[new Date().getMonth() + 1] || 'Enero');
  const [anio, setAnio] = useState(anioInicial || String(anioActual));
  const [obs, setObs] = useState('');
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);
  const fileRef = useRef(null);

  const handleSubmit = async () => {
    if (subiendo) return;
    if (!cliente) { toast.error('Selecciona un cliente'); return; }
    if (archivos.length === 0) { toast.error('Adjunta al menos un archivo'); return; }
    setSubiendo(true);
    try {
      const fd = new FormData();
      fd.append('cliente_ref', cliente);
      fd.append('mes', mes);
      fd.append('anio', anio);
      fd.append('observaciones', obs);
      archivos.forEach(f => fd.append('files', f));
      const res = await api.post('/planillas', fd);
      const { archivos: guardados = [], omitidos = [], reutilizada = false } = res.data;
      if (omitidos.length === 0) {
        toast.success(reutilizada
          ? `${guardados.length} archivo${guardados.length !== 1 ? 's' : ''} agregado${guardados.length !== 1 ? 's' : ''} a la planilla existente`
          : `Planilla subida — ${guardados.length} archivo${guardados.length !== 1 ? 's' : ''}`);
      } else if (guardados.length === 0) {
        toast.error(`No se guardó ningún archivo. ${omitidos.length} omitido${omitidos.length !== 1 ? 's' : ''}`);
        setSubiendo(false); return;
      } else {
        toast.success(`${guardados.length} archivo${guardados.length !== 1 ? 's' : ''} guardado${guardados.length !== 1 ? 's' : ''}`);
        toast.error(`${omitidos.length} omitido${omitidos.length !== 1 ? 's' : ''}: ${omitidos.map(o => `${o.nombre} (${o.motivo})`).join(' | ')}`, { duration: 8000 });
      }
      onSuccess();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al subir planilla');
    }
    setSubiendo(false);
  };

  const inp = { width: '100%', padding: '8px 10px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, boxSizing: 'border-box', outline: 'none', color: C.text, background: C.surface };
  const lbl = { fontSize: 12, fontWeight: 600, color: C.text2, display: 'block', marginBottom: 4 };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 500, boxShadow: '0 20px 60px rgba(0,0,0,.3)', maxHeight: '90vh', overflowY: 'auto' }}>
        <h3 style={{ margin: '0 0 16px', color: C.primary, fontSize: 16 }}>Subir Planilla de Pago SS</h3>
        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Cliente *</label>
          <select style={inp} value={cliente} onChange={e => setCliente(e.target.value)}>
            <option value="">— Seleccionar cliente —</option>
            {clientes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={lbl}>Mes *</label>
            <select style={inp} value={mes} onChange={e => setMes(e.target.value)}>
              {MESES.filter(Boolean).map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Año *</label>
            <select style={inp} value={anio} onChange={e => setAnio(e.target.value)}>
              {ANIOS.filter(Boolean).map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label style={lbl}>Observaciones (opcional)</label>
          <textarea style={{ ...inp, resize: 'vertical', minHeight: 60 }} value={obs} onChange={e => setObs(e.target.value)} />
        </div>
        <AreaArchivos archivos={archivos} setArchivos={setArchivos} fileRef={fileRef} lbl={lbl} />
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn onClick={handleSubmit} disabled={subiendo || !cliente || archivos.length === 0}>
            {subiendo ? 'Subiendo...' : 'Subir planilla'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ModalAdjuntar({ planillaId, onClose, onSuccess }) {
  const [archivos, setArchivos] = useState([]);
  const [subiendo, setSubiendo] = useState(false);
  const fileRef = useRef(null);
  const lbl = { fontSize: 12, fontWeight: 600, color: C.text2, display: 'block', marginBottom: 4 };

  const handleSubmit = async () => {
    if (subiendo || archivos.length === 0) return;
    setSubiendo(true);
    try {
      const fd = new FormData();
      archivos.forEach(f => fd.append('files', f));
      const res = await api.post(`/planillas/${planillaId}/archivos`, fd);
      const { archivos: guardados = [], omitidos = [] } = res.data;
      if (guardados.length > 0) toast.success(`${guardados.length} archivo${guardados.length !== 1 ? 's' : ''} adjuntado${guardados.length !== 1 ? 's' : ''}`);
      if (omitidos.length > 0) toast.error(`${omitidos.length} omitido${omitidos.length !== 1 ? 's' : ''}`, { duration: 6000 });
      onSuccess();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error al adjuntar');
    }
    setSubiendo(false);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 1500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 460, boxShadow: '0 20px 60px rgba(0,0,0,.3)', maxHeight: '90vh', overflowY: 'auto' }}>
        <h3 style={{ margin: '0 0 16px', color: C.primary, fontSize: 16 }}>Adjuntar archivos a planilla</h3>
        <AreaArchivos archivos={archivos} setArchivos={setArchivos} fileRef={fileRef} lbl={lbl} />
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Btn variant="secondary" onClick={onClose}>Cancelar</Btn>
          <Btn onClick={handleSubmit} disabled={subiendo || archivos.length === 0}>
            {subiendo ? 'Subiendo...' : 'Adjuntar'}
          </Btn>
        </div>
      </div>
    </div>
  );
}

function AreaArchivos({ archivos, setArchivos, fileRef, lbl }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={lbl}>Archivos *</label>
      <label htmlFor="planilla-file-input" style={{
        display: 'block', border: `2px dashed ${C.border}`, borderRadius: 8, padding: 14,
        textAlign: 'center', background: C.surface2, cursor: 'pointer',
      }}>
        <input id="planilla-file-input" ref={fileRef} type="file" multiple
          accept=".pdf,.jpg,.jpeg,.png,.xls,.xlsx"
          style={{ display: 'none' }}
          onChange={e => {
            const nuevos = Array.from(e.target.files || []);
            if (nuevos.length) setArchivos(prev => [...prev, ...nuevos]);
            e.target.value = '';
          }} />
        <div style={{ fontSize: 13, color: C.text2 }}>📂 Clic para seleccionar archivos</div>
        <div style={{ fontSize: 11, color: C.text2, marginTop: 4 }}>PDF, JPG, PNG, XLS · máx. 10 MB c/u</div>
      </label>
      {archivos.length > 0 && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {archivos.map((f, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.text,
              background: C.surface2, padding: '5px 10px', borderRadius: 6,
            }}>
              <span style={{ flexShrink: 0 }}>{fileIcon(f.name)}</span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
              <span style={{ color: C.text2, flexShrink: 0 }}>{fmtTam(f.size)}</span>
              <span style={{ cursor: 'pointer', color: C.red, fontWeight: 700, flexShrink: 0 }}
                onClick={e => { e.preventDefault(); setArchivos(prev => prev.filter((_, j) => j !== i)); }}>×</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
