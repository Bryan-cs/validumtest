import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { C, ConfirmModal } from '../components/UI';

const inp = { width: '100%', padding: '9px 12px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, outline: 'none', boxSizing: 'border-box', color: C.text, background: C.surface };
const lbl = { display: 'block', fontSize: 12, color: C.text2, fontWeight: 500, marginBottom: 4 };

function Btn({ children, onClick, variant = 'primary', size = 'md', disabled = false, style = {} }) {
  const base = { cursor: disabled ? 'not-allowed' : 'pointer', border: 'none', borderRadius: 7, fontWeight: 600, fontSize: size === 'sm' ? 12 : 13, padding: size === 'sm' ? '5px 12px' : '9px 18px', opacity: disabled ? 0.6 : 1, ...style };
  const variants = {
    primary:   { background: C.primary,  color: '#fff' },
    accent:    { background: C.accent,   color: '#fff' },
    success:   { background: C.green,    color: '#fff' },
    danger:    { background: C.red,      color: '#fff' },
    secondary: { background: C.surface2, color: C.primary, border: `1px solid ${C.border}` },
    blue:      { background: C.blueBg,   color: C.blue,    border: `1px solid ${C.blue}` },
  };
  return <button style={{ ...base, ...variants[variant] }} onClick={onClick} disabled={disabled}>{children}</button>;
}

const ESTADO_CFG = {
  pendiente:  { label: 'Pendiente',  color: '#92400E', bg: '#FEF3C7' },
  en_proceso: { label: 'En proceso', color: C.blue,    bg: C.blueBg  },
  completada: { label: 'Completada', color: C.green,   bg: C.greenBg },
  finalizada: { label: 'Finalizada', color: C.text2,   bg: C.surface2},
};

function EstadoBadge({ estado }) {
  const cfg = ESTADO_CFG[estado] || { label: estado, color: C.text2, bg: C.surface2 };
  return (
    <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 10, padding: '2px 10px', background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap' }}>
      {cfg.label}
    </span>
  );
}

// Modal de confirmación con contraseña
function PasswordModal({ open, onClose, onConfirm, cantidad }) {
  const [pwd, setPwd] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) { setPwd(''); setError(''); }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const h = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);

  if (!open) return null;

  const handleConfirm = async () => {
    if (!pwd.trim()) { setError('Ingresa tu contraseña'); return; }
    setLoading(true);
    setError('');
    try {
      await onConfirm(pwd);
    } catch (e) {
      setError(e.message || 'Contraseña incorrecta');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: C.surface, borderRadius: 14, padding: 28, width: 380, boxShadow: '0 25px 80px rgba(0,0,0,.3)' }}>
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
          <input
            type="password"
            style={{ ...inp, borderColor: error ? C.red : C.border }}
            value={pwd}
            onChange={e => { setPwd(e.target.value); setError(''); }}
            placeholder="Tu contraseña..."
            autoFocus
            onKeyDown={e => { if (e.key === 'Enter') handleConfirm(); }}
          />
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

const TABS = [
  { key: 'pendiente',  label: 'Pendientes'  },
  { key: 'en_proceso', label: 'En proceso'  },
  { key: 'completada', label: 'Completadas' },
  { key: 'finalizada', label: 'Finalizadas' },
];

export default function Tareas() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const isAdmin = user?.rol === 'admin';

  const [tab, setTab]               = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_tareas_filtros'))?.tab ?? 'pendiente'; } catch { return 'pendiente'; } });
  const [modalNueva, setModalNueva] = useState(false);
  const [form, setForm]             = useState({ titulo: '', descripcion: '', asignado_a: '', fecha_limite: '', privada: false });
  const [expandida, setExpandida]   = useState(null);
  const [notaEstado, setNotaEstado] = useState({});
  const [txtComent, setTxtComent]   = useState({});
  const [confirm, setConfirm]       = useState(null);
  const [fechaDesde, setFechaDesde] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_tareas_filtros'))?.fechaDesde ?? ''; } catch { return ''; } });
  const [fechaHasta, setFechaHasta] = useState(() => { try { return JSON.parse(localStorage.getItem('bbc_tareas_filtros'))?.fechaHasta ?? ''; } catch { return ''; } });

  useEffect(() => { try { localStorage.setItem('bbc_tareas_filtros', JSON.stringify({ tab, fechaDesde, fechaHasta })); } catch {} }, [tab, fechaDesde, fechaHasta]);

  // Selección múltiple (solo en tab completada)
  const [seleccionadas, setSeleccionadas] = useState(new Set());
  const [modalPwd, setModalPwd]           = useState(false);

  // Archivos adjuntos al crear tarea
  const [nuevaFiles, setNuevaFiles] = useState([]);
  // Archivos adjuntos al completar tarea (por id de tarea)
  const [completarFiles, setCompletarFiles] = useState({});

  // Limpiar selección al cambiar tab
  useEffect(() => { setSeleccionadas(new Set()); }, [tab]);

  const { data: tareas = [], isLoading } = useQuery({
    queryKey: ['tareas'],
    queryFn: () => api.get('/tareas').then(r => r.data.items || []),
    refetchInterval: 60_000,
  });

  const { data: usuarios = [] } = useQuery({
    queryKey: ['usuarios'],
    queryFn: () => api.get('/usuarios').then(r => r.data),
    enabled: isAdmin,
  });

  const crear = useMutation({
    mutationFn: (payload) => api.post('/tareas', payload),
    onSuccess: (res) => {
      const tareaId = res.data?.id;
      toast.success('Tarea creada');
      qc.setQueryData(['tareas'], prev => [res.data, ...(prev || [])]);
      setModalNueva(false);
      setForm({ titulo: '', descripcion: '', asignado_a: '', fecha_limite: '', privada: false });

      // Subir archivos en background (no bloquea el modal)
      if (tareaId && nuevaFiles.length > 0) {
        const filesToUpload = [...nuevaFiles];
        setNuevaFiles([]);
        Promise.all(filesToUpload.map(file => {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('afiliado_doc', '');
          fd.append('contexto', 'tarea');
          fd.append('contexto_id', String(tareaId));
          return api.post('/documentos', fd);
        })).then(() => {
          qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaId] });
        }).catch(err => {
          toast.error('Error al subir adjunto: ' + (err?.response?.data?.detail || err.message));
        });
      } else {
        setNuevaFiles([]);
      }
    },
    onError: e => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
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
      qc.setQueryData(['tareas'], prev =>
        prev?.map(t => {
          const upd = (actualizadas || []).find(u => u.id === t.id);
          return upd ? upd : t;
        })
      );
      qc.invalidateQueries({ queryKey: ['notificaciones'] });
      setSeleccionadas(new Set());
    },
    onError: e => { const d = e.response?.data?.detail; toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error')); },
  });

  const eliminarTarea = useMutation({
    mutationFn: id => api.delete(`/tareas/${id}`),
    onSuccess: (_, id) => { toast.success('Tarea eliminada'); qc.setQueryData(['tareas'], prev => prev?.filter(t => t.id !== id)); },
    onError: e => { const d = e.response?.data?.detail; toast.error(d || 'Error al eliminar'); },
  });

  const comentar = useMutation({
    mutationFn: ({ id, texto }) => api.post(`/tareas/${id}/comentarios`, { texto }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['tareas'] });
      setTxtComent(prev => ({ ...prev, [id]: '' }));
    },
    onError: () => toast.error('Error al comentar'),
  });

  const toDateStr = iso => {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  const esVencida = t => {
    if (!t.fecha_limite || t.estado === 'completada' || t.estado === 'finalizada') return false;
    return t.fecha_limite < new Date().toISOString().slice(0, 10);
  };

  const filtradas = tareas.filter(t => {
    if (t.estado !== tab) return false;
    const f = toDateStr(t.creado);
    if (fechaDesde && f < fechaDesde) return false;
    if (fechaHasta && f > fechaHasta) return false;
    return true;
  });

  const conteo = {};
  TABS.forEach(x => { conteo[x.key] = tareas.filter(t => t.estado === x.key).length; });

  // Selección
  const toggleSeleccion = id => {
    setSeleccionadas(prev => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };
  const seleccionarTodas = () => setSeleccionadas(new Set(filtradas.map(t => t.id)));
  const deseleccionarTodas = () => setSeleccionadas(new Set());
  const todasSeleccionadas = filtradas.length > 0 && filtradas.every(t => seleccionadas.has(t.id));

  // Verificar contraseña y luego finalizar lote
  const handleConfirmPassword = async (pwd) => {
    try {
      await api.post('/auth/login', { username: user.username, password: pwd });
    } catch (e) {
      if (e.response?.status === 401) {
        throw new Error('Contraseña incorrecta');
      }
      throw new Error(e.response?.data?.detail || 'Error de conexión. Intente nuevamente.');
    }
    setModalPwd(false);
    finalizarLote.mutate(Array.from(seleccionadas));
  };

  const handleFinalizar = t => setConfirm({
    title: 'Finalizar tarea',
    message: `¿Finalizar "${t.titulo}"? Quedará archivada en el historial.`,
    confirmLabel: 'Finalizar',
    variant: 'primary',
    onConfirm: () => { finalizar.mutate(t.id); setConfirm(null); },
  });

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, color: C.primary, fontSize: 22, fontWeight: 700 }}>✅ Tareas</h2>
          <p style={{ margin: '4px 0 0', color: C.text2, fontSize: 13 }}>
            {isAdmin ? 'Gestión y asignación de tareas' : 'Mis tareas asignadas y personales'}
          </p>
        </div>
        <Btn variant="accent" onClick={() => setModalNueva(true)}>+ Nueva tarea</Btn>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, background: C.surface2, borderRadius: 10, padding: 4, border: `1px solid ${C.border}` }}>
        {TABS.map(t => {
          const cfg = ESTADO_CFG[t.key];
          const activo = tab === t.key;
          return (
            <button key={t.key} onClick={() => setTab(t.key)} style={{
              flex: 1, padding: '8px 4px', border: 'none', borderRadius: 7, cursor: 'pointer', fontSize: 13,
              fontWeight: activo ? 700 : 400,
              background: activo ? cfg.bg : 'transparent',
              color: activo ? cfg.color : C.text2,
              transition: 'all .15s',
            }}>
              {t.label}
              {conteo[t.key] > 0 && (
                <span style={{
                  marginLeft: 6, background: activo ? cfg.color : C.border,
                  color: activo ? '#fff' : C.text2,
                  borderRadius: 10, padding: '1px 7px', fontSize: 11, fontWeight: 700,
                }}>
                  {conteo[t.key]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Filtro fechas */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 16, background: C.surface, borderRadius: 10, padding: '12px 16px', border: `1px solid ${C.border}` }}>
        <div>
          <label style={lbl}>Desde</label>
          <input type="date" style={{ ...inp, width: 150 }} value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} />
        </div>
        <div>
          <label style={lbl}>Hasta</label>
          <input type="date" style={{ ...inp, width: 150 }} value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} />
        </div>
        {(fechaDesde || fechaHasta) && (
          <Btn size="sm" variant="secondary" onClick={() => { setFechaDesde(''); setFechaHasta(''); }}>✕ Limpiar</Btn>
        )}
      </div>

      {/* Barra de selección múltiple (solo admin en tab completada) */}
      {isAdmin && tab === 'completada' && filtradas.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
          background: seleccionadas.size > 0 ? C.blueBg : C.surface2,
          border: `1px solid ${seleccionadas.size > 0 ? C.blue : C.border}`,
          borderRadius: 9, padding: '10px 14px', transition: 'all .2s',
        }}>
          <input type="checkbox" checked={todasSeleccionadas} onChange={todasSeleccionadas ? deseleccionarTodas : seleccionarTodas}
            style={{ width: 16, height: 16, cursor: 'pointer', accentColor: C.primary }} />
          <span style={{ fontSize: 13, color: C.text2, flex: 1 }}>
            {seleccionadas.size === 0
              ? 'Seleccionar todas'
              : <><strong style={{ color: C.blue }}>{seleccionadas.size}</strong> tarea{seleccionadas.size !== 1 ? 's' : ''} seleccionada{seleccionadas.size !== 1 ? 's' : ''}</>
            }
          </span>
          {seleccionadas.size > 0 && (
            <>
              <Btn size="sm" variant="secondary" onClick={deseleccionarTodas}>Deseleccionar</Btn>
              <Btn size="sm" variant="primary" onClick={() => setModalPwd(true)}>
                ⬛ Finalizar {seleccionadas.size} seleccionada{seleccionadas.size !== 1 ? 's' : ''}
              </Btn>
            </>
          )}
        </div>
      )}

      {/* Lista */}
      {isLoading ? (
        <p style={{ color: C.text2 }}>Cargando...</p>
      ) : filtradas.length === 0 ? (
        <div style={{ background: C.surface, borderRadius: 10, padding: 32, textAlign: 'center', border: `1px solid ${C.border}` }}>
          <p style={{ color: C.text2, fontSize: 14, margin: 0 }}>
            No hay tareas {TABS.find(x => x.key === tab)?.label.toLowerCase()}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtradas.map(t => {
            const vencida = esVencida(t);
            const abierta = expandida === t.id;
            const marcada = seleccionadas.has(t.id);
            return (
              <div key={t.id} style={{
                background: marcada ? C.blueBg : C.surface,
                borderRadius: 10,
                border: `1px solid ${marcada ? C.blue : vencida ? C.red : C.border}`,
                overflow: 'hidden',
                transition: 'border-color .15s, background .15s',
              }}>
                {/* Cabecera */}
                <div style={{ padding: '14px 18px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  {/* Checkbox (solo admin en tab completada) */}
                  {isAdmin && tab === 'completada' && (
                    <input type="checkbox" checked={marcada} onChange={() => toggleSeleccion(t.id)}
                      style={{ marginTop: 2, width: 16, height: 16, cursor: 'pointer', accentColor: C.primary, flexShrink: 0 }} />
                  )}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: 14, color: C.text }}>{t.titulo}</span>
                      <EstadoBadge estado={t.estado} />
                      {t.privada && (
                        <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 10, padding: '2px 10px', background: C.amberBg, color: C.amber }}>🔒 Privada</span>
                      )}
                      {vencida && (
                        <span style={{ fontSize: 11, fontWeight: 600, borderRadius: 10, padding: '2px 10px', background: C.redBg, color: C.red }}>¡Vencida!</span>
                      )}
                    </div>
                    {t.descripcion && <p style={{ margin: '5px 0 0', fontSize: 13, color: C.text2 }}>{t.descripcion}</p>}
                    <div style={{ marginTop: 6, fontSize: 11, color: C.text2, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      <span>👤 {isAdmin ? 'Asignado a' : 'Creado por'}: <strong>{isAdmin ? t.asignado_a : t.creado_por}</strong></span>
                      {t.fecha_limite && (
                        <span style={{ color: vencida ? C.red : C.text2 }}>📅 Límite: <strong>{t.fecha_limite}</strong></span>
                      )}
                      <span>🗓 Creado: {new Date(t.creado).toLocaleDateString('es-CO')}</span>
                      {t.completado_en && <span>✅ Completada: {new Date(t.completado_en).toLocaleDateString('es-CO')}</span>}
                      {t.finalizado_en && <span>⬛ Finalizada: {new Date(t.finalizado_en).toLocaleDateString('es-CO')} por <strong>{t.finalizado_por}</strong></span>}
                    </div>
                  </div>

                  {/* Botones */}
                  <div style={{ display: 'flex', gap: 6, flexShrink: 0, flexWrap: 'wrap', alignItems: 'center' }}>
                    {t.asignado_a === user?.username && t.estado === 'pendiente' && (
                      <Btn size="sm" variant="blue" onClick={() => cambiarEstado.mutate({ id: t.id, estado: 'en_proceso', nota: '' })}>
                        ▶ Iniciar
                      </Btn>
                    )}
                    {t.asignado_a === user?.username && t.estado === 'en_proceso' && (
                      <Btn size="sm" variant="success" onClick={() => setExpandida(abierta ? null : t.id)}>
                        ✓ Completar
                      </Btn>
                    )}
                    {isAdmin && t.estado === 'completada' && (
                      <Btn size="sm" variant="primary" onClick={() => handleFinalizar(t)}>
                        ⬛ Finalizar
                      </Btn>
                    )}
                    {(t.privada || isAdmin) && (t.estado === 'completada' || t.estado === 'finalizada') && (isAdmin || t.creado_por === user?.username) && (
                      <Btn size="sm" variant="danger" disabled={eliminarTarea.isPending}
                        onClick={() => setConfirm({
                          title: 'Eliminar tarea',
                          message: `¿Eliminar "${t.titulo}"? Esta acción no se puede deshacer.`,
                          confirmLabel: 'Eliminar', variant: 'danger',
                          onConfirm: () => { eliminarTarea.mutate(t.id); setConfirm(null); },
                        })}>
                        🗑️
                      </Btn>
                    )}
                    <Btn size="sm" variant="secondary" onClick={() => setExpandida(abierta ? null : t.id)}>
                      {abierta ? 'Cerrar' : `💬 ${t.comentarios.length}`}
                    </Btn>
                  </div>
                </div>

                {/* Panel expandido */}
                {abierta && (
                  <div style={{ borderTop: `1px solid ${C.border}`, padding: '14px 18px', background: C.surface2 }}>
                    {t.asignado_a === user?.username && t.estado === 'en_proceso' && (
                      <div style={{ background: C.greenBg, borderRadius: 8, padding: 12, marginBottom: 12 }}>
                        <label style={{ ...lbl, color: C.green }}>Nota de cierre (opcional)</label>
                        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                          <input style={{ ...inp, flex: 1 }} placeholder="Describe qué se realizó..."
                            value={notaEstado[t.id] || ''}
                            onChange={e => setNotaEstado(prev => ({ ...prev, [t.id]: e.target.value }))} />
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <label style={{ display:'inline-block',padding:'5px 10px',border:`1px dashed ${C.green}`,
                            borderRadius:6,cursor:'pointer',fontSize:11,color:C.green }}>
                            📎 {(completarFiles[t.id]||[]).length > 0 ? `${completarFiles[t.id].length} archivo(s)` : 'Adjuntar evidencia'}
                            <input type="file" multiple style={{ display:'none' }}
                              accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                              onChange={e => setCompletarFiles(p=>({...p,[t.id]:[...(p[t.id]||[]),...Array.from(e.target.files)]}))} />
                          </label>
                          {(completarFiles[t.id]||[]).length > 0 && (
                            <div style={{ display:'inline-flex',flexWrap:'wrap',gap:4,marginLeft:8 }}>
                              {(completarFiles[t.id]||[]).map((f,i)=>(
                                <span key={i} style={{ fontSize:10,padding:'2px 6px',background:C.surface,
                                  borderRadius:4,color:C.text,border:`1px solid ${C.border}` }}>
                                  {f.name}
                                  <span style={{ cursor:'pointer',color:C.red,marginLeft:4,fontWeight:700 }}
                                    onClick={()=>setCompletarFiles(p=>({...p,[t.id]:p[t.id].filter((_,j)=>j!==i)}))}>×</span>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <Btn variant="success" size="sm"
                          onClick={async () => {
                            const files = completarFiles[t.id] || [];
                            if (files.length > 0) {
                              try {
                                for (const file of files) {
                                  const fd = new FormData();
                                  fd.append('file', file);
                                  fd.append('afiliado_doc', '');
                                  fd.append('contexto', 'tarea');
                                  fd.append('contexto_id', String(t.id));
                                  await api.post('/documentos', fd);
                                }
                              } catch(err) {
                                toast.error('Error al subir archivo: ' + (err?.response?.data?.detail || err.message));
                                return;
                              }
                              qc.invalidateQueries({ queryKey: ['documentos-tarea', t.id] });
                              setCompletarFiles(p => ({ ...p, [t.id]: [] }));
                            }
                            cambiarEstado.mutate({ id: t.id, estado: 'completada', nota: notaEstado[t.id] || '' });
                            setExpandida(null);
                          }}>
                          ✓ Confirmar completada
                        </Btn>
                      </div>
                    )}

                    {t.comentarios.length > 0 && (
                      <div style={{ marginBottom: 12 }}>
                        <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: C.text2 }}>Comentarios:</p>
                        {t.comentarios.map(c => (
                          <div key={c.id} style={{ background: C.surface, borderRadius: 7, padding: '8px 12px', marginBottom: 6, border: `1px solid ${C.border}` }}>
                            <span style={{ fontWeight: 600, fontSize: 12, color: C.primary }}>{c.usuario}</span>
                            <span style={{ fontSize: 11, color: C.text2, marginLeft: 8 }}>{new Date(c.creado).toLocaleString('es-CO')}</span>
                            <p style={{ margin: '4px 0 0', fontSize: 13, color: C.text }}>{c.texto}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Documentos adjuntos de la tarea */}
                    <TareaDocumentos tareaId={t.id} />

                    {t.estado !== 'finalizada' && (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input style={{ ...inp, flex: 1 }} placeholder="Agregar comentario..."
                          value={txtComent[t.id] || ''}
                          onChange={e => setTxtComent(prev => ({ ...prev, [t.id]: e.target.value }))}
                          onKeyDown={e => { if (e.key === 'Enter' && txtComent[t.id]?.trim()) comentar.mutate({ id: t.id, texto: txtComent[t.id] }); }} />
                        <Btn size="sm" variant="secondary" disabled={!txtComent[t.id]?.trim()}
                          onClick={() => comentar.mutate({ id: t.id, texto: txtComent[t.id] })}>
                          Enviar
                        </Btn>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Modal nueva tarea */}
      {modalNueva && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: C.surface, borderRadius: 14, padding: 28, width: 460, boxShadow: '0 20px 60px rgba(0,0,0,.25)', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 style={{ margin: '0 0 18px', color: C.primary }}>Nueva tarea</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Título *</label>
              <input style={inp} value={form.titulo} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))} placeholder="Ej: Actualizar datos de afiliado" />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Descripción</label>
              <textarea rows={3} style={{ ...inp, resize: 'vertical' }} value={form.descripcion}
                onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} placeholder="Detalle de la tarea..." />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display:'flex',alignItems:'center',gap:8,cursor:'pointer',fontSize:13,color:C.text }}>
                <input type="checkbox" checked={form.privada}
                  onChange={e=>setForm(f=>({...f, privada:e.target.checked, asignado_a: e.target.checked && !isAdmin ? user?.username||'' : f.asignado_a}))}
                  style={{ width:16,height:16,accentColor:C.primary }} />
                🔒 Tarea privada (solo visible para mí)
              </label>
            </div>
            {!form.privada && isAdmin && (
              <div style={{ marginBottom: 12 }}>
                <label style={lbl}>Asignar a *</label>
                <select style={inp} value={form.asignado_a} onChange={e => setForm(f => ({ ...f, asignado_a: e.target.value }))}>
                  <option value="">— Seleccionar usuario —</option>
                  {usuarios.filter(u => u.activo).map(u => (
                    <option key={u.id} value={u.username}>{u.nombre} ({u.username})</option>
                  ))}
                </select>
              </div>
            )}
            {!form.privada && !isAdmin && (
              <div style={{ marginBottom: 12 }}>
                <label style={lbl}>Asignada a</label>
                <input style={{ ...inp, background:C.surface2 }} readOnly value={user?.username || ''} />
              </div>
            )}
            <div style={{ marginBottom: 18 }}>
              <label style={lbl}>Fecha límite</label>
              <input type="date" style={inp} value={form.fecha_limite} onChange={e => setForm(f => ({ ...f, fecha_limite: e.target.value }))} />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={lbl}>Adjuntar archivos (opcional)</label>
              <label style={{ display:'block',padding:'8px 12px',border:`2px dashed ${C.border}`,
                borderRadius:7,textAlign:'center',cursor:'pointer',color:C.text2,fontSize:12,background:C.surface2 }}>
                📎 {nuevaFiles.length > 0 ? `${nuevaFiles.length} archivo(s) seleccionado(s)` : 'Haz clic para adjuntar'}
                <input type="file" multiple style={{ display:'none' }}
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png"
                  onChange={e => setNuevaFiles(prev => [...prev, ...Array.from(e.target.files)])} />
              </label>
              {nuevaFiles.length > 0 && (
                <div style={{ marginTop:6,display:'flex',flexWrap:'wrap',gap:4 }}>
                  {nuevaFiles.map((f,i) => (
                    <div key={i} style={{ display:'flex',alignItems:'center',gap:4,padding:'3px 8px',
                      background:C.blueBg,border:`1px solid ${C.blue}`,borderRadius:5,fontSize:11 }}>
                      <span style={{ color:C.blue }}>{f.name}</span>
                      <span style={{ cursor:'pointer',color:C.red,fontWeight:700 }}
                        onClick={()=>setNuevaFiles(p=>p.filter((_,j)=>j!==i))}>×</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Btn variant="secondary" onClick={() => { setModalNueva(false); setNuevaFiles([]); }}>Cancelar</Btn>
              <Btn variant="accent"
                disabled={!form.titulo.trim() || (!form.privada && !form.asignado_a && isAdmin) || crear.isPending}
                onClick={() => {
                  const payload = { ...form };
                  if (payload.privada && !isAdmin) payload.asignado_a = user?.username || '';
                  crear.mutate(payload);
                }}>
                {crear.isPending ? 'Creando...' : 'Crear tarea'}
              </Btn>
            </div>
          </div>
        </div>
      )}

      {/* Modal contraseña para finalizar en lote */}
      <PasswordModal
        open={modalPwd}
        onClose={() => setModalPwd(false)}
        onConfirm={handleConfirmPassword}
        cantidad={seleccionadas.size}
      />

      {/* Confirm modal (finalizar individual) */}
      {confirm && (
        <ConfirmModal
          open={!!confirm}
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.confirmLabel}
          variant={confirm.variant}
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
}

// ─── DOCUMENTOS DE TAREA ────────────────────────────────────────────────────
function TareaDocumentos({ tareaId }) {
  const qc = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const { data: docs=[] } = useQuery({
    queryKey: ['documentos-tarea', tareaId],
    queryFn: () => api.get('/documentos', { params: { contexto: 'tarea', contexto_id: tareaId } }).then(r=>r.data),
  });

  const handleUpload = async (files) => {
    if (!files.length) return;
    setUploading(true);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('afiliado_doc', '');
        fd.append('contexto', 'tarea');
        fd.append('contexto_id', String(tareaId));
        await api.post('/documentos', fd);
      }
      qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaId] });
    } catch (e) {
      alert(e.response?.data?.detail || 'Error subiendo archivo');
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (doc) => {
    try {
      const res = await api.get(`/documentos/${doc.id}/descargar`);
      if (res.data?.url) {
        // URL presignada R2 — descarga directa desde Cloudflare
        const a = document.createElement('a');
        a.href = res.data.url;
        a.download = res.data.nombre || doc.nombre;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        return;
      }
      // Fallback local (dev): blob
      const blobRes = await api.get(`/documentos/${doc.id}/descargar`, { responseType: 'blob' });
      const url = URL.createObjectURL(blobRes.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.nombre;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { alert('Error descargando'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar documento?')) return;
    try {
      await api.delete(`/documentos/${id}`);
      qc.invalidateQueries({ queryKey: ['documentos-tarea', tareaId] });
    } catch { alert('Error eliminando'); }
  };

  if (docs.length === 0) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display:'flex',alignItems:'center',gap:8,marginBottom:6 }}>
        <span style={{ fontSize:12,fontWeight:600,color:C.text2 }}>📎 Adjuntos ({docs.length})</span>
      </div>
      {docs.map(d=>(
        <div key={d.id} style={{ display:'flex',alignItems:'center',gap:8,fontSize:12,color:C.text,
          background:C.surface,padding:'4px 10px',borderRadius:6,marginBottom:3,border:`1px solid ${C.border}` }}>
          <span style={{ flex:1,cursor:'pointer',textDecoration:'underline',color:C.blue }} onClick={()=>handleDownload(d)}>
            {d.nombre}
          </span>
          <span style={{ color:C.text2,fontSize:11 }}>{d.subido_por}</span>
          <span style={{ cursor:'pointer',color:C.red,fontWeight:700 }} onClick={()=>handleDelete(d.id)}>×</span>
        </div>
      ))}
    </div>
  );
}
