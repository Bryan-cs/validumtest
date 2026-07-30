import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api, { buildUploadForm } from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { C, ConfirmModal, ErrorMsg } from '../components/UI';
import { hashStr, EMPRESA_PALETTE } from '../utils/colors';

const FONT = "'Plus Jakarta Sans', sans-serif";

const inp = { width: '100%', padding: '9px 12px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, outline: 'none', boxSizing: 'border-box', color: C.text, background: C.surface, fontFamily: FONT };
const lbl = { display: 'block', fontSize: 12, color: C.text2, fontWeight: 500, marginBottom: 4 };

const COLS = [
  { key: 'pendiente',  label: 'Pendiente',   dot: '#d97706', borderColor: '#d97706' },
  { key: 'en_proceso', label: 'En proceso',  dot: '#2563eb', borderColor: '#2563eb' },
  { key: 'completada', label: 'Completadas', dot: '#16a34a', borderColor: '#16a34a' },
];
const COL_FINALIZADA = { key: 'finalizada', label: 'Finalizadas', dot: '#94a3b8', borderColor: '#94a3b8' };
const COL_VENCIDA = { key: 'vencida', label: 'Vencidas', dot: '#dc2626', borderColor: '#fca5a5' };

// Tinte y rótulo de columna derivados del color de la columna, mezclados contra
// los tokens de tema para que funcionen igual en claro y en oscuro.
const headBg = col => `color-mix(in srgb, ${col.dot} 12%, var(--c-surface))`;
const headLabel = col => `color-mix(in srgb, ${col.dot} 45%, var(--c-text))`;

function Btn({ children, onClick, variant = 'primary', size = 'md', disabled = false, style = {} }) {
  const base = { cursor: disabled ? 'not-allowed' : 'pointer', border: 'none', borderRadius: 7, fontWeight: 600, fontSize: size === 'sm' ? 12 : 13, padding: size === 'sm' ? '5px 12px' : '9px 18px', opacity: disabled ? 0.6 : 1, fontFamily: FONT, ...style };
  const variants = {
    primary:   { background: C.primary,  color: '#fff' },
    accent:    { background: C.accent,   color: '#fff' },
    success:   { background: C.green,    color: '#fff' },
    danger:    { background: C.red,      color: '#fff' },
    secondary: { background: C.surface2, color: C.primary, border: `1px solid ${C.border}` },
    blue:      { background: C.blueBg,   color: C.blue,    border: `1px solid ${C.blue}` },
  };
  return <button type="button" style={{ ...base, ...variants[variant] }} onClick={onClick} disabled={disabled}>{children}</button>;
}

function PasswordModal({ open, onClose, onConfirm, cantidad }) {
  const [pwd, setPwd] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (!open) { setPwd(''); setError(''); } }, [open]);
  useEffect(() => {
    if (!open) return;
    const h = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);

  if (!open) return null;

  const handleConfirm = async () => {
    if (!pwd.trim()) { setError('Ingresa tu contraseña'); return; }
    setLoading(true); setError('');
    try { await onConfirm(pwd); }
    catch (e) { setError(e.message || 'Contraseña incorrecta'); }
    finally { setLoading(false); }
  };

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: C.surface, borderRadius: 14, padding: 28, width: 380, boxShadow: '0 25px 80px rgba(0,0,0,.3)', fontFamily: FONT }}>
        <div style={{ textAlign: 'center', marginBottom: 18 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🔐</div>
          <h3 style={{ margin: 0, color: C.primary, fontSize: 16, fontWeight: 700 }}>Confirmar acción</h3>
          <p style={{ margin: '6px 0 0', color: C.text2, fontSize: 13 }}>
            Vas a finalizar <strong>{cantidad}</strong> tarea{cantidad !== 1 ? 's' : ''} completada{cantidad !== 1 ? 's' : ''}.<br />
            Ingresa tu contraseña de administrador para continuar.
          </p>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={lbl}>Contraseña</label>
          <input type="password" style={{ ...inp, borderColor: error ? C.red : C.border }}
            value={pwd} onChange={e => { setPwd(e.target.value); setError(''); }}
            placeholder="Tu contraseña..." autoFocus
            onKeyDown={e => { if (e.key === 'Enter') handleConfirm(); }} />
          {error && <p style={{ margin: '4px 0 0', fontSize: 12, color: C.red }}>{error}</p>}
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Btn variant="secondary" onClick={onClose} disabled={loading}>Cancelar</Btn>
          <Btn variant="primary" onClick={handleConfirm} disabled={loading || !pwd.trim()}>
            {loading ? 'Verificando...' : `Finalizar ${cantidad}`}
          </Btn>
        </div>
      </div>
    </div>
  );
}

export default function Tareas() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const isAdmin = user?.rol === 'admin';
  const canAssign = isAdmin || user?.rol === 'empleado';
  const filterRef = useRef(null);

  const [modalNueva, setModalNueva]           = useState(false);
  const [form, setForm]                       = useState({ titulo: '', descripcion: '', asignado_a: '', fecha_limite: '', privada: false });
  const [expandida, setExpandida]             = useState(null); // { id, mode } | null
  const [notaEstado, setNotaEstado]           = useState({});
  const [txtComent, setTxtComent]             = useState({});
  const [confirm, setConfirm]                 = useState(null);
  const [fechaDesde, setFechaDesde]           = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_tareas_filtros'))?.fechaDesde ?? ''; } catch { return ''; } });
  const [fechaHasta, setFechaHasta]           = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_tareas_filtros'))?.fechaHasta ?? ''; } catch { return ''; } });
  const [seleccionadas, setSeleccionadas]     = useState(new Set());
  const [modalPwd, setModalPwd]               = useState(false);
  const [nuevaFiles, setNuevaFiles]           = useState([]);
  const [completarFiles, setCompletarFiles]   = useState({});
  const [batchMode, setBatchMode]             = useState(false);
  const [showFilterPopover, setShowFilterPopover] = useState(false);
  const [showFinalizadas, setShowFinalizadas] = useState(false);
  const [dragId, setDragId]                   = useState(null);
  const [dragOver, setDragOver]               = useState(null);
  const [filtroAsignado, setFiltroAsignado]   = useState('');
  const [filtroEstado, setFiltroEstado]       = useState('');
  const [expandedDesc, setExpandedDesc]               = useState(new Set());
  const [modalMensajeCompleto, setModalMensajeCompleto] = useState(null);

  useEffect(() => { try { localStorage.setItem('bbc_tareas_filtros', JSON.stringify({ fechaDesde, fechaHasta })); } catch {} }, [fechaDesde, fechaHasta]);
  useEffect(() => { if (!batchMode) setSeleccionadas(new Set()); }, [batchMode]);
  useEffect(() => {
    if (!showFilterPopover) return;
    const h = e => { if (filterRef.current && !filterRef.current.contains(e.target)) setShowFilterPopover(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [showFilterPopover]);

  const { data: tareas = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['tareas'],
    queryFn: () => api.get('/tareas').then(r => r.data.items || []),
    refetchInterval: 60_000,
  });

  const { data: usuarios = [] } = useQuery({
    queryKey: ['tareas-asignables'],
    queryFn: () => api.get('/tareas/asignables').then(r => r.data),
    enabled: canAssign,
    staleTime: 300_000,
  });

  const initialForm = { titulo: '', descripcion: '', asignado_a: '', fecha_limite: '', privada: false };

  const crear = useMutation({
    mutationFn: (payload) => api.post('/tareas', payload),
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: ['tareas'] });
      const prev = qc.getQueryData(['tareas']);
      const optimistic = { id: `temp-${Date.now()}`, ...payload, estado: 'pendiente', creado: new Date().toISOString(), creado_por: user?.username || '', comentarios: [] };
      qc.setQueryData(['tareas'], old => [optimistic, ...(old || [])]);
      return { prev };
    },
    onError: (e, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(['tareas'], ctx.prev);
      const d = e.response?.data?.detail;
      toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error al crear tarea'));
    },
    onSuccess: (res) => {
      const tareaId = res.data?.id;
      setModalNueva(false);
      setForm(initialForm);
      toast.success('Tarea creada');
      if (tareaId && nuevaFiles.length > 0) {
        const uploads = nuevaFiles.map(file => buildUploadForm(file, { afiliado_doc: '', contexto: 'tarea', contexto_id: String(tareaId) }));
        setNuevaFiles([]);
        Promise.all(uploads.map(({ fd }) => api.post('/documentos', fd))).then(() => {
          qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaId] });
        }).catch(err => {
          toast.error('Error al subir adjunto: ' + (err?.response?.data?.detail || err.message));
        });
      } else {
        setNuevaFiles([]);
      }
    },
    onSettled: () => { qc.invalidateQueries({ queryKey: ['tareas'] }); },
  });

  const cambiarEstado = useMutation({
    mutationFn: ({ id, estado, nota }) => api.put(`/tareas/${id}/estado`, { estado, nota }),
    onSuccess: (res) => {
      toast.success('Estado actualizado');
      qc.setQueryData(['tareas'], prev => prev?.map(t => t.id === res.data.id ? res.data : t));
      qc.invalidateQueries({ queryKey: ['notificaciones'] });
    },
    onError: e => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const finalizar = useMutation({
    mutationFn: id => api.put(`/tareas/${id}/finalizar`),
    onSuccess: (res) => {
      toast.success('Tarea finalizada y archivada');
      qc.setQueryData(['tareas'], prev => prev?.map(t => t.id === res.data.id ? res.data : t));
      qc.invalidateQueries({ queryKey: ['notificaciones'] });
    },
    onError: e => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const finalizarLote = useMutation({
    mutationFn: ids => api.put('/tareas/finalizar-lote', { ids }),
    onSuccess: (res) => {
      const { finalizadas, tareas: actualizadas } = res.data;
      toast.success(`${finalizadas} tarea${finalizadas !== 1 ? 's' : ''} finalizada${finalizadas !== 1 ? 's' : ''}`);
      qc.setQueryData(['tareas'], prev => prev?.map(t => { const upd = (actualizadas || []).find(u => u.id === t.id); return upd ? upd : t; }));
      qc.invalidateQueries({ queryKey: ['notificaciones'] });
      setSeleccionadas(new Set());
      setBatchMode(false);
    },
    onError: e => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const eliminarTarea = useMutation({
    mutationFn: id => api.delete(`/tareas/${id}`),
    onSuccess: (_, id) => { toast.success('Tarea eliminada'); qc.setQueryData(['tareas'], prev => prev?.filter(t => t.id !== id)); },
    onError: e => { const d = e.response?.data?.detail; toast.error(d || 'Error al eliminar'); },
  });

  const eliminarFinalizadas = useMutation({
    mutationFn: () => api.post('/tareas/limpiar-historial'),
    onSuccess: (res) => {
      const n = res.data?.eliminadas ?? 0;
      toast.success(`${n} tarea${n !== 1 ? 's' : ''} finalizada${n !== 1 ? 's' : ''} eliminada${n !== 1 ? 's' : ''}`);
      qc.setQueryData(['tareas'], prev => prev?.filter(t => t.estado !== 'finalizada'));
    },
    onError: e => { const d = e.response?.data?.detail; toast.error(typeof d === 'string' ? d : 'Error al eliminar'); },
  });

  const comentar = useMutation({
    mutationFn: ({ id, texto }) => api.post(`/tareas/${id}/comentarios`, { texto }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['tareas'] });
      setTxtComent(prev => ({ ...prev, [id]: '' }));
    },
    onError: () => toast.error('Error al comentar'),
  });

  const toDateStr = iso => { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const esVencida = t => { if (!t.fecha_limite || t.estado === 'completada' || t.estado === 'finalizada' || t.estado === 'en_proceso') return false; return t.fecha_limite < new Date().toISOString().slice(0, 10); };
  const diasRestantes = t => { if (!t.fecha_limite) return null; const hoy = new Date(); hoy.setHours(0, 0, 0, 0); const lim = new Date(t.fecha_limite + 'T00:00:00'); return Math.ceil((lim - hoy) / 86400000); };

  const tasksByCol = {};
  [...COLS, COL_FINALIZADA].forEach(col => {
    tasksByCol[col.key] = tareas.filter(t => {
      if (t.estado !== col.key) return false;
      if (esVencida(t)) return false; // vencidas go to their own column
      const f = toDateStr(t.creado);
      if (fechaDesde && f < fechaDesde) return false;
      if (fechaHasta && f > fechaHasta) return false;
      if (filtroAsignado && t.asignado_a !== filtroAsignado) return false;
      if (filtroEstado && col.key !== filtroEstado) return false;
      return true;
    });
  });
  tasksByCol['vencida'] = tareas.filter(t => {
    if (!esVencida(t)) return false;
    if (filtroEstado && filtroEstado !== 'vencida') return false;
    const f = toDateStr(t.creado);
    if (fechaDesde && f < fechaDesde) return false;
    if (fechaHasta && f > fechaHasta) return false;
    if (filtroAsignado && t.asignado_a !== filtroAsignado) return false;
    return true;
  });

  const counts = {};
  [...COLS, COL_FINALIZADA].forEach(c => { counts[c.key] = tareas.filter(t => t.estado === c.key).length; });
  counts['vencida'] = tasksByCol['vencida'].length;
  const total = tareas.length || 1;
  const allCols = showFinalizadas ? [...COLS, COL_VENCIDA, COL_FINALIZADA] : [...COLS, COL_VENCIDA];

  const completadasList = tasksByCol['completada'] || [];
  const toggleSeleccion = id => setSeleccionadas(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  const seleccionarTodas = () => setSeleccionadas(new Set(completadasList.map(t => t.id)));
  const deseleccionarTodas = () => setSeleccionadas(new Set());
  const todasSeleccionadas = completadasList.length > 0 && completadasList.every(t => seleccionadas.has(t.id));

  const truncar = (txt, max = 30) => txt && txt.length > max ? txt.slice(0, max).trim() + '…' : txt;
  const inicioSemanaStr = (() => {
    const d = new Date();
    const day = d.getDay();
    d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  })();
  const kpiSemanal = (() => {
    const map = {};
    tareas.forEach(t => {
      if (t.estado === 'completada' || t.estado === 'finalizada') {
        const fechaRef = (t.completado_en || t.creado || '').slice(0, 10);
        if (fechaRef >= inicioSemanaStr) { const k = t.asignado_a || 'Sin asignar'; map[k] = (map[k] || 0) + 1; }
      }
    });
    return Object.entries(map).sort((a, b) => b[1] - a[1]);
  })();

  const handleConfirmPassword = async (pwd) => {
    try { await api.post('/auth/verify-password', { password: pwd }); }
    catch (e) { throw new Error(e.response?.status === 401 ? 'Contraseña incorrecta' : (e.response?.data?.detail || 'Error de conexión. Intente nuevamente.')); }
    setModalPwd(false);
    finalizarLote.mutate(Array.from(seleccionadas));
  };

  const handleFinalizar = t => setConfirm({
    title: 'Finalizar tarea',
    message: `¿Finalizar "${t.titulo}"? Quedará archivada en el historial.`,
    confirmLabel: 'Finalizar', variant: 'primary',
    onConfirm: () => { finalizar.mutate(t.id); setConfirm(null); },
  });

  const handleDragStart = (e, id) => { setDragId(id); e.dataTransfer.effectAllowed = 'move'; };
  const handleDragEnd = () => { setDragId(null); setDragOver(null); };
  const handleDragOver = (e, colKey) => { e.preventDefault(); if (dragOver !== colKey) setDragOver(colKey); };
  const handleDrop = (e, colKey) => {
    e.preventDefault(); setDragOver(null);
    if (!dragId || colKey === 'finalizada' || colKey === 'vencida') return;
    const tarea = tareas.find(t => t.id === dragId);
    if (!tarea || tarea.estado === colKey) return;
    cambiarEstado.mutate({ id: dragId, estado: colKey, nota: '' });
    setDragId(null);
  };

  const tareaExpandida = expandida ? tareas.find(t => t.id === expandida.id) : null;

  const ghostBtn = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '7px 14px', borderRadius: 7, border: `1px solid ${C.border}`,
    background: 'transparent', color: C.text2, fontSize: 13, fontWeight: 600,
    cursor: 'pointer', fontFamily: FONT,
  };

  const colActionBtn = {
    padding: '5px 10px', borderRadius: 7, border: `1px solid ${C.border}`,
    background: 'transparent', color: C.text2, fontSize: 12, fontWeight: 600,
    cursor: 'pointer', fontFamily: FONT,
  };

  return (
    <div style={{ fontFamily: FONT }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: 0, color: C.primary, fontSize: 20, fontWeight: 700, letterSpacing: '-.2px' }}>Tareas</h2>
          <p style={{ margin: '3px 0 0', color: C.text2, fontSize: 13 }}>
            {isAdmin ? 'Equipo BBC File' : 'Mis tareas asignadas'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ position: 'relative' }} ref={filterRef}>
            <button type="button" style={{
              ...ghostBtn,
              color: (fechaDesde || fechaHasta) ? C.primary : C.text2,
              borderColor: (fechaDesde || fechaHasta) ? C.primary : C.border,
            }} onClick={() => setShowFilterPopover(v => !v)}>
              📅 Filtrar fecha
              {(fechaDesde || fechaHasta) && (
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.primary, display: 'inline-block' }} />
              )}
            </button>
            {showFilterPopover && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0,
                background: C.surface, borderRadius: 10, border: `1px solid ${C.border}`,
                boxShadow: '0 8px 24px rgba(0,0,0,.12)', padding: 16, zIndex: 50,
                display: 'flex', flexDirection: 'column', gap: 12, minWidth: 240,
              }}>
                <div>
                  <label style={lbl}>Desde</label>
                  <input type="date" style={inp} value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} />
                </div>
                <div>
                  <label style={lbl}>Hasta</label>
                  <input type="date" style={inp} value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} />
                </div>
                {(fechaDesde || fechaHasta) && (
                  <button type="button" onClick={() => { setFechaDesde(''); setFechaHasta(''); }}
                    style={{ ...ghostBtn, fontSize: 12, padding: '5px 12px', justifyContent: 'center', width: '100%' }}>
                    ✕ Limpiar filtros
                  </button>
                )}
              </div>
            )}
          </div>
          <Btn variant="accent" onClick={() => setModalNueva(true)}>+ Nueva tarea</Btn>
        </div>
      </div>

      {/* ── Stats bar ── */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        {COLS.map(col => {
          const active = filtroEstado === col.key;
          return (
            <button key={col.key} type="button"
              onClick={() => setFiltroEstado(active ? '' : col.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 20,
                background: active ? col.dot : headBg(col),
                color: active ? '#fff' : headLabel(col),
                fontSize: 12, fontWeight: 600,
                border: `1.5px solid ${active ? col.dot : 'transparent'}`,
                cursor: 'pointer', fontFamily: FONT, transition: 'all .15s',
              }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: active ? '#fff' : col.dot, flexShrink: 0, display: 'inline-block' }} />
              {counts[col.key]} {col.label.toLowerCase()}
            </button>
          );
        })}
        {counts.vencida > 0 && (() => {
          const active = filtroEstado === 'vencida';
          return (
            <button type="button"
              onClick={() => setFiltroEstado(active ? '' : 'vencida')}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 20,
                background: active ? COL_VENCIDA.dot : headBg(COL_VENCIDA),
                color: active ? '#fff' : headLabel(COL_VENCIDA),
                fontSize: 12, fontWeight: 700,
                border: `1.5px solid ${active ? COL_VENCIDA.dot : 'transparent'}`,
                cursor: 'pointer', fontFamily: FONT, transition: 'all .15s',
              }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: active ? '#fff' : COL_VENCIDA.dot, flexShrink: 0, display: 'inline-block' }} />
              {counts.vencida} vencida{counts.vencida !== 1 ? 's' : ''}
            </button>
          );
        })()}
        {counts.finalizada > 0 && (() => {
          const active = filtroEstado === 'finalizada';
          return (
            <button type="button"
              onClick={() => { setFiltroEstado(active ? '' : 'finalizada'); if (!active) setShowFinalizadas(true); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 20,
                background: active ? COL_FINALIZADA.dot : headBg(COL_FINALIZADA),
                color: active ? '#fff' : headLabel(COL_FINALIZADA),
                fontSize: 12, fontWeight: 600,
                border: `1.5px solid ${active ? COL_FINALIZADA.dot : 'transparent'}`,
                cursor: 'pointer', fontFamily: FONT, transition: 'all .15s',
              }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: active ? '#fff' : COL_FINALIZADA.dot, flexShrink: 0, display: 'inline-block' }} />
              {counts.finalizada} finalizada{counts.finalizada !== 1 ? 's' : ''}
            </button>
          );
        })()}
        {(filtroEstado || filtroAsignado || fechaDesde || fechaHasta) && (
          <button type="button"
            onClick={() => { setFiltroEstado(''); setFiltroAsignado(''); setFechaDesde(''); setFechaHasta(''); }}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 11px', borderRadius: 20,
              background: '#fef2f2', color: C.red,
              border: `1.5px solid #fca5a5`,
              fontSize: 12, fontWeight: 600,
              cursor: 'pointer', fontFamily: FONT, transition: 'all .15s',
            }}>
            ✕ Limpiar filtros
          </button>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: C.text2, fontWeight: 500 }}>Distribución</span>
            <div style={{ display: 'flex', borderRadius: 4, overflow: 'hidden', height: 4, width: 100, gap: 1 }}>
              {COLS.map(col => counts[col.key] > 0 ? (
                <div key={col.key} style={{ flex: counts[col.key], background: col.dot, minWidth: 2, borderRadius: 2, transition: 'flex .3s' }} />
              ) : null)}
            </div>
          </div>
          <button type="button" onClick={() => setShowFinalizadas(v => !v)} style={{
            ...ghostBtn, fontSize: 11, padding: '4px 10px',
            color: showFinalizadas ? C.primary : C.text2,
            borderColor: showFinalizadas ? C.primary : C.border,
          }}>
            {showFinalizadas ? '▲' : '▼'} Historial{counts.finalizada > 0 ? ` (${counts.finalizada})` : ''}
          </button>
        </div>
      </div>

      {/* ── Filtro empleados (solo admin) ── */}
      {isAdmin && usuarios.filter(u => u.activo).length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: C.text2, fontWeight: 600, marginRight: 2 }}>👤</span>
          <button type="button"
            onClick={() => setFiltroAsignado('')}
            style={{
              padding: '4px 12px', borderRadius: 20, border: `1.5px solid ${!filtroAsignado ? C.primary : C.border}`,
              background: !filtroAsignado ? `${C.primary}18` : C.surface2,
              color: !filtroAsignado ? C.primary : C.text2,
              fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: FONT,
            }}>
            Todos
          </button>
          {usuarios.filter(u => u.activo && (u.rol === 'admin' || u.rol === 'empleado')).map(u => {
            const selected = filtroAsignado === u.username;
            const words = (u.nombre || u.username).trim().split(/\s+/);
            const initials = words.length >= 2 ? (words[0][0] + words[1][0]).toUpperCase() : words[0].slice(0, 2).toUpperCase();
            const pal = EMPRESA_PALETTE[hashStr(u.username) % EMPRESA_PALETTE.length];
            return (
              <button key={u.id} type="button"
                onClick={() => setFiltroAsignado(selected ? '' : u.username)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '4px 10px 4px 5px', borderRadius: 20,
                  border: `1.5px solid ${selected ? C.primary : C.border}`,
                  background: selected ? `${C.primary}18` : C.surface2,
                  cursor: 'pointer', fontFamily: FONT,
                }}>
                <span style={{ width: 20, height: 20, borderRadius: '50%', background: pal.bg, color: pal.color, fontSize: 9, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{initials}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: selected ? C.primary : C.text }}>{words[0]}</span>
              </button>
            );
          })}
        </div>
      )}


      {/* ── KPI semanal ── */}
      {kpiSemanal.length > 0 && (
        <div style={{ marginBottom: 14, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '7px 16px', borderBottom: `1px solid ${C.border}`, background: 'color-mix(in srgb, var(--c-green) 12%, var(--c-surface))' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'color-mix(in srgb, var(--c-green) 45%, var(--c-text))', textTransform: 'uppercase', letterSpacing: '.08em' }}>✦ Completadas esta semana</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap' }}>
            {kpiSemanal.map(([nombre, count], i) => {
              const words = nombre.trim().split(/\s+/);
              const initials = words.length >= 2 ? (words[0][0] + words[1][0]).toUpperCase() : nombre.slice(0, 2).toUpperCase();
              const pal = EMPRESA_PALETTE[hashStr(nombre) % EMPRESA_PALETTE.length];
              const isFirst = i === 0;
              return (
                <div key={nombre} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px', borderRight: `1px solid ${C.border}` }}>
                  <div style={{ width: 36, height: 36, borderRadius: '50%', background: pal.bg, color: pal.color, fontSize: 13, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{initials}</div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: C.text2, lineHeight: 1, marginBottom: 3 }}>{words[0]} {words[1] || ''}</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
                      <span style={{ fontSize: 28, fontWeight: 900, color: C.green, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{count}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: C.green }}>tarea{count !== 1 ? 's' : ''}</span>
                      {isFirst && kpiSemanal.length > 1 && <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 20, background: C.amberBg, color: 'color-mix(in srgb, var(--c-amber) 35%, var(--c-text))', marginLeft: 4 }}>🥇 líder</span>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Board ── */}
      {isError ? (
        <ErrorMsg message="Error al cargar tareas" onRetry={refetch} />
      ) : isLoading ? (
        <div style={{ display: 'flex', gap: 12 }}>
          {COLS.map(col => (
            <div key={col.key} style={{ flex: 1, minWidth: 280 }}>
              <div className="bbc-skeleton" style={{ height: 40, borderRadius: '10px 10px 0 0' }} />
              <div style={{ background: C.surface2, border: `1px solid ${C.border}`, borderTop: `2px solid ${col.borderColor}`, borderRadius: '0 0 10px 10px', padding: '10px 8px' }}>
                {[90, 70, 110].map((h, i) => <div key={i} className="bbc-skeleton" style={{ height: h, borderRadius: 9, marginBottom: 8 }} />)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', overflowX: 'auto', paddingBottom: 8 }}>
          {allCols.map(col => {
            const tasks = tasksByCol[col.key] || [];
            const isCompletada = col.key === 'completada';
            const isFinalizada = col.key === 'finalizada';
            const isVencida = col.key === 'vencida';

            return (
              <div key={col.key} style={{ flex: 1, minWidth: 280, maxWidth: 360, display: 'flex', flexDirection: 'column', flexShrink: 0 }}>

                {/* Column header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: headBg(col), borderRadius: '10px 10px 0 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: col.dot, display: 'inline-block', flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', color: headLabel(col) }}>{col.label}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 10, padding: '1px 7px', background: 'color-mix(in srgb, var(--c-text) 10%, transparent)', color: headLabel(col) }}>{tasks.length}</span>
                  </div>
                  {isAdmin && isFinalizada && tasks.length > 0 && (
                    <button type="button"
                      disabled={eliminarFinalizadas.isPending}
                      onClick={() => setConfirm({
                        title: 'Limpiar historial',
                        message: `¿Eliminar las ${tasks.length} tarea${tasks.length !== 1 ? 's' : ''} finalizada${tasks.length !== 1 ? 's' : ''}? Esta acción no se puede deshacer.`,
                        confirmLabel: 'Eliminar todas',
                        variant: 'danger',
                        onConfirm: () => { eliminarFinalizadas.mutate(); setConfirm(null); },
                      })}
                      style={{ fontSize: 11, padding: '3px 9px', borderRadius: 6, border: `1px solid #fca5a5`, background: '#fff9f9', color: C.red, cursor: 'pointer', fontFamily: FONT, opacity: eliminarFinalizadas.isPending ? 0.6 : 1 }}>
                      🗑️ Limpiar
                    </button>
                  )}
                  {isAdmin && isCompletada && (
                    batchMode ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="checkbox" checked={todasSeleccionadas} onChange={todasSeleccionadas ? deseleccionarTodas : seleccionarTodas}
                          style={{ width: 14, height: 14, cursor: 'pointer', accentColor: C.primary }} title="Seleccionar todas" />
                        {seleccionadas.size > 0 && (
                          <button type="button" onClick={() => setModalPwd(true)}
                            style={{ fontSize: 11, padding: '3px 9px', borderRadius: 6, border: 'none', background: C.primary, color: '#fff', cursor: 'pointer', fontWeight: 700, fontFamily: FONT }}>
                            ⬛ {seleccionadas.size}
                          </button>
                        )}
                        <button type="button" onClick={() => setBatchMode(false)}
                          style={{ fontSize: 11, padding: '3px 9px', borderRadius: 6, border: `1px solid ${C.border}`, background: 'transparent', color: C.text2, cursor: 'pointer', fontFamily: FONT }}>
                          ✕
                        </button>
                      </div>
                    ) : (
                      tasks.length > 0 && (
                        <button type="button" onClick={() => setBatchMode(true)}
                          style={{ fontSize: 11, padding: '3px 9px', borderRadius: 6, border: `1px solid ${C.border}`, background: 'transparent', color: C.text2, cursor: 'pointer', fontFamily: FONT }}>
                          ☑ Seleccionar
                        </button>
                      )
                    )
                  )}
                </div>

                {/* Column body */}
                <div
                  onDragOver={!isFinalizada && !isVencida ? e => handleDragOver(e, col.key) : undefined}
                  onDragLeave={!isFinalizada && !isVencida ? () => setDragOver(null) : undefined}
                  onDrop={!isFinalizada && !isVencida ? e => handleDrop(e, col.key) : undefined}
                  style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 8px 12px', background: dragOver === col.key ? `${col.borderColor}18` : C.surface2, border: `1px solid ${dragOver === col.key ? col.borderColor : C.border}`, borderTop: `2px solid ${col.borderColor}`, borderRadius: '0 0 10px 10px', minHeight: 120, transition: 'background .15s, border-color .15s' }}>

                  {tasks.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '24px 8px', color: C.text2, fontSize: 12 }}>Sin tareas</div>
                  ) : tasks.map(t => {
                    const vencida = esVencida(t);
                    const marcada = seleccionadas.has(t.id);
                    const dias = diasRestantes(t);
                    const urgente = !vencida && dias !== null && dias <= 3;
                    const canAction = isAdmin || t.asignado_a === user?.username;
                    const canDrag = canAction && !isFinalizada && !isVencida;

                    return (
                      <div key={t.id}
                        draggable={canDrag}
                        onDragStart={canDrag ? e => handleDragStart(e, t.id) : undefined}
                        onDragEnd={canDrag ? handleDragEnd : undefined}
                        style={{
                          background: marcada ? C.blueBg : vencida ? C.redBg : C.surface,
                          border: `1px solid ${marcada ? C.blue : vencida ? C.red : C.border}`,
                          borderRadius: 9, overflow: 'hidden',
                          transition: 'box-shadow .15s, border-color .15s, opacity .15s',
                          opacity: dragId === t.id ? 0.45 : 1,
                          cursor: canDrag ? 'grab' : 'default',
                        }}>
                        <div style={{ padding: '12px 13px' }}>

                          {/* Title */}
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 7 }}>
                            {isAdmin && isCompletada && batchMode && (
                              <input type="checkbox" checked={marcada} onChange={() => toggleSeleccion(t.id)}
                                style={{ marginTop: 2, width: 14, height: 14, cursor: 'pointer', accentColor: C.primary, flexShrink: 0 }} />
                            )}
                            <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: C.primary, lineHeight: 1.4 }}>{t.titulo}</span>
                          </div>

                          {/* Badges */}
                          {(t.privada || vencida || urgente) && (
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 7 }}>
                              {t.privada && <span style={{ fontSize: 10, fontWeight: 700, borderRadius: 5, padding: '2px 7px', background: C.surface2, color: C.text, textTransform: 'uppercase', letterSpacing: '.03em' }}>🔒 Privada</span>}
                              {vencida && <span style={{ fontSize: 10, fontWeight: 700, borderRadius: 5, padding: '2px 7px', background: C.redBg, color: 'color-mix(in srgb, var(--c-red) 35%, var(--c-text))', textTransform: 'uppercase', letterSpacing: '.03em' }}>⚠ Vencida</span>}
                              {urgente && <span style={{ fontSize: 10, fontWeight: 700, borderRadius: 5, padding: '2px 7px', background: C.amberBg, color: 'color-mix(in srgb, var(--c-amber) 35%, var(--c-text))', textTransform: 'uppercase', letterSpacing: '.03em' }}>⏰ {dias}d</span>}
                            </div>
                          )}

                          {/* Description */}
                          {t.descripcion && (
                            <div style={{ margin: '0 0 7px' }}>
                              <p style={{ margin: 0, fontSize: 12, color: C.text, lineHeight: 1.45, fontWeight: 700 }}>{truncar(t.descripcion)}</p>
                              {t.descripcion.length > 30 && (
                                <button type="button"
                                  onClick={e => { e.stopPropagation(); setModalMensajeCompleto({ titulo: t.titulo, texto: t.descripcion, asignado: t.asignado_a, fecha: t.fecha_limite, estado: t.estado }); }}
                                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.primary, fontSize: 11, fontWeight: 600, padding: '2px 0', fontFamily: FONT, textDecoration: 'underline', textUnderlineOffset: 2 }}>
                                  Ver completo
                                </button>
                              )}
                            </div>
                          )}

                          {/* Footer */}
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                              <div style={{ width: 26, height: 26, borderRadius: '50%', background: C.accent, color: '#fff', fontSize: 11, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: '0 1px 4px rgba(0,0,0,.15)' }}>
                                {(t.asignado_a || '?')[0].toUpperCase()}
                              </div>
                              <span style={{ fontSize: 12, color: C.text, fontWeight: 700 }}>{t.asignado_a}</span>
                            </div>
                            {t.fecha_limite ? (
                              <span style={{ fontSize: 11, fontWeight: 600, color: vencida ? C.red : urgente ? C.amber : dias === 0 ? C.blue : C.text2, display: 'flex', alignItems: 'center', gap: 3 }}>
                                📅 Vence: {dias === 0 ? 'Hoy' : dias === 1 ? 'Mañana' : t.fecha_limite.slice(5).replace('-', '/')}
                              </span>
                            ) : t.completado_en && isCompletada ? (
                              <span style={{ fontSize: 11, fontWeight: 600, color: C.green }}>
                                ✅ {new Date(t.completado_en).toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit' })}
                              </span>
                            ) : null}
                          </div>

                          {/* Fecha asignación */}
                          <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
                            <span style={{ fontSize: 11, color: C.text2, fontWeight: 500 }}>📌 Asignada</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: C.text, background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 5, padding: '1px 7px' }}>
                              {new Date(t.creado).toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit', year: '2-digit' })}
                            </span>
                          </div>

                          {/* Actions */}
                          <div style={{ display: 'flex', gap: 6, paddingTop: 8, borderTop: `1px solid ${C.border}` }}>
                            {canAction && t.estado === 'pendiente' && (
                              <button type="button" onClick={() => cambiarEstado.mutate({ id: t.id, estado: 'en_proceso', nota: '' })}
                                style={{ ...colActionBtn, flex: 1 }}>▶ Iniciar</button>
                            )}
                            {canAction && t.estado === 'en_proceso' && (
                              <button type="button" onClick={() => setExpandida({ id: t.id, mode: 'completar' })}
                                style={{ ...colActionBtn, flex: 1, color: C.green, borderColor: '#bbf7d0' }}>✓ Completar</button>
                            )}
                            {isAdmin && t.estado === 'completada' && (
                              <button type="button" onClick={() => handleFinalizar(t)}
                                style={{ ...colActionBtn, flex: 1 }}>⬛ Finalizar</button>
                            )}
                            {(t.privada || isAdmin) && (t.estado === 'completada' || t.estado === 'finalizada') && (isAdmin || t.creado_por === user?.username) && (
                              <button type="button" disabled={eliminarTarea.isPending}
                                onClick={() => setConfirm({ title: 'Eliminar tarea', message: `¿Eliminar "${t.titulo}"? Esta acción no se puede deshacer.`, confirmLabel: 'Eliminar', variant: 'danger', onConfirm: () => { eliminarTarea.mutate(t.id); setConfirm(null); } })}
                                style={{ ...colActionBtn, color: C.red }}>🗑️</button>
                            )}
                            {!isFinalizada && (
                              <button type="button" onClick={() => setExpandida({ id: t.id, mode: 'ver' })}
                                style={{ ...colActionBtn, display: 'flex', alignItems: 'center', gap: 4 }}>
                                Ver adjuntos{t.comentarios.length > 0 ? ` · 💬 ${t.comentarios.length}` : ''}
                              </button>
                            )}
                          </div>

                        </div>
                      </div>
                    );
                  })}

                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Modal: Ver / Completar tarea ── */}
      {expandida && tareaExpandida && (
        <div onClick={() => setExpandida(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.35)', backdropFilter: 'blur(3px)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={e => e.stopPropagation()}
            style={{ background: C.surface, borderRadius: 14, width: 520, maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,.18)', border: `1px solid ${C.border}`, fontFamily: FONT }}>

            {/* Modal header */}
            <div style={{ padding: '18px 22px 14px', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, position: 'sticky', top: 0, background: C.surface, zIndex: 1 }}>
              <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: C.primary, lineHeight: 1.3 }}>{tareaExpandida.titulo}</p>
                {tareaExpandida.descripcion && <p style={{ margin: '4px 0 0', fontSize: 13, color: C.text2 }}>{tareaExpandida.descripcion}</p>}
              </div>
              <button type="button" onClick={() => setExpandida(null)}
                style={{ width: 28, height: 28, borderRadius: 7, border: `1px solid ${C.border}`, background: C.surface2, color: C.text2, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                ✕
              </button>
            </div>

            {/* Modal body */}
            <div style={{ padding: '16px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>

              {/* Completar panel */}
              {expandida?.mode === 'completar' && (isAdmin || tareaExpandida.asignado_a === user?.username) && tareaExpandida.estado === 'en_proceso' && (
                <div style={{ background: C.greenBg, borderRadius: 10, padding: 14 }}>
                  <label style={{ ...lbl, color: C.green, marginBottom: 8 }}>Nota de cierre (opcional)</label>
                  <input style={{ ...inp, marginBottom: 10, background: C.surface }}
                    placeholder="Describe qué se realizó..."
                    value={notaEstado[tareaExpandida.id] || ''}
                    onChange={e => setNotaEstado(prev => ({ ...prev, [tareaExpandida.id]: e.target.value }))} />
                  <div style={{ marginBottom: 10 }}>
                    <label style={{ display: 'inline-block', padding: '5px 12px', border: `1px dashed ${C.green}`, borderRadius: 7, cursor: 'pointer', fontSize: 12, color: C.green, fontFamily: FONT }}>
                      📎 {(completarFiles[tareaExpandida.id] || []).length > 0 ? `${completarFiles[tareaExpandida.id].length} archivo(s)` : 'Adjuntar evidencia'}
                      <input type="file" multiple style={{ display: 'none' }} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                        onChange={e => setCompletarFiles(p => ({ ...p, [tareaExpandida.id]: [...(p[tareaExpandida.id] || []), ...Array.from(e.target.files)] }))} />
                    </label>
                    {(completarFiles[tareaExpandida.id] || []).length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                        {(completarFiles[tareaExpandida.id] || []).map((f, i) => (
                          <span key={i} style={{ fontSize: 11, padding: '3px 8px', background: C.surface, borderRadius: 5, color: C.text, border: `1px solid ${C.border}`, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            {f.name}
                            <span style={{ cursor: 'pointer', color: C.red, fontWeight: 700 }}
                              onClick={() => setCompletarFiles(p => ({ ...p, [tareaExpandida.id]: p[tareaExpandida.id].filter((_, j) => j !== i) }))}>×</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <Btn variant="success" size="sm"
                    onClick={async () => {
                      const files = completarFiles[tareaExpandida.id] || [];
                      if (files.length > 0) {
                        try {
                          await Promise.all(files.map(file => { const { fd } = buildUploadForm(file, { afiliado_doc: '', contexto: 'tarea', contexto_id: String(tareaExpandida.id) }); return api.post('/documentos', fd); }));
                        } catch (err) { toast.error('Error al subir archivo: ' + (err?.response?.data?.detail || err.message)); return; }
                        qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaExpandida.id] });
                        setCompletarFiles(p => ({ ...p, [tareaExpandida.id]: [] }));
                      }
                      cambiarEstado.mutate({ id: tareaExpandida.id, estado: 'completada', nota: notaEstado[tareaExpandida.id] || '' });
                      setExpandida(null);
                    }}>
                    ✓ Confirmar completada
                  </Btn>
                </div>
              )}

              {/* Comments list */}
              {tareaExpandida.comentarios.length > 0 && (
                <div>
                  <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: C.text2 }}>Comentarios</p>
                  {tareaExpandida.comentarios.map(c => (
                    <div key={c.id} style={{ background: C.surface2, borderRadius: 8, padding: '9px 12px', marginBottom: 6, border: `1px solid ${C.border}` }}>
                      <span style={{ fontWeight: 600, fontSize: 12, color: C.primary }}>{c.usuario}</span>
                      <span style={{ fontSize: 11, color: C.text2, marginLeft: 8 }}>{new Date(c.creado).toLocaleString('es-CO')}</span>
                      <p style={{ margin: '4px 0 0', fontSize: 13, color: C.text }}>{c.texto}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Adjuntos */}
              <TareaDocumentos tareaId={tareaExpandida.id} />

              {/* Comment input */}
              {tareaExpandida.estado !== 'finalizada' && tareaExpandida.estado !== 'en_proceso' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <input style={{ ...inp, flex: 1 }} placeholder="Agregar comentario..."
                    value={txtComent[tareaExpandida.id] || ''}
                    onChange={e => setTxtComent(prev => ({ ...prev, [tareaExpandida.id]: e.target.value }))}
                    onKeyDown={e => { if (e.key === 'Enter' && txtComent[tareaExpandida.id]?.trim()) comentar.mutate({ id: tareaExpandida.id, texto: txtComent[tareaExpandida.id] }); }} />
                  <Btn size="sm" variant="secondary" disabled={!txtComent[tareaExpandida.id]?.trim()}
                    onClick={() => comentar.mutate({ id: tareaExpandida.id, texto: txtComent[tareaExpandida.id] })}>
                    Enviar
                  </Btn>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Nueva tarea ── */}
      {modalNueva && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.45)', backdropFilter: 'blur(4px)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: C.surface, borderRadius: 14, width: 480, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,.22)', border: `1px solid ${C.border}`, fontFamily: FONT }}>

            {/* Header */}
            <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: C.text }}>Nueva tarea</h3>
              <button type="button" onClick={() => { setModalNueva(false); setNuevaFiles([]); }}
                style={{ width: 28, height: 28, borderRadius: 7, border: `1px solid ${C.border}`, background: C.surface2, color: C.text2, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
            </div>

            {/* Body */}
            <div style={{ padding: '20px 24px' }}>

              {/* Título */}
              <div style={{ marginBottom: 16 }}>
                <label style={lbl}>TÍTULO <span style={{ color: C.red }}>*</span></label>
                <input style={inp} value={form.titulo} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))} placeholder="Ej: Actualizar datos de afiliado" autoFocus />
              </div>

              {/* Descripción */}
              <div style={{ marginBottom: 16 }}>
                <label style={lbl}>DESCRIPCIÓN</label>
                <textarea rows={4} style={{ ...inp, resize: 'vertical' }} value={form.descripcion}
                  onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} placeholder="Detalle de la tarea..." />
              </div>

              {/* Fecha + Visibilidad */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div>
                  <label style={lbl}>FECHA LÍMITE</label>
                  <input type="date" style={inp} value={form.fecha_limite} onChange={e => setForm(f => ({ ...f, fecha_limite: e.target.value }))} />
                </div>
                <div>
                  <label style={lbl}>VISIBILIDAD</label>
                  <div style={{ display: 'flex', border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden' }}>
                    <button type="button"
                      onClick={() => setForm(f => ({ ...f, privada: false }))}
                      style={{ flex: 1, padding: '9px 0', border: 'none', borderRight: `1px solid ${C.border}`, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: FONT, transition: 'background .15s, color .15s',
                        background: !form.privada ? C.primary : C.surface2,
                        color: !form.privada ? '#fff' : C.text2,
                      }}>Pública</button>
                    <button type="button"
                      onClick={() => setForm(f => ({ ...f, privada: true, asignado_a: !canAssign ? user?.username || '' : f.asignado_a }))}
                      style={{ flex: 1, padding: '9px 0', border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: FONT, transition: 'background .15s, color .15s',
                        background: form.privada ? C.primary : C.surface2,
                        color: form.privada ? '#fff' : C.text2,
                      }}>🔒 Privada</button>
                  </div>
                </div>
              </div>

              {/* Asignar a — avatar pills */}
              {!form.privada && canAssign && (
                <div style={{ marginBottom: 16 }}>
                  <label style={lbl}>ASIGNAR A <span style={{ color: C.red }}>*</span></label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {usuarios.filter(u => u.activo && (u.rol === 'admin' || u.rol === 'empleado')).map(u => {
                      const selected = form.asignado_a === u.username;
                      const words = (u.nombre || u.username).trim().split(/\s+/);
                      const initials = words.length >= 2
                        ? (words[0][0] + words[1][0]).toUpperCase()
                        : words[0].slice(0, 2).toUpperCase();
                      const pal = EMPRESA_PALETTE[hashStr(u.username) % EMPRESA_PALETTE.length];
                      return (
                        <button key={u.id} type="button"
                          onClick={() => setForm(f => ({ ...f, asignado_a: f.asignado_a === u.username ? '' : u.username }))}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '5px 10px 5px 5px', borderRadius: 20,
                            border: `1.5px solid ${selected ? C.primary : C.border}`,
                            background: selected ? `${C.primary}18` : C.surface2,
                            cursor: 'pointer', fontFamily: FONT, transition: 'all .15s',
                          }}>
                          <span style={{
                            width: 24, height: 24, borderRadius: '50%',
                            background: pal.bg, color: pal.color,
                            fontSize: 10, fontWeight: 700,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                          }}>{initials}</span>
                          <span style={{ fontSize: 12, fontWeight: 600, color: selected ? C.primary : C.text }}>
                            {words[0]}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              {!form.privada && !canAssign && (
                <div style={{ marginBottom: 16 }}>
                  <label style={lbl}>ASIGNAR A</label>
                  <input style={{ ...inp, background: C.surface2 }} readOnly value={user?.username || ''} />
                </div>
              )}

              {/* Adjuntos */}
              <div>
                <label style={lbl}>ADJUNTOS (OPCIONAL)</label>
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px 14px', border: `1px solid ${C.border}`, borderRadius: 8, cursor: 'pointer', color: C.text2, fontSize: 13, background: C.surface2, fontWeight: 500, fontFamily: FONT }}>
                  📎 {nuevaFiles.length > 0 ? `${nuevaFiles.length} archivo(s) seleccionado(s)` : 'Adjuntar archivos'}
                  <input type="file" multiple style={{ display: 'none' }} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                    onChange={e => setNuevaFiles(prev => [...prev, ...Array.from(e.target.files)])} />
                </label>
                {nuevaFiles.length > 0 && (
                  <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {nuevaFiles.map((f, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px', background: C.blueBg, border: `1px solid ${C.blue}`, borderRadius: 5, fontSize: 11 }}>
                        <span style={{ color: C.blue }}>{f.name}</span>
                        <span style={{ cursor: 'pointer', color: C.red, fontWeight: 700 }} onClick={() => setNuevaFiles(p => p.filter((_, j) => j !== i))}>×</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>

            {/* Footer */}
            <div style={{ padding: '4px 24px 20px', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Btn variant="secondary" onClick={() => { setModalNueva(false); setNuevaFiles([]); }}>Cancelar</Btn>
              <Btn variant="accent"
                disabled={!form.titulo.trim() || (!form.privada && !form.asignado_a && canAssign) || crear.isPending}
                onClick={() => {
                  const payload = { ...form };
                  if (!canAssign || form.privada) payload.asignado_a = user?.username || '';
                  crear.mutate(payload);
                }}>
                {crear.isPending ? 'Creando...' : 'Crear tarea'}
              </Btn>
            </div>

          </div>
        </div>
      )}

      {/* ── Modal ver descripción completa ── */}
      {modalMensajeCompleto && (
        <div
          onClick={() => setModalMensajeCompleto(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1200,
            background: 'rgba(0,0,0,0.35)',
            backdropFilter: 'blur(3px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: C.bg,
              borderRadius: 16,
              boxShadow: '0 20px 60px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.10)',
              width: '100%',
              maxWidth: 520,
              overflow: 'hidden',
              border: `1px solid ${C.border}`,
            }}
          >
            {/* Header */}
            <div style={{
              padding: '18px 22px 14px',
              borderBottom: `1px solid ${C.border}`,
              display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: '0 0 4px', fontSize: 11, fontWeight: 700, color: C.text2, textTransform: 'uppercase', letterSpacing: '.07em' }}>Descripción</p>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: C.text, lineHeight: 1.3, wordBreak: 'break-word' }}>
                  {modalMensajeCompleto.titulo}
                </h3>
              </div>
              <button
                onClick={() => setModalMensajeCompleto(null)}
                style={{
                  background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8,
                  width: 30, height: 30, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: C.text2, fontSize: 16, flexShrink: 0, lineHeight: 1,
                }}
              >×</button>
            </div>

            {/* Body */}
            <div style={{ padding: '18px 22px' }}>
              <p style={{
                margin: 0,
                fontSize: 14,
                color: C.text,
                lineHeight: 1.65,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {modalMensajeCompleto.texto}
              </p>
            </div>

            {/* Footer meta */}
            <div style={{
              padding: '12px 22px',
              borderTop: `1px solid ${C.border}`,
              display: 'flex', gap: 16, flexWrap: 'wrap',
              background: C.surface,
            }}>
              {modalMensajeCompleto.asignado && (
                <span style={{ fontSize: 12, color: C.text2 }}>
                  <span style={{ fontWeight: 600, color: C.text }}>Asignado a:</span> {modalMensajeCompleto.asignado}
                </span>
              )}
              {modalMensajeCompleto.fecha && (
                <span style={{ fontSize: 12, color: C.text2 }}>
                  <span style={{ fontWeight: 600, color: C.text }}>Límite:</span> {modalMensajeCompleto.fecha}
                </span>
              )}
              {modalMensajeCompleto.estado && (
                <span style={{ fontSize: 12, color: C.text2 }}>
                  <span style={{ fontWeight: 600, color: C.text }}>Estado:</span> {modalMensajeCompleto.estado}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Password modal ── */}
      <PasswordModal open={modalPwd} onClose={() => setModalPwd(false)} onConfirm={handleConfirmPassword} cantidad={seleccionadas.size} />

      {/* ── Confirm modal ── */}
      {confirm && (
        <ConfirmModal open={!!confirm} title={confirm.title} message={confirm.message}
          confirmLabel={confirm.confirmLabel} variant={confirm.variant}
          onConfirm={confirm.onConfirm} onCancel={() => setConfirm(null)} />
      )}
    </div>
  );
}

// ─── DOCUMENTOS DE TAREA ────────────────────────────────────────────────────
function TareaDocumentos({ tareaId }) {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const { data: docs = [] } = useQuery({
    queryKey: ['documentos-tarea', tareaId],
    queryFn: () => api.get('/documentos', { params: { contexto: 'tarea', contexto_id: tareaId } }).then(r => r.data),
  });

  const handleUpload = async (files) => {
    if (!files.length || uploading) return;
    setUploading(true);
    try {
      await Promise.all(files.map(file => { const { fd } = buildUploadForm(file, { afiliado_doc: '', contexto: 'tarea', contexto_id: String(tareaId) }); return api.post('/documentos', fd); }));
      qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaId] });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error subiendo archivo');
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (doc) => {
    try {
      const res = await api.get(`/documentos/${doc.id}/descargar`);
      if (res.data?.url) {
        const a = document.createElement('a');
        a.href = res.data.url;
        a.download = res.data.nombre || doc.nombre;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        return;
      }
      const blobRes = await api.get(`/documentos/${doc.id}/descargar`, { responseType: 'blob' });
      const url = URL.createObjectURL(blobRes.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.nombre;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { toast.error('Error descargando archivo'); }
  };

  const [delConfirm, setDelConfirm] = useState({ open: false, id: null });

  const doDelete = async () => {
    const id = delConfirm.id;
    setDelConfirm({ open: false, id: null });
    try {
      await api.delete(`/documentos/${id}`);
      qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaId] });
    } catch { toast.error('Error eliminando documento'); }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: C.text2 }}>📎 Adjuntos {docs.length > 0 ? `(${docs.length})` : ''}</span>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', border: `1px dashed ${C.border}`, borderRadius: 6, cursor: uploading ? 'not-allowed' : 'pointer', fontSize: 11, color: C.text2, fontFamily: FONT, opacity: uploading ? 0.6 : 1 }}>
          {uploading ? 'Subiendo…' : '+ Adjuntar'}
          <input type="file" multiple style={{ display: 'none' }} disabled={uploading}
            accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
            onChange={e => handleUpload(Array.from(e.target.files))} />
        </label>
      </div>
      {docs.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: C.text2, fontStyle: 'italic' }}>Sin archivos adjuntos</p>
      ) : docs.map(d => (
        <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: C.text, background: C.surface2, padding: '5px 10px', borderRadius: 7, marginBottom: 4, border: `1px solid ${C.border}` }}>
          <span style={{ flex: 1, cursor: 'pointer', textDecoration: 'underline', color: C.blue }} onClick={() => handleDownload(d)}>{d.nombre}</span>
          <span style={{ color: C.text2, fontSize: 11 }}>{d.subido_por}</span>
          <span style={{ cursor: 'pointer', color: C.red, fontWeight: 700 }} onClick={() => setDelConfirm({ open: true, id: d.id })}>×</span>
        </div>
      ))}
      <ConfirmModal open={delConfirm.open} title="Eliminar documento"
        message="¿Eliminar este documento? Esta acción no se puede deshacer."
        onConfirm={doDelete} onCancel={() => setDelConfirm({ open: false, id: null })} />
    </div>
  );
}
