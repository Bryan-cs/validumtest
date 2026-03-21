import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

const C = {
  primary: '#0D3B6E', accent: '#E89B2A', green: '#16A34A', greenBg: '#DCFCE7',
  red: '#DC2626', redBg: '#FEE2E2', blue: '#2563EB', blueBg: '#DBEAFE',
  border: '#E2E8F0', surface2: '#F8FAFC', text2: '#64748B',
};
const inp = { width: '100%', padding: '9px 12px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, outline: 'none', boxSizing: 'border-box', color: '#1E293B' };
const lbl = { display: 'block', fontSize: 12, color: C.text2, fontWeight: 500, marginBottom: 4 };

function Btn({ children, onClick, variant = 'primary', size = 'md', disabled = false, style = {} }) {
  const base = { cursor: disabled ? 'not-allowed' : 'pointer', border: 'none', borderRadius: 7, fontWeight: 600, fontSize: size === 'sm' ? 12 : 13, padding: size === 'sm' ? '5px 12px' : '9px 18px', opacity: disabled ? 0.6 : 1, ...style };
  const variants = {
    primary: { background: C.primary, color: '#fff' },
    accent:  { background: C.accent,  color: '#fff' },
    success: { background: C.green,   color: '#fff' },
    danger:  { background: C.red,     color: '#fff' },
    secondary: { background: C.surface2, color: C.primary, border: `1px solid ${C.border}` },
  };
  return <button style={{ ...base, ...variants[variant] }} onClick={onClick} disabled={disabled}>{children}</button>;
}

export default function Tareas() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const isAdmin = user?.rol === 'admin';
  const [tab, setTab] = useState('pendiente');
  const [modalNueva, setModalNueva] = useState(false);
  const [form, setForm] = useState({ titulo: '', descripcion: '', asignado_a: '' });
  const [expandida, setExpandida] = useState(null);
  const [notaCompletar, setNotaCompletar] = useState({});
  const [textoComentario, setTextoComentario] = useState({});
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  const { data: tareas = [], isLoading } = useQuery({
    queryKey: ['tareas'],
    queryFn: () => api.get('/tareas').then(r => r.data),
    refetchInterval: 30_000,
  });

  const { data: usuarios = [] } = useQuery({
    queryKey: ['usuarios'],
    queryFn: () => api.get('/usuarios').then(r => r.data),
    enabled: isAdmin,
  });

  const crear = useMutation({
    mutationFn: () => api.post('/tareas', form),
    onSuccess: () => {
      toast.success('Tarea creada');
      qc.invalidateQueries({ queryKey: ['tareas'] });
      setModalNueva(false);
      setForm({ titulo: '', descripcion: '', asignado_a: '' });
    },
    onError: e => toast.error(e.response?.data?.detail || 'Error'),
  });

  const completar = useMutation({
    mutationFn: ({ id, nota }) => api.put(`/tareas/${id}/completar`, { nota }),
    onSuccess: () => {
      toast.success('Tarea completada');
      qc.invalidateQueries({ queryKey: ['tareas'] });
      qc.invalidateQueries({ queryKey: ['notificaciones'] });
    },
    onError: e => toast.error(e.response?.data?.detail || 'Error'),
  });

  const comentar = useMutation({
    mutationFn: ({ id, texto }) => api.post(`/tareas/${id}/comentarios`, { texto }),
    onSuccess: (_, { id }) => {
      toast.success('Comentario agregado');
      qc.invalidateQueries({ queryKey: ['tareas'] });
      setTextoComentario(prev => ({ ...prev, [id]: '' }));
    },
    onError: e => toast.error(e.response?.data?.detail || 'Error'),
  });

  const toLocalDateStr = iso => {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  const filtradas = tareas.filter(t => {
    if (t.estado !== tab) return false;
    const fechaTarea = toLocalDateStr(t.creado);
    if (fechaDesde && fechaTarea < fechaDesde) return false;
    if (fechaHasta && fechaTarea > fechaHasta) return false;
    return true;
  });

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, color: C.primary, fontSize: 22, fontWeight: 700 }}>✅ Tareas</h2>
          <p style={{ margin: '4px 0 0', color: C.text2, fontSize: 13 }}>
            {isAdmin ? 'Gestión y asignación de tareas' : 'Mis tareas asignadas'}
          </p>
        </div>
        {isAdmin && (
          <Btn variant="accent" onClick={() => setModalNueva(true)}>+ Nueva tarea</Btn>
        )}
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Pendientes', estado: 'pendiente', color: C.accent },
          { label: 'Completadas', estado: 'completada', color: C.green },
        ].map(s => (
          <div key={s.estado} onClick={() => setTab(s.estado)} style={{
            background: 'white', borderRadius: 10, padding: '14px 20px',
            border: `2px solid ${tab === s.estado ? s.color : C.border}`,
            cursor: 'pointer', minWidth: 120,
          }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: s.color }}>
              {tareas.filter(t => t.estado === s.estado).length}
            </div>
            <div style={{ fontSize: 12, color: C.text2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filtro por fechas */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 16, background: 'white', borderRadius: 10, padding: '12px 16px', border: `1px solid ${C.border}` }}>
        <div>
          <label style={lbl}>Desde</label>
          <input type="date" style={{ ...inp, width: 150 }} value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} />
        </div>
        <div>
          <label style={lbl}>Hasta</label>
          <input type="date" style={{ ...inp, width: 150 }} value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} />
        </div>
        {(fechaDesde || fechaHasta) && (
          <Btn size="sm" variant="secondary" onClick={() => { setFechaDesde(''); setFechaHasta(''); }}>
            ✕ Limpiar
          </Btn>
        )}
        {(fechaDesde || fechaHasta) && (
          <span style={{ fontSize: 12, color: C.text2, alignSelf: 'center' }}>
            {filtradas.length} resultado{filtradas.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Lista de tareas */}
      {isLoading ? (
        <p style={{ color: C.text2 }}>Cargando...</p>
      ) : filtradas.length === 0 ? (
        <div style={{ background: 'white', borderRadius: 10, padding: 32, textAlign: 'center', border: `1px solid ${C.border}` }}>
          <p style={{ color: C.text2, fontSize: 14 }}>No hay tareas {tab === 'pendiente' ? 'pendientes' : 'completadas'}</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {filtradas.map(t => (
            <div key={t.id} style={{ background: 'white', borderRadius: 10, border: `1px solid ${C.border}`, overflow: 'hidden' }}>
              {/* Cabecera */}
              <div style={{ padding: '14px 18px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 14, color: '#1E293B' }}>{t.titulo}</span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, borderRadius: 10, padding: '2px 10px',
                      background: t.estado === 'pendiente' ? '#FEF3C7' : C.greenBg,
                      color: t.estado === 'pendiente' ? '#92400E' : C.green,
                    }}>
                      {t.estado === 'pendiente' ? 'Pendiente' : 'Completada'}
                    </span>
                  </div>
                  {t.descripcion && (
                    <p style={{ margin: '6px 0 0', fontSize: 13, color: C.text2 }}>{t.descripcion}</p>
                  )}
                  <div style={{ marginTop: 6, fontSize: 11, color: C.text2, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <span>👤 Asignado a: <strong>{t.asignado_a}</strong></span>
                    {isAdmin && <span>📋 Creado por: <strong>{t.creado_por}</strong></span>}
                    <span>📅 {new Date(t.creado).toLocaleDateString('es-CO')}</span>
                    {t.completado_en && <span>✅ Completada: {new Date(t.completado_en).toLocaleDateString('es-CO')}</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  <Btn size="sm" variant="secondary" onClick={() => setExpandida(expandida === t.id ? null : t.id)}>
                    {expandida === t.id ? 'Cerrar' : `💬 ${t.comentarios.length}`}
                  </Btn>
                </div>
              </div>

              {/* Expandido: comentarios + acciones */}
              {expandida === t.id && (
                <div style={{ borderTop: `1px solid ${C.border}`, padding: '14px 18px', background: C.surface2 }}>
                  {/* Comentarios existentes */}
                  {t.comentarios.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 600, color: C.text2 }}>Comentarios:</p>
                      {t.comentarios.map(c => (
                        <div key={c.id} style={{ background: 'white', borderRadius: 7, padding: '8px 12px', marginBottom: 6, border: `1px solid ${C.border}` }}>
                          <span style={{ fontWeight: 600, fontSize: 12, color: C.primary }}>{c.usuario}</span>
                          <span style={{ fontSize: 11, color: C.text2, marginLeft: 8 }}>{new Date(c.creado).toLocaleString('es-CO')}</span>
                          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#1E293B' }}>{c.texto}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Agregar comentario */}
                  <div style={{ display: 'flex', gap: 8, marginBottom: t.estado === 'pendiente' ? 12 : 0 }}>
                    <input
                      style={{ ...inp, flex: 1 }}
                      placeholder="Agregar comentario o novedad..."
                      value={textoComentario[t.id] || ''}
                      onChange={e => setTextoComentario(prev => ({ ...prev, [t.id]: e.target.value }))}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && textoComentario[t.id]?.trim()) {
                          comentar.mutate({ id: t.id, texto: textoComentario[t.id] });
                        }
                      }}
                    />
                    <Btn size="sm" variant="secondary"
                      disabled={!textoComentario[t.id]?.trim()}
                      onClick={() => comentar.mutate({ id: t.id, texto: textoComentario[t.id] })}>
                      Enviar
                    </Btn>
                  </div>

                  {/* Marcar completada (solo empleado en tareas pendientes propias) */}
                  {t.estado === 'pendiente' && (!isAdmin || t.asignado_a === user?.username) && (
                    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                      <div style={{ flex: 1 }}>
                        <label style={lbl}>Nota al completar (opcional)</label>
                        <input
                          style={inp}
                          placeholder="Describe cómo quedó la tarea..."
                          value={notaCompletar[t.id] || ''}
                          onChange={e => setNotaCompletar(prev => ({ ...prev, [t.id]: e.target.value }))}
                        />
                      </div>
                      <Btn variant="success"
                        disabled={completar.isPending}
                        onClick={() => completar.mutate({ id: t.id, nota: notaCompletar[t.id] || '' })}>
                        ✓ Marcar completada
                      </Btn>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal nueva tarea (solo admin) */}
      {modalNueva && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#fff', borderRadius: 14, padding: 28, width: 440, boxShadow: '0 20px 60px rgba(0,0,0,.25)' }}>
            <h3 style={{ margin: '0 0 18px', color: C.primary }}>Nueva tarea</h3>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Título *</label>
              <input style={inp} value={form.titulo} onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))} placeholder="Ej: Actualizar datos de afiliado" />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Descripción</label>
              <textarea rows={3} style={{ ...inp, resize: 'vertical' }} value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} placeholder="Detalle de la tarea..." />
            </div>
            <div style={{ marginBottom: 18 }}>
              <label style={lbl}>Asignar a *</label>
              <select style={inp} value={form.asignado_a} onChange={e => setForm(f => ({ ...f, asignado_a: e.target.value }))}>
                <option value="">— Seleccionar usuario —</option>
                {usuarios.filter(u => u.activo).map(u => (
                  <option key={u.id} value={u.username}>{u.nombre} ({u.username})</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Btn variant="secondary" onClick={() => setModalNueva(false)}>Cancelar</Btn>
              <Btn variant="accent"
                disabled={!form.titulo.trim() || !form.asignado_a || crear.isPending}
                onClick={() => crear.mutate()}>
                {crear.isPending ? 'Creando...' : 'Crear tarea'}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
