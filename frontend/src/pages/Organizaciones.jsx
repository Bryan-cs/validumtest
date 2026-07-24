import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';
import { C, Btn, ConfirmModal, ErrorMsg } from '../components/UI';

const lbl = { display: 'block', fontSize: 12, color: C.text2, fontWeight: 500, marginBottom: 4 };
const inp = { width: '100%', padding: '9px 12px', border: `1px solid ${C.border}`, borderRadius: 7, fontSize: 13, outline: 'none', boxSizing: 'border-box', color: C.text, background: C.surface };

export default function Organizaciones() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { user, orgActiva, setOrgActiva, logout } = useAuthStore();

  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [err, setErr] = useState('');
  const [confirmDel, setConfirmDel] = useState(null);
  const sf = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const { data: orgs = [], isError, refetch } = useQuery({
    queryKey: ['organizaciones'],
    queryFn: () => api.get('/organizaciones').then(r => r.data),
  });

  const crear = useMutation({
    mutationFn: () => {
      if (!form.nombre || !form.admin_username || !form.admin_password) {
        setErr('Nombre de la organización, usuario y contraseña del admin son obligatorios.');
        return Promise.reject();
      }
      if (form.admin_password !== form.admin_password2) {
        setErr('Las contraseñas no coinciden.');
        return Promise.reject();
      }
      return api.post('/organizaciones', {
        nombre: form.nombre,
        slug: form.slug || undefined,
        admin_username: form.admin_username,
        admin_password: form.admin_password,
        admin_nombre: form.admin_nombre || undefined,
      });
    },
    onSuccess: (res) => {
      toast.success('Organización creada');
      qc.setQueryData(['organizaciones'], prev => [res.data, ...(prev || [])]);
      setModal(false); setForm({}); setErr('');
    },
    onError: (e) => {
      if (e?.response) {
        const d = e.response?.data?.detail;
        setErr(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error'));
      }
    },
  });

  const toggleActivo = useMutation({
    mutationFn: (org) => api.patch(`/organizaciones/${org.id}`, { activo: !org.activo }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['organizaciones'] }); },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  });

  const eliminar = useMutation({
    mutationFn: (id) => api.delete(`/organizaciones/${id}`),
    onSuccess: (_, id) => {
      toast.success('Organización eliminada');
      qc.setQueryData(['organizaciones'], prev => prev?.filter(o => o.id !== id));
      setConfirmDel(null);
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  });

  const entrar = (org) => {
    setOrgActiva({ id: org.id, nombre: org.nombre });
    toast.success(`Entrando a ${org.nombre}`);
    navigate('/');
  };

  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.text }}>
      {/* Barra superior */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 28px', borderBottom: `1px solid ${C.border}`, background: C.surface }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: C.primary,
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700 }}>◆</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700 }}>Panel Superadmin</div>
            <div style={{ fontSize: 12, color: C.text2 }}>Gestión de organizaciones · {user?.nombre}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {orgActiva && (
            <Btn variant="secondary" size="sm" onClick={() => navigate('/')}>
              Volver a {orgActiva.nombre}
            </Btn>
          )}
          <Btn variant="secondary" size="sm" onClick={() => logout().then(() => navigate('/login'))}>
            Cerrar sesión
          </Btn>
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Organizaciones</h1>
            <p style={{ fontSize: 13, color: C.text2, margin: '4px 0 0' }}>
              Cada organización tiene sus propios usuarios, afiliados y datos aislados.
            </p>
          </div>
          <Btn onClick={() => { setForm({}); setErr(''); setModal(true); }}>+ Nueva organización</Btn>
        </div>

        {isError ? (
          <ErrorMsg message="No se pudieron cargar las organizaciones" onRetry={refetch} />
        ) : orgs.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: C.text2, border: `1px dashed ${C.border}`, borderRadius: 10 }}>
            Aún no hay organizaciones. Crea la primera para empezar.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
            {orgs.map(org => (
              <div key={org.id} style={{ border: `1px solid ${C.border}`, borderRadius: 10, padding: 16, background: C.surface }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{org.nombre}</div>
                    <div style={{ fontSize: 12, color: C.text2, fontFamily: 'monospace' }}>{org.slug}</div>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 20,
                    background: org.activo ? C.greenBg : C.redBg, color: org.activo ? C.green : C.red }}>
                    {org.activo ? 'Activa' : 'Inactiva'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 18, margin: '14px 0', fontSize: 13, color: C.text2 }}>
                  <div><b style={{ color: C.text, fontSize: 16 }}>{org.total_usuarios ?? 0}</b> usuarios</div>
                  <div><b style={{ color: C.text, fontSize: 16 }}>{org.total_afiliados ?? 0}</b> afiliados</div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Btn size="sm" onClick={() => entrar(org)}>Entrar</Btn>
                  <Btn size="sm" variant="secondary" onClick={() => toggleActivo.mutate(org)}>
                    {org.activo ? 'Desactivar' : 'Activar'}
                  </Btn>
                  <Btn size="sm" variant="danger" onClick={() => setConfirmDel(org)}>Eliminar</Btn>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal crear organización */}
      {modal && (
        <div onClick={() => setModal(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: 16 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: C.surface, borderRadius: 12, padding: 24,
            width: 460, maxWidth: '100%', maxHeight: '90vh', overflowY: 'auto', border: `1px solid ${C.border}` }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 4px' }}>Nueva organización</h2>
            <p style={{ fontSize: 12, color: C.text2, margin: '0 0 18px' }}>
              Se crea la organización y su usuario administrador inicial.
            </p>
            {err && <div style={{ background: C.redBg, color: C.red, padding: '8px 12px', borderRadius: 7, fontSize: 12, marginBottom: 14 }}>{err}</div>}
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Nombre de la organización *</label>
              <input style={inp} value={form.nombre || ''} onChange={e => sf('nombre', e.target.value)} placeholder="Ej: Contadores del Valle S.A.S" />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Slug (opcional)</label>
              <input style={inp} value={form.slug || ''} onChange={e => sf('slug', e.target.value)} placeholder="se genera del nombre si se deja vacío" />
            </div>
            <hr style={{ border: 'none', borderTop: `1px solid ${C.border}`, margin: '16px 0' }} />
            <div style={{ fontSize: 12, fontWeight: 600, color: C.text2, marginBottom: 10 }}>ADMINISTRADOR INICIAL</div>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Nombre del admin</label>
              <input style={inp} value={form.admin_nombre || ''} onChange={e => sf('admin_nombre', e.target.value)} placeholder="opcional" />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={lbl}>Usuario (login) *</label>
              <input style={inp} value={form.admin_username || ''} onChange={e => sf('admin_username', e.target.value)} placeholder="usuario único global" />
            </div>
            <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
              <div style={{ flex: 1 }}>
                <label style={lbl}>Contraseña *</label>
                <input type="password" style={inp} value={form.admin_password || ''} onChange={e => sf('admin_password', e.target.value)} />
              </div>
              <div style={{ flex: 1 }}>
                <label style={lbl}>Confirmar *</label>
                <input type="password" style={inp} value={form.admin_password2 || ''} onChange={e => sf('admin_password2', e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Btn variant="secondary" onClick={() => setModal(false)}>Cancelar</Btn>
              <Btn onClick={() => crear.mutate()} disabled={crear.isPending}>
                {crear.isPending ? 'Creando...' : 'Crear organización'}
              </Btn>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={!!confirmDel}
        title="Eliminar organización"
        message={confirmDel ? `¿Eliminar "${confirmDel.nombre}" y TODOS sus datos (usuarios, afiliados, facturas...)? Esta acción no se puede deshacer.` : ''}
        confirmLabel="Eliminar todo"
        onConfirm={() => eliminar.mutate(confirmDel.id)}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
