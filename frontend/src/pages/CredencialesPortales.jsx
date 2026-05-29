import React, { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import { C, PageHeader, Btn, Modal, ConfirmModal, ErrorMsg } from '../components/UI';
import useAuthStore from '../hooks/useAuth';

const PORTALES = ['EPS', 'CCF', 'ARL', 'Aportes en Línea', 'Pago Simple', 'Asopagos'];
const TIPOS_DOC = ['NIT', 'CC'];

const PORTAL_STYLE = {
  'EPS':              { bg: '#EFF6FF', color: '#2563EB' },
  'CCF':              { bg: '#ECFDF5', color: '#059669' },
  'ARL':              { bg: '#FEF2F2', color: '#DC2626' },
  'Aportes en Línea': { bg: '#FFFBEB', color: '#D97706' },
  'Pago Simple':      { bg: '#F5F3FF', color: '#7C3AED' },
  'Asopagos':         { bg: '#FDF2F8', color: '#DB2777' },
};

const EMPTY_FORM = {
  portal: 'EPS', entidad: '',
  usuario_portal: '', clave_portal: '', obs: '',
};

// Detecta URLs http(s) en texto plano y las convierte en <a> seguros.
// Soporta hasta el primer carácter de espacio o salto de línea.
// XSS-safe: solo construye <a> con href validado, nunca innerHTML.
const URL_RE = /(https?:\/\/[^\s<>"']+)/g;

function linkify(text, linkColor = '#2563EB') {
  if (!text) return null;
  const parts = String(text).split(URL_RE);
  return parts.map((part, i) => {
    if (URL_RE.test(part)) {
      URL_RE.lastIndex = 0;
      return (
        <a
          key={i}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => e.stopPropagation()}
          style={{ color: linkColor, textDecoration: 'underline', wordBreak: 'break-all' }}
        >
          {part}
        </a>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

function PortalBadge({ portal }) {
  const s = PORTAL_STYLE[portal] || { bg: '#F3F4F6', color: '#6B7280' };
  return (
    <span style={{
      fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
      padding: '3px 8px', borderRadius: 4, background: s.bg, color: s.color,
      fontFamily: 'monospace', whiteSpace: 'nowrap',
    }}>
      {portal}
    </span>
  );
}

const lbl = {
  fontSize: 11, fontWeight: 700, color: C.text2, textTransform: 'uppercase',
  letterSpacing: '0.05em', marginBottom: 4, display: 'block',
};
const inp = {
  padding: '9px 12px', borderRadius: 8, border: `1px solid ${C.border}`,
  background: C.surface, fontSize: 13, color: C.text, outline: 'none',
  fontFamily: 'inherit', width: '100%', boxSizing: 'border-box',
};
const mono = { ...inp, fontFamily: 'monospace' };

export default function CredencialesPortales() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.rol === 'admin';

  const [filtroPortal, setFiltroPortal] = useState('');
  const [buscar, setBuscar] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [showPw, setShowPw] = useState(false);
  const [claves, setClaves] = useState({});
  const [confirmDel, setConfirmDel] = useState(null);
  const [modalObs, setModalObs] = useState(null);   // credencial seleccionada para ver obs completa

  // Seguridad: limpiar claves reveladas al desmontar (cambio de página, logout)
  // y al perder visibilidad del tab para que no queden en memoria del SPA.
  useEffect(() => {
    const onVisibility = () => { if (document.hidden) setClaves({}); };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      setClaves({});
    };
  }, []);

  const { data: creds = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['credenciales'],
    queryFn: () => api.get('/credenciales').then(r => r.data),
  });

  const filtradas = useMemo(() => {
    let r = creds;
    if (filtroPortal) r = r.filter(c => c.portal === filtroPortal);
    if (buscar.trim()) {
      const q = buscar.toLowerCase();
      r = r.filter(c =>
        [c.titular, c.entidad, c.usuario_portal, c.numero_doc, c.portal]
          .join(' ').toLowerCase().includes(q)
      );
    }
    return r;
  }, [creds, filtroPortal, buscar]);

  const stats = useMemo(() => {
    const m = {};
    creds.forEach(c => { m[c.portal] = (m[c.portal] || 0) + 1; });
    return m;
  }, [creds]);

  const mutCreate = useMutation({
    mutationFn: d => api.post('/credenciales', d).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['credenciales'] }); toast.success('Credencial guardada'); closeForm(); },
  });
  const mutUpdate = useMutation({
    mutationFn: ({ id, d }) => api.put(`/credenciales/${id}`, d).then(r => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['credenciales'] }); toast.success('Actualizada'); closeForm(); },
  });
  const mutDelete = useMutation({
    mutationFn: id => api.delete(`/credenciales/${id}`),
    onSuccess: () => {
      // Limpiar clave revelada si existía
      if (confirmDel) setClaves(p => { const n = { ...p }; delete n[confirmDel.id]; return n; });
      qc.invalidateQueries({ queryKey: ['credenciales'] });
      toast.success('Credencial eliminada');
      setConfirmDel(null);
    },
  });

  const toggleClave = async (id) => {
    if (claves[id] !== undefined) {
      setClaves(p => { const n = { ...p }; delete n[id]; return n; });
      return;
    }
    try {
      const r = await api.get(`/credenciales/${id}/clave`);
      setClaves(p => ({ ...p, [id]: r.data.clave }));
    } catch { toast.error('Error al revelar clave'); }
  };

  const openNew = () => {
    setEditId(null); setForm(EMPTY_FORM); setShowPw(false); setShowForm(true);
  };
  const openEdit = (c) => {
    setEditId(c.id);
    setForm({ portal: c.portal, entidad: c.entidad,
               usuario_portal: c.usuario_portal, clave_portal: '', obs: c.obs || '' });
    setShowPw(false); setShowForm(true);
  };
  const closeForm = () => { setShowForm(false); setEditId(null); };

  const handleSubmit = () => {
    if (!form.entidad.trim() || !form.usuario_portal.trim()) {
      toast.error('Completa todos los campos requeridos'); return;
    }
    if (!editId && !form.clave_portal.trim()) { toast.error('La contraseña es requerida'); return; }
    const d = { ...form };
    if (editId && !d.clave_portal) delete d.clave_portal;
    if (editId) mutUpdate.mutate({ id: editId, d });
    else mutCreate.mutate(d);
  };

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const busy = mutCreate.isPending || mutUpdate.isPending;

  return (
    <div>
      <PageHeader
        title="🔑 Credenciales de Portales"
        subtitle="Accesos a portales EPS, cajas de compensación y sistemas de pago"
        action={<Btn variant="primary" onClick={openNew}>+ Nueva Credencial</Btn>}
      />

      {/* Stats */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {[
          { label: 'Total', val: creds.length, color: C.primary },
          ...PORTALES.map(p => ({ label: p, val: stats[p] || 0, color: PORTAL_STYLE[p]?.color })),
        ].map(s => (
          <div key={s.label} style={{
            background: '#fff', border: `1px solid ${C.border}`, borderRadius: 10,
            padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.color, flexShrink: 0 }} />
            <span style={{ fontWeight: 800, fontSize: 18, color: C.primary }}>{s.val}</span>
            <span style={{ fontSize: 10, color: C.text2, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        {['', ...PORTALES].map(p => {
          const active = filtroPortal === p;
          const col = PORTAL_STYLE[p]?.color || C.primary;
          return (
            <button key={p} onClick={() => setFiltroPortal(p)} style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 700, cursor: 'pointer',
              border: `1.5px solid ${active ? col : C.border}`,
              background: active ? col : '#fff',
              color: active ? '#fff' : C.text2,
              transition: 'all 0.15s',
            }}>
              {p || 'Todos'}
            </button>
          );
        })}
        <input
          style={{ ...inp, width: 220, marginLeft: 'auto', padding: '6px 12px' }}
          placeholder="🔍 Buscar..."
          value={buscar}
          onChange={e => setBuscar(e.target.value)}
        />
      </div>

      {isError && (
        <ErrorMsg msg="Error al cargar credenciales">
          <button onClick={refetch} style={{ marginLeft: 8, color: C.primary, textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}>
            Reintentar
          </button>
        </ErrorMsg>
      )}

      {isLoading ? (
        <p style={{ color: C.text2, fontSize: 13 }}>Cargando...</p>
      ) : filtradas.length === 0 ? (
        <p style={{ color: C.text2, fontSize: 13, textAlign: 'center', padding: 40 }}>
          {creds.length === 0 ? 'No hay credenciales registradas. Agrega la primera.' : 'Sin resultados para el filtro actual.'}
        </p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
          {filtradas.map(c => {
            const clave = claves[c.id];
            const revealed = clave !== undefined;
            return (
              <div key={c.id} style={{
                background: '#fff',
                border: `1px solid ${revealed ? 'rgba(201,168,76,0.5)' : C.border}`,
                borderRadius: 14, overflow: 'hidden',
                boxShadow: revealed ? '0 0 0 3px rgba(201,168,76,0.1)' : '0 1px 4px rgba(0,0,0,0.04)',
                transition: 'all 0.18s',
              }}>
                {/* Top */}
                <div style={{
                  padding: '12px 16px', borderBottom: `1px solid ${C.border}`,
                }}>
                  <PortalBadge portal={c.portal} />
                </div>

                {/* Body */}
                <div style={{ padding: '12px 16px' }}>
                  <div style={{ fontWeight: 700, fontSize: 15, color: C.primary, marginBottom: 12 }}>{c.entidad || '—'}</div>

                  <div style={{ marginBottom: 8 }}>
                    <div style={lbl}>Usuario</div>
                    <div style={{ fontFamily: 'monospace', fontSize: 12, background: C.surface2, padding: '5px 10px', borderRadius: 6, border: `1px solid ${C.border}`, wordBreak: 'break-all' }}>
                      {c.usuario_portal}
                    </div>
                  </div>

                  <div>
                    <div style={lbl}>Contraseña</div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <div style={{
                        fontFamily: 'monospace', fontSize: 12, padding: '5px 10px', borderRadius: 6, flex: 1,
                        border: `1px solid ${revealed ? '#BBF7D0' : C.border}`,
                        background: revealed ? '#F0FDF4' : C.surface2,
                        color: revealed ? '#16A34A' : C.text2,
                        letterSpacing: revealed ? 'normal' : '0.18em',
                        wordBreak: 'break-all',
                      }}>
                        {revealed ? clave : '••••••••••••'}
                      </div>
                      <button onClick={() => toggleClave(c.id)} style={{
                        padding: '5px 11px', borderRadius: 6, border: 'none', cursor: 'pointer',
                        fontSize: 11, fontWeight: 700, letterSpacing: '0.03em', whiteSpace: 'nowrap',
                        background: revealed
                          ? '#F0FDF4'
                          : 'linear-gradient(135deg, #7A5800, #C9A84C)',
                        color: revealed ? '#16A34A' : '#fff',
                        boxShadow: revealed ? 'none' : '0 2px 6px rgba(201,168,76,0.4)',
                        transition: 'all 0.15s',
                      }}>
                        {revealed ? '🔒 Ocultar' : '👁 Revelar'}
                      </button>
                    </div>
                  </div>

                  {c.obs && (() => {
                    const obsTrim = c.obs.trim();
                    const isLong = obsTrim.length > 80 || obsTrim.includes('\n');
                    const preview = isLong ? obsTrim.slice(0, 80).replace(/\n/g, ' ') + '…' : obsTrim;
                    return (
                      <div
                        onClick={() => setModalObs(c)}
                        title="Click para ver completa"
                        style={{
                          marginTop: 8, fontSize: 11, color: C.text2, background: C.surface2,
                          borderRadius: 6, padding: '6px 10px', fontStyle: 'italic',
                          cursor: 'pointer', border: `1px solid transparent`,
                          transition: 'border-color 0.15s, background 0.15s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.background = '#fff'; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'transparent'; e.currentTarget.style.background = C.surface2; }}
                      >
                        <span style={{ marginRight: 6 }}>📝</span>
                        {linkify(preview)}
                        {isLong && (
                          <span style={{ marginLeft: 6, color: C.primary, fontStyle: 'normal', fontWeight: 700 }}>
                            Ver completa →
                          </span>
                        )}
                      </div>
                    );
                  })()}
                </div>

                {/* Footer */}
                <div style={{
                  padding: '9px 16px', borderTop: `1px solid ${C.border}`, background: C.surface,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span style={{ fontSize: 11, color: C.text2 }}>
                    {c.actualizado ? `Actualizado ${c.actualizado}` : `Creado ${c.creado}`}
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => openEdit(c)} title="Editar" style={{
                      width: 28, height: 28, borderRadius: 6, border: `1px solid ${C.border}`,
                      background: '#fff', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>✏️</button>
                    {isAdmin && (
                      <button onClick={() => setConfirmDel(c)} title="Eliminar" style={{
                        width: 28, height: 28, borderRadius: 6, border: `1px solid ${C.border}`,
                        background: '#fff', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>🗑️</button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal form */}
      <Modal open={showForm} onClose={closeForm} title={editId ? 'Editar Credencial' : 'Nueva Credencial'} width={560}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '4px 0' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div>
              <label style={lbl}>Portal *</label>
              <select style={inp} value={form.portal} onChange={e => f('portal', e.target.value)}>
                {PORTALES.map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label style={lbl}>Entidad *</label>
              <input style={inp} value={form.entidad} onChange={e => f('entidad', e.target.value)} placeholder="Ej: Sura EPS, Compensar…" />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div>
              <label style={lbl}>Usuario del portal *</label>
              <input style={mono} value={form.usuario_portal} onChange={e => f('usuario_portal', e.target.value)} placeholder="usuario@email.com" />
            </div>
            <div>
              <label style={lbl}>Contraseña {editId ? '(vacío = sin cambio)' : '*'}</label>
              <div style={{ position: 'relative' }}>
                <input
                  style={{ ...mono, paddingRight: 36 }}
                  type={showPw ? 'text' : 'password'}
                  value={form.clave_portal}
                  onChange={e => f('clave_portal', e.target.value)}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(p => !p)}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: C.text2 }}
                >
                  {showPw ? '🙈' : '👁'}
                </button>
              </div>
            </div>
          </div>

          <div>
            <label style={lbl}>Observaciones <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, color: C.text2 }}>— soporta URLs (se vuelven enlaces clicables)</span></label>
            <textarea
              style={{ ...inp, minHeight: 72, resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }}
              value={form.obs}
              onChange={e => f('obs', e.target.value)}
              placeholder="Notas, URL del portal, instrucciones, etc."
              rows={3}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, paddingTop: 4 }}>
            <Btn variant="secondary" onClick={closeForm}>Cancelar</Btn>
            <Btn variant="primary" onClick={handleSubmit} disabled={busy}>
              {busy ? 'Guardando…' : editId ? 'Guardar cambios' : 'Guardar Credencial'}
            </Btn>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={!!confirmDel}
        title="Eliminar credencial"
        message={confirmDel ? `¿Eliminar credencial de ${confirmDel.portal} — ${confirmDel.entidad}?` : ''}
        confirmLabel="Eliminar"
        variant="danger"
        onConfirm={() => mutDelete.mutate(confirmDel.id)}
        onCancel={() => setConfirmDel(null)}
      />

      {/* Modal: observación completa con URLs clicables */}
      <Modal
        open={!!modalObs}
        onClose={() => setModalObs(null)}
        title={modalObs ? `📝 Observaciones — ${modalObs.portal} · ${modalObs.entidad || ''}` : ''}
        width={620}
      >
        {modalObs && (
          <div style={{ padding: '4px 0' }}>
            <div style={{
              background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 8,
              padding: '14px 16px', fontSize: 14, lineHeight: 1.65, color: C.text,
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              maxHeight: '60vh', overflowY: 'auto',
            }}>
              {linkify(modalObs.obs)}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 14 }}>
              <Btn variant="secondary" onClick={() => setModalObs(null)}>Cerrar</Btn>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
