import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as ReTooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { toast } from 'sonner';
import api from '../utils/api';
import useAuthStore from '../hooks/useAuth';

/* ─────────────────────────────────────────────────────────────────────────────
   Panel Superadmin — dashboard claro estilo admin clásico:
   fondo gris claro, tarjetas blancas redondeadas con sombra suave,
   tarjeta destacada oscura, tipografía Figtree, números tabulares.
   ──────────────────────────────────────────────────────────────────────────── */
const ESTILOS = `
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

.sa-root {
  --bg:     #F4F5F8;
  --card:   #FFFFFF;
  --ink:    #232629;
  --muted:  #8A9099;
  --line:   #E9EBEF;
  --dark:   #2B2D31;
  --green:  #3FA96E;
  --amber:  #E0A23C;
  --red:    #D9695C;
  --shadow: 0 1px 3px rgba(16,24,40,.07), 0 1px 2px rgba(16,24,40,.04);
  --shadow-lg: 0 10px 28px -8px rgba(16,24,40,.14), 0 2px 6px rgba(16,24,40,.05);
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  font-family: 'Figtree', sans-serif;
  -webkit-font-smoothing: antialiased;
}
@keyframes saUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes saFade { from { opacity: 0; } to { opacity: 1; } }

/* ── Topbar ── */
.sa-top {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 32px; background: var(--card); border-bottom: 1px solid var(--line);
  position: sticky; top: 0; z-index: 20;
}
.sa-brand { display: flex; align-items: center; gap: 12px; }
.sa-logo {
  width: 38px; height: 38px; border-radius: 10px; background: var(--dark);
  display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 17px;
}
.sa-brand-name { font-size: 17px; font-weight: 800; letter-spacing: -.2px; }
.sa-brand-sub  { font-size: 11px; color: var(--muted); font-weight: 500; margin-top: 1px; }
.sa-user { text-align: right; }
.sa-user-name { font-size: 13px; font-weight: 700; }
.sa-user-rol  { font-size: 11px; color: var(--muted); }

/* ── Encabezado ── */
.sa-head { max-width: 1180px; margin: 0 auto; padding: 30px 32px 0; display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; animation: saUp .4s ease both; }
.sa-title { font-size: 26px; font-weight: 800; letter-spacing: -.4px; margin: 0; }
.sa-lede  { color: var(--muted); font-size: 13.5px; margin: 4px 0 0; }

/* ── Tabs ── */
.sa-tabs { max-width: 1180px; margin: 22px auto 0; padding: 0 32px; display: flex; gap: 4px; animation: saUp .4s .05s ease both; }
.sa-tab {
  background: none; border: none; cursor: pointer; padding: 9px 16px; border-radius: 10px;
  font-family: inherit; font-size: 13.5px; font-weight: 600; color: var(--muted);
  transition: all .2s;
}
.sa-tab:hover { color: var(--ink); background: rgba(0,0,0,.04); }
.sa-tab[data-on="true"] { background: var(--dark); color: #fff; }
.sa-tab b { font-size: 11px; font-weight: 700; opacity: .55; margin-left: 6px; }

.sa-main { max-width: 1180px; margin: 0 auto; padding: 22px 32px 70px; }

/* ── Tarjetas / tiles ── */
.sa-card {
  background: var(--card); border-radius: 16px; box-shadow: var(--shadow);
  padding: 22px; transition: box-shadow .25s, transform .25s; animation: saUp .4s ease both;
}
.sa-card:hover { box-shadow: var(--shadow-lg); }
.sa-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 18px; }
.sa-card-name { font-size: 16.5px; font-weight: 800; letter-spacing: -.2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sa-card-slug { font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: var(--muted); margin-top: 2px; }
.sa-chip { font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; white-space: nowrap; }
.sa-chip--on  { color: var(--green); background: rgba(63,169,110,.12); }
.sa-chip--off { color: var(--red); background: rgba(217,105,92,.12); }
.sa-card-stats { display: flex; gap: 30px; margin: 18px 0 16px; padding-top: 14px; border-top: 1px solid var(--line); }
.sa-stat-n { font-size: 24px; font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
.sa-stat-l { font-size: 11.5px; color: var(--muted); font-weight: 600; margin-top: 4px; }

/* ── Tiles resumen (fila superior) ── */
.sa-tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; margin-bottom: 18px; }
@media (max-width: 980px) { .sa-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 540px) { .sa-tiles { grid-template-columns: 1fr; } }
.sa-tile {
  background: var(--card); border-radius: 16px; box-shadow: var(--shadow); padding: 20px 22px;
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  animation: saUp .4s ease both;
}
.sa-tile--dark { background: var(--dark); color: #fff; }
.sa-tile--dark .sa-tile-l { color: rgba(255,255,255,.65); }
.sa-tile-l { font-size: 13px; font-weight: 700; color: var(--ink); }
.sa-tile--dark .sa-tile-label-row { color: #fff; }
.sa-tile-n { font-size: 27px; font-weight: 800; letter-spacing: -.5px; margin-top: 10px; font-variant-numeric: tabular-nums; line-height: 1.05; }
.sa-tile-sub { font-size: 11.5px; color: var(--muted); font-weight: 600; margin-top: 5px; }
.sa-tile--dark .sa-tile-sub { color: rgba(255,255,255,.55); }
.sa-ico {
  width: 40px; height: 40px; border-radius: 999px; flex: none;
  display: grid; place-items: center; background: #F1F2F5; color: var(--ink);
}
.sa-tile--dark .sa-ico { background: rgba(255,255,255,.14); color: #fff; }

/* ── Tabla ── */
.sa-tablewrap { background: var(--card); border-radius: 16px; box-shadow: var(--shadow); overflow-x: auto; animation: saUp .4s .08s ease both; }
.sa-tabletitle { font-size: 15.5px; font-weight: 800; padding: 20px 24px 6px; }
.sa-table { width: 100%; border-collapse: collapse; font-size: 13.5px; min-width: 700px; }
.sa-table thead th {
  font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: var(--muted);
  font-weight: 700; text-align: center; padding: 12px 18px; border-bottom: 1px solid var(--line);
}
.sa-table thead th:first-child { text-align: left; padding-left: 24px; }
.sa-table tbody tr { border-bottom: 1px solid var(--line); transition: background .15s; }
.sa-table tbody tr:last-child { border-bottom: none; }
.sa-table tbody tr:hover { background: #FAFBFC; }
.sa-table td { padding: 14px 18px; text-align: center; font-variant-numeric: tabular-nums; font-weight: 600; }
.sa-table td:first-child { text-align: left; padding-left: 24px; }
.sa-td-name { font-weight: 800; }
.sa-td-slug { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--muted); font-weight: 400; margin-top: 1px; }
.sa-badge-n { display: inline-block; min-width: 34px; padding: 3px 9px; border-radius: 999px; font-weight: 700; font-size: 12.5px; }

/* ── Botones ── */
.sa-btn {
  font-family: inherit; font-size: 13px; font-weight: 700; padding: 9px 18px; border-radius: 10px;
  cursor: pointer; transition: all .2s; background: var(--dark); color: #fff; border: 1px solid var(--dark);
}
.sa-btn:hover { background: #3A3D42; border-color: #3A3D42; box-shadow: var(--shadow); }
.sa-btn:disabled { opacity: .4; cursor: not-allowed; box-shadow: none; }
.sa-btn--ghost { background: var(--card); color: var(--ink); border: 1px solid var(--line); }
.sa-btn--ghost:hover { background: #F6F7F9; border-color: #DDE0E5; box-shadow: none; }
.sa-btn--danger { background: var(--card); color: var(--red); border: 1px solid var(--line); }
.sa-btn--danger:hover { background: rgba(217,105,92,.08); border-color: rgba(217,105,92,.4); box-shadow: none; }
.sa-btn--sm { padding: 7px 14px; font-size: 12px; border-radius: 9px; }

/* ── Panel dashboard: dona + tabla ── */
.sa-dash-grid { display: grid; grid-template-columns: 1fr 340px; gap: 18px; align-items: start; }
@media (max-width: 900px) { .sa-dash-grid { grid-template-columns: 1fr; } }
.sa-legend { display: flex; flex-direction: column; gap: 10px; margin-top: 6px; }
.sa-legend-item { display: flex; align-items: center; gap: 9px; font-size: 13px; font-weight: 600; color: var(--ink); }
.sa-legend-dot { width: 9px; height: 9px; border-radius: 999px; flex: none; }
.sa-legend-n { margin-left: auto; font-weight: 800; font-variant-numeric: tabular-nums; }

/* ── Modales ── */
.sa-overlay {
  position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center;
  background: rgba(23,25,28,.45); backdrop-filter: blur(3px); padding: 18px; animation: saFade .2s ease both;
}
.sa-modal {
  background: var(--card); border-radius: 18px; padding: 28px;
  width: 460px; max-width: 100%; max-height: 92vh; overflow-y: auto;
  box-shadow: 0 24px 60px -12px rgba(16,24,40,.28); animation: saUp .3s ease both;
}
.sa-modal-title { font-size: 19px; font-weight: 800; letter-spacing: -.3px; margin: 0 0 4px; }
.sa-modal-sub { font-size: 12.5px; color: var(--muted); line-height: 1.55; margin: 0 0 18px; }
.sa-label { display: block; font-size: 12px; font-weight: 700; color: var(--ink); margin-bottom: 6px; }
.sa-input {
  width: 100%; box-sizing: border-box; padding: 10px 13px; font-family: inherit; font-size: 13.5px;
  background: #FAFBFC; color: var(--ink); border: 1px solid var(--line); border-radius: 10px;
  outline: none; transition: border-color .2s, box-shadow .2s;
}
.sa-input:focus { border-color: var(--dark); background: #fff; box-shadow: 0 0 0 3px rgba(43,45,49,.08); }
.sa-field { margin-bottom: 13px; }
.sa-divider { font-size: 10.5px; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); font-weight: 700; margin: 18px 0 12px; display: flex; align-items: center; gap: 10px; }
.sa-divider::after { content: ''; flex: 1; height: 1px; background: var(--line); }
.sa-err {
  background: rgba(217,105,92,.09); border: 1px solid rgba(217,105,92,.28); color: #B84C40;
  padding: 9px 13px; border-radius: 10px; font-size: 12.5px; font-weight: 600; margin-bottom: 14px;
}
.sa-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }

.sa-empty {
  background: var(--card); border-radius: 16px; box-shadow: var(--shadow);
  padding: 64px 30px; text-align: center; color: var(--muted); font-size: 13.5px;
}
.sa-empty b { display: block; font-size: 17px; font-weight: 800; color: var(--ink); margin-bottom: 5px; }

/* ── Precio editable ── */
.sa-price { display: inline-flex; align-items: center; gap: 7px; justify-content: center; }
.sa-price-v { font-weight: 800; }
.sa-price-edit {
  background: #F1F2F5; border: none; cursor: pointer; color: var(--muted); font-size: 12px;
  width: 26px; height: 26px; border-radius: 8px; display: grid; place-items: center; transition: all .2s;
}
.sa-price-edit:hover { background: var(--dark); color: #fff; }
.sa-price-input {
  width: 100px; padding: 7px 9px; font-family: 'JetBrains Mono', monospace; font-size: 12.5px;
  background: #fff; color: var(--ink); border: 1.5px solid var(--dark); border-radius: 9px;
  outline: none; text-align: right;
}

@media (max-width: 640px) {
  .sa-top { padding: 12px 16px; }
  .sa-head, .sa-tabs { padding-left: 16px; padding-right: 16px; }
  .sa-main { padding: 18px 16px 60px; }
}
`;

/* Iconos SVG minimalistas (estilo material outline) */
const Ico = {
  users: (c = 'currentColor') => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  check: (c = 'currentColor') => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  pause: (c = 'currentColor') => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2.2" strokeLinecap="round">
      <line x1="10" y1="5" x2="10" y2="19" /><line x1="14" y1="5" x2="14" y2="19" />
    </svg>
  ),
  alert: (c = 'currentColor') => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  money: (c = 'currentColor') => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  building: (c = 'currentColor') => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="2" width="16" height="20" rx="2" /><line x1="9" y1="7" x2="10" y2="7" /><line x1="14" y1="7" x2="15" y2="7" />
      <line x1="9" y1="11" x2="10" y2="11" /><line x1="14" y1="11" x2="15" y2="11" /><path d="M9 22v-4h6v4" />
    </svg>
  ),
};

const COLORES_ESTADO = {
  activos: '#3FA96E',
  suspendidos: '#E0A23C',
  no_encontrados: '#D9695C',
  otros: '#B9BEC6',
};

export default function Organizaciones() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { user, logout, login } = useAuthStore();

  const [tab, setTab] = useState('orgs');   // 'orgs' | 'dash' | 'ing'
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [err, setErr] = useState('');
  const [confirmDel, setConfirmDel] = useState(null);
  const sf = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // Login por organización (segundo login)
  const [loginOrg, setLoginOrg] = useState(null);
  const [lf, setLf] = useState({});
  const [lErr, setLErr] = useState('');
  const [lLoading, setLLoading] = useState(false);

  const { data: orgs = [], isError, refetch } = useQuery({
    queryKey: ['organizaciones'],
    queryFn: () => api.get('/organizaciones').then(r => r.data),
  });

  const { data: dash, isError: dashError, refetch: refetchDash } = useQuery({
    queryKey: ['organizaciones-dashboard'],
    queryFn: () => api.get('/organizaciones/dashboard').then(r => r.data),
    enabled: tab === 'dash',
  });

  const { data: ing, isError: ingError, refetch: refetchIng } = useQuery({
    queryKey: ['organizaciones-ingresos'],
    queryFn: () => api.get('/organizaciones/ingresos').then(r => r.data),
    enabled: tab === 'ing',
  });

  // Facturas emitidas a organizaciones
  const { data: fact } = useQuery({
    queryKey: ['organizaciones-facturas'],
    queryFn: () => api.get('/organizaciones/facturas').then(r => r.data),
    enabled: tab === 'ing',
  });
  const facturar = useMutation({
    mutationFn: (orgId) => api.post(`/organizaciones/${orgId}/facturar`),
    onSuccess: (res) => {
      const f = res.data;
      toast.success(`Factura emitida: ${f.nombre} · ${f.periodo} · ${f.afiliados} afiliados`);
      qc.invalidateQueries({ queryKey: ['organizaciones-facturas'] });
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al facturar'),
  });
  const pagarFactura = useMutation({
    mutationFn: (id) => api.patch(`/organizaciones/facturas/${id}/pagar`),
    onSuccess: () => { toast.success('Factura marcada como pagada'); qc.invalidateQueries({ queryKey: ['organizaciones-facturas'] }); },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  });
  const anularFactura = useMutation({
    mutationFn: (id) => api.delete(`/organizaciones/facturas/${id}`),
    onSuccess: () => { toast.success('Factura anulada'); qc.invalidateQueries({ queryKey: ['organizaciones-facturas'] }); },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  });

  // Resumen mensual (snapshots congelados por mes)
  const [anioMens, setAnioMens] = useState(0);   // 0 = año actual
  const { data: mens } = useQuery({
    queryKey: ['organizaciones-ingresos-mensuales', anioMens],
    queryFn: () => api.get('/organizaciones/ingresos-mensuales', { params: anioMens ? { anio: anioMens } : {} }).then(r => r.data),
    enabled: tab === 'ing',
  });

  // Edición inline del precio por afiliado
  const [editPrecio, setEditPrecio] = useState(null);
  const precioMut = useMutation({
    mutationFn: ({ id, precio }) => api.patch(`/organizaciones/${id}`, { precio_afiliado: precio }),
    onSuccess: () => {
      toast.success('Precio actualizado');
      qc.invalidateQueries({ queryKey: ['organizaciones-ingresos'] });
      setEditPrecio(null);
    },
    onError: (e) => {
      const d = e.response?.data?.detail;
      toast.error(Array.isArray(d) ? d.map(x => x.msg).join(', ') : (d || 'Error'));
    },
  });
  const guardarPrecio = () => {
    const v = parseFloat(editPrecio?.valor);
    if (isNaN(v) || v < 0) { toast.error('Precio inválido'); return; }
    precioMut.mutate({ id: editPrecio.id, precio: v });
  };

  const fmtCOP = (v) => new Intl.NumberFormat('es-CO', {
    style: 'currency', currency: 'COP', maximumFractionDigits: 0,
  }).format(v || 0);

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
      qc.invalidateQueries({ queryKey: ['organizaciones-dashboard'] });
      qc.invalidateQueries({ queryKey: ['organizaciones-ingresos'] });
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
      qc.invalidateQueries({ queryKey: ['organizaciones-dashboard'] });
      qc.invalidateQueries({ queryKey: ['organizaciones-ingresos'] });
      setConfirmDel(null);
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  });

  // Segundo login: autenticar como usuario de la organización elegida.
  const entrarOrg = async () => {
    if (!lf.username || !lf.password) { setLErr('Ingresa usuario y contraseña.'); return; }
    setLLoading(true); setLErr('');
    try {
      const { data } = await api.post('/auth/login', {
        username: lf.username, password: lf.password, remember_me: true,
      });
      if (data.rol === 'superadmin') {
        setLErr('Esas son credenciales de superadmin. Usa un usuario de la organización.');
        return;
      }
      if (data.organizacion_id !== loginOrg.id) {
        setLErr('Ese usuario no pertenece a esta organización.');
        return;
      }
      login(data.access_token, {
        username: data.username, nombre: data.nombre, rol: data.rol,
        organizacion_id: data.organizacion_id, cliente_ref: data.cliente_ref,
        ver_detalle: data.ver_detalle,
      }, true);
      toast.success(`Bienvenido a ${loginOrg.nombre}`);
      navigate(data.rol === 'cliente' ? '/portal' : '/');
    } catch (e) {
      setLErr(e.response?.data?.detail || 'Credenciales inválidas');
    } finally {
      setLLoading(false);
    }
  };

  const abrirLoginOrg = (org) => { setLoginOrg(org); setLf({}); setLErr(''); };

  const donutData = dash ? [
    { name: 'Activos', value: dash.totales.activos, color: COLORES_ESTADO.activos },
    { name: 'Suspendidos', value: dash.totales.suspendidos, color: COLORES_ESTADO.suspendidos },
    { name: 'No se encuentran', value: dash.totales.no_encontrados, color: COLORES_ESTADO.no_encontrados },
    { name: 'Otros', value: dash.totales.otros, color: COLORES_ESTADO.otros },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="sa-root">
      <style>{ESTILOS}</style>

      {/* Topbar */}
      <div className="sa-top">
        <div className="sa-brand">
          <div className="sa-logo">V</div>
          <div>
            <div className="sa-brand-name">Validum</div>
            <div className="sa-brand-sub">Consola central</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div className="sa-user">
            <div className="sa-user-name">{user?.nombre}</div>
            <div className="sa-user-rol">Superadministrador</div>
          </div>
          <button className="sa-btn sa-btn--ghost sa-btn--sm" onClick={() => logout().then(() => navigate('/login'))}>
            Cerrar sesión
          </button>
        </div>
      </div>

      {/* Encabezado */}
      <div className="sa-head">
        <div>
          <h1 className="sa-title">Organizaciones</h1>
          <p className="sa-lede">Cada organización opera aislada: sus usuarios, sus afiliados, sus datos.</p>
        </div>
        <button className="sa-btn" onClick={() => { setForm({}); setErr(''); setModal(true); }}>
          + Nueva organización
        </button>
      </div>

      {/* Tabs */}
      <div className="sa-tabs">
        <button className="sa-tab" data-on={tab === 'orgs'} onClick={() => setTab('orgs')}>
          Organizaciones <b>{orgs.length}</b>
        </button>
        <button className="sa-tab" data-on={tab === 'dash'} onClick={() => setTab('dash')}>Dashboard</button>
        <button className="sa-tab" data-on={tab === 'ing'} onClick={() => setTab('ing')}>Ingresos</button>
      </div>

      <div className="sa-main">
        {tab === 'ing' ? (
          /* ═══ INGRESOS ═══ */
          ingError ? (
            <div className="sa-empty"><b>No se pudo cargar</b>
              <button className="sa-btn sa-btn--ghost sa-btn--sm" style={{ marginTop: 12 }} onClick={refetchIng}>Reintentar</button>
            </div>
          ) : !ing ? (
            <div className="sa-empty">Cargando…</div>
          ) : (
            <>
              <div className="sa-tiles">
                <div className="sa-tile sa-tile--dark">
                  <div>
                    <div className="sa-tile-l" style={{ color: '#fff' }}>Ingreso mensual</div>
                    <div className="sa-tile-n">{fmtCOP(ing.totales.ingreso_mensual)}</div>
                    <div className="sa-tile-sub">{ing.totales.afiliados} afiliados facturables</div>
                  </div>
                  <div className="sa-ico">{Ico.money()}</div>
                </div>
                <div className="sa-tile" style={{ animationDelay: '50ms' }}>
                  <div>
                    <div className="sa-tile-l">Proyección anual</div>
                    <div className="sa-tile-n">{fmtCOP(ing.totales.ingreso_anual)}</div>
                    <div className="sa-tile-sub">precio base {fmtCOP(ing.precio_default)}/afiliado</div>
                  </div>
                  <div className="sa-ico">{Ico.money()}</div>
                </div>
                <div className="sa-tile" style={{ animationDelay: '100ms' }}>
                  <div>
                    <div className="sa-tile-l">Afiliados facturables</div>
                    <div className="sa-tile-n">{ing.totales.afiliados}</div>
                    <div className="sa-tile-sub">afiliados activos</div>
                  </div>
                  <div className="sa-ico">{Ico.users()}</div>
                </div>
                <div className="sa-tile" style={{ animationDelay: '150ms' }}>
                  <div>
                    <div className="sa-tile-l">Organizaciones activas</div>
                    <div className="sa-tile-n">{ing.totales.organizaciones_activas}</div>
                    <div className="sa-tile-sub">de {ing.organizaciones.length} en total</div>
                  </div>
                  <div className="sa-ico">{Ico.building()}</div>
                </div>
              </div>
              <div className="sa-tablewrap">
                <div className="sa-tabletitle">Ingresos por organización</div>
                <table className="sa-table">
                  <thead>
                    <tr>{['Organización', 'Afiliados', 'Precio por afiliado', 'Ingreso mensual', 'Proyección anual', ''].map((h, i) => <th key={i}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {ing.organizaciones.map(o => (
                      <tr key={o.id}>
                        <td>
                          <div className="sa-td-name">{o.nombre}</div>
                          <div className="sa-td-slug">{o.slug}{!o.activo && ' · inactiva'}</div>
                        </td>
                        <td>{o.afiliados}</td>
                        <td>
                          {editPrecio?.id === o.id ? (
                            <span className="sa-price">
                              <input
                                className="sa-price-input" autoFocus type="number" min="0" step="1000"
                                value={editPrecio.valor}
                                onChange={e => setEditPrecio(p => ({ ...p, valor: e.target.value }))}
                                onKeyDown={e => { if (e.key === 'Enter') guardarPrecio(); if (e.key === 'Escape') setEditPrecio(null); }}
                              />
                              <button className="sa-price-edit" title="Guardar" onClick={guardarPrecio} disabled={precioMut.isPending}>✓</button>
                              <button className="sa-price-edit" title="Cancelar" onClick={() => setEditPrecio(null)}>✕</button>
                            </span>
                          ) : (
                            <span className="sa-price">
                              <span className="sa-price-v">{fmtCOP(o.precio_afiliado)}</span>
                              <button className="sa-price-edit" title="Modificar precio"
                                      onClick={() => setEditPrecio({ id: o.id, valor: o.precio_afiliado })}>✎</button>
                            </span>
                          )}
                        </td>
                        <td style={{ fontWeight: 800 }}>{fmtCOP(o.ingreso_mensual)}</td>
                        <td style={{ color: 'var(--muted)' }}>{fmtCOP(o.ingreso_anual)}</td>
                        <td>
                          <button className="sa-btn sa-btn--sm" disabled={facturar.isPending}
                                  title={`Emitir factura del mes: ${o.afiliados} afiliados × ${fmtCOP(o.precio_afiliado)}`}
                                  onClick={() => facturar.mutate(o.id)}>
                            Facturar
                          </button>
                        </td>
                      </tr>
                    ))}
                    {ing.organizaciones.length === 0 && (
                      <tr><td colSpan={6} style={{ padding: 46, textAlign: 'center', color: 'var(--muted)' }}>Sin organizaciones aún.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* ── Facturas emitidas ── */}
              {fact && fact.facturas.length > 0 && (
                <div className="sa-tablewrap" style={{ marginTop: 18 }}>
                  <div className="sa-tabletitle" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 24, flexWrap: 'wrap', gap: 8 }}>
                    <span>Facturas emitidas</span>
                    <span style={{ fontSize: 12.5, fontWeight: 700 }}>
                      <span style={{ color: COLORES_ESTADO.suspendidos }}>Pendiente: {fmtCOP(fact.totales.pendiente)}</span>
                      <span style={{ color: 'var(--muted)', margin: '0 8px' }}>·</span>
                      <span style={{ color: COLORES_ESTADO.activos }}>Cobrado: {fmtCOP(fact.totales.pagado)}</span>
                    </span>
                  </div>
                  <table className="sa-table">
                    <thead>
                      <tr>{['Organización', 'Período', 'Afiliados', 'Monto', 'Estado', ''].map((h, i) => <th key={i}>{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {fact.facturas.map(f => (
                        <tr key={f.id}>
                          <td>
                            <div className="sa-td-name">{f.nombre}</div>
                            <div className="sa-td-slug">{f.slug}</div>
                          </td>
                          <td style={{ fontWeight: 700 }}>{f.periodo}</td>
                          <td>{f.afiliados} × {fmtCOP(f.precio)}</td>
                          <td style={{ fontWeight: 800 }}>{fmtCOP(f.monto)}</td>
                          <td>
                            <span className={`sa-chip ${f.estado === 'pagada' ? 'sa-chip--on' : ''}`}
                                  style={f.estado !== 'pagada' ? { color: COLORES_ESTADO.suspendidos, background: 'rgba(224,162,60,.13)' } : {}}>
                              {f.estado === 'pagada' ? 'Pagada' : 'Pendiente'}
                            </span>
                          </td>
                          <td>
                            <span style={{ display: 'inline-flex', gap: 6 }}>
                              {f.estado !== 'pagada' && (
                                <button className="sa-btn sa-btn--ghost sa-btn--sm" onClick={() => pagarFactura.mutate(f.id)}
                                        disabled={pagarFactura.isPending}>
                                  Marcar pagada
                                </button>
                              )}
                              <button className="sa-price-edit" title="Anular factura" onClick={() => anularFactura.mutate(f.id)}>✕</button>
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* ── Resumen mensual (snapshots) ── */}
              {mens && (
                <div className="sa-dash-grid" style={{ marginTop: 18 }}>
                  <div className="sa-tablewrap">
                    <div className="sa-tabletitle" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 24 }}>
                      <span>Resumen mensual · {mens.anio}</span>
                      {mens.anios_disponibles?.length > 1 && (
                        <select className="sa-input" style={{ width: 'auto', padding: '6px 10px', fontSize: 12.5 }}
                                value={mens.anio} onChange={e => setAnioMens(Number(e.target.value))}>
                          {mens.anios_disponibles.map(a => <option key={a} value={a}>{a}</option>)}
                        </select>
                      )}
                    </div>
                    <table className="sa-table" style={{ minWidth: 420 }}>
                      <thead>
                        <tr>{['Mes', 'Afiliados facturados', 'Ingreso'].map(h => <th key={h}>{h}</th>)}</tr>
                      </thead>
                      <tbody>
                        {mens.meses.map(m => (
                          <tr key={m.mes}>
                            <td>
                              <div className="sa-td-name">{m.nombre}</div>
                              <div className="sa-td-slug">
                                {m.organizaciones.map(o => `${o.nombre}: ${o.afiliados}`).join(' · ')}
                              </div>
                            </td>
                            <td style={{ fontWeight: 800 }}>{m.afiliados}</td>
                            <td style={{ fontWeight: 800 }}>{fmtCOP(m.ingreso)}</td>
                          </tr>
                        ))}
                        {mens.meses.length === 0 && (
                          <tr><td colSpan={3} style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>Sin datos para {mens.anio}.</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="sa-card">
                    <div style={{ fontSize: 15.5, fontWeight: 800, marginBottom: 12 }}>Afiliados por mes</div>
                    {mens.meses.length === 0 ? (
                      <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>Sin datos aún.</div>
                    ) : (
                      <div style={{ height: 220 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={mens.meses} barSize={22}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#EDEFF2" vertical={false} />
                            <XAxis dataKey="nombre" tickFormatter={v => v.slice(0, 3)} tick={{ fontSize: 11, fontFamily: 'Figtree', fill: '#8A9099' }} axisLine={false} tickLine={false} />
                            <YAxis allowDecimals={false} tick={{ fontSize: 11, fontFamily: 'Figtree', fill: '#8A9099' }} axisLine={false} tickLine={false} width={30} />
                            <ReTooltip formatter={(v, n) => [v, n === 'afiliados' ? 'Afiliados' : n]}
                                       labelStyle={{ fontWeight: 700 }}
                                       contentStyle={{ borderRadius: 10, border: '1px solid #E9EBEF', fontSize: 12, fontFamily: 'Figtree' }} />
                            <Bar dataKey="afiliados" fill="#2B2D31" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                    <p style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 10, marginBottom: 0 }}>
                      El mes en curso se actualiza en vivo; los meses anteriores quedan congelados con lo facturado.
                    </p>
                  </div>
                </div>
              )}
            </>
          )
        ) : tab === 'dash' ? (
          /* ═══ DASHBOARD ═══ */
          dashError ? (
            <div className="sa-empty"><b>No se pudo cargar</b>
              <button className="sa-btn sa-btn--ghost sa-btn--sm" style={{ marginTop: 12 }} onClick={refetchDash}>Reintentar</button>
            </div>
          ) : !dash ? (
            <div className="sa-empty">Cargando…</div>
          ) : (
            <>
              <div className="sa-tiles">
                <div className="sa-tile sa-tile--dark">
                  <div>
                    <div className="sa-tile-l" style={{ color: '#fff' }}>Total afiliados</div>
                    <div className="sa-tile-n">{dash.totales.total}</div>
                    <div className="sa-tile-sub">{dash.totales.usuarios} usuarios en el sistema</div>
                  </div>
                  <div className="sa-ico">{Ico.users()}</div>
                </div>
                <div className="sa-tile" style={{ animationDelay: '50ms' }}>
                  <div>
                    <div className="sa-tile-l">Activos</div>
                    <div className="sa-tile-n" style={{ color: COLORES_ESTADO.activos }}>{dash.totales.activos}</div>
                  </div>
                  <div className="sa-ico" style={{ background: 'rgba(63,169,110,.12)', color: COLORES_ESTADO.activos }}>{Ico.check()}</div>
                </div>
                <div className="sa-tile" style={{ animationDelay: '100ms' }}>
                  <div>
                    <div className="sa-tile-l">Suspendidos</div>
                    <div className="sa-tile-n" style={{ color: COLORES_ESTADO.suspendidos }}>{dash.totales.suspendidos}</div>
                  </div>
                  <div className="sa-ico" style={{ background: 'rgba(224,162,60,.13)', color: COLORES_ESTADO.suspendidos }}>{Ico.pause()}</div>
                </div>
                <div className="sa-tile" style={{ animationDelay: '150ms' }}>
                  <div>
                    <div className="sa-tile-l">No se encuentran</div>
                    <div className="sa-tile-n" style={{ color: COLORES_ESTADO.no_encontrados }}>{dash.totales.no_encontrados}</div>
                  </div>
                  <div className="sa-ico" style={{ background: 'rgba(217,105,92,.12)', color: COLORES_ESTADO.no_encontrados }}>{Ico.alert()}</div>
                </div>
              </div>

              <div className="sa-dash-grid">
                <div className="sa-tablewrap">
                  <div className="sa-tabletitle">Estados por organización</div>
                  <table className="sa-table">
                    <thead>
                      <tr>{['Organización', 'Afiliados', 'Activos', 'Suspendidos', 'No se encuentran', 'Otros', 'Usuarios'].map(h => <th key={h}>{h}</th>)}</tr>
                    </thead>
                    <tbody>
                      {dash.organizaciones.map(o => (
                        <tr key={o.id}>
                          <td>
                            <div className="sa-td-name">{o.nombre}</div>
                            <div className="sa-td-slug">{o.slug}{!o.activo && ' · inactiva'}</div>
                          </td>
                          <td style={{ fontWeight: 800 }}>{o.total}</td>
                          <td><span className="sa-badge-n" style={{ color: COLORES_ESTADO.activos, background: 'rgba(63,169,110,.1)' }}>{o.activos}</span></td>
                          <td><span className="sa-badge-n" style={{ color: COLORES_ESTADO.suspendidos, background: 'rgba(224,162,60,.12)' }}>{o.suspendidos}</span></td>
                          <td><span className="sa-badge-n" style={{ color: COLORES_ESTADO.no_encontrados, background: 'rgba(217,105,92,.1)' }}>{o.no_encontrados}</span></td>
                          <td style={{ color: 'var(--muted)' }} title={Object.entries(o.detalle || {}).map(([k, v]) => `${k}: ${v}`).join('\n')}>{o.otros}</td>
                          <td style={{ color: 'var(--muted)' }}>{o.usuarios}</td>
                        </tr>
                      ))}
                      {dash.organizaciones.length === 0 && (
                        <tr><td colSpan={7} style={{ padding: 46, textAlign: 'center', color: 'var(--muted)' }}>Sin organizaciones aún.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="sa-card" style={{ animationDelay: '100ms' }}>
                  <div style={{ fontSize: 15.5, fontWeight: 800, marginBottom: 4 }}>Distribución de estados</div>
                  {donutData.length === 0 ? (
                    <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
                      Sin afiliados registrados aún.
                    </div>
                  ) : (
                    <>
                      <div style={{ height: 190 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie data={donutData} dataKey="value" nameKey="name"
                                 innerRadius={55} outerRadius={82} paddingAngle={3} strokeWidth={0}>
                              {donutData.map(d => <Cell key={d.name} fill={d.color} />)}
                            </Pie>
                            <ReTooltip formatter={(v, n) => [v, n]} contentStyle={{ borderRadius: 10, border: '1px solid #E9EBEF', fontSize: 12, fontFamily: 'Figtree' }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="sa-legend">
                        {donutData.map(d => (
                          <div key={d.name} className="sa-legend-item">
                            <span className="sa-legend-dot" style={{ background: d.color }} />
                            {d.name}
                            <span className="sa-legend-n">{d.value}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </>
          )
        ) : (
          /* ═══ ORGANIZACIONES ═══ */
          isError ? (
            <div className="sa-empty"><b>No se pudieron cargar</b>
              <button className="sa-btn sa-btn--ghost sa-btn--sm" style={{ marginTop: 12 }} onClick={refetch}>Reintentar</button>
            </div>
          ) : orgs.length === 0 ? (
            <div className="sa-empty">
              <b>Aún no hay organizaciones</b>
              Crea la primera para empezar a operar.
            </div>
          ) : (
            <div className="sa-grid">
              {orgs.map((org, i) => (
                <div key={org.id} className="sa-card" style={{ animationDelay: `${i * 60}ms` }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                      <div className="sa-ico" style={{ borderRadius: 12 }}>{Ico.building()}</div>
                      <div style={{ minWidth: 0 }}>
                        <div className="sa-card-name">{org.nombre}</div>
                        <div className="sa-card-slug">/{org.slug}</div>
                      </div>
                    </div>
                    <span className={`sa-chip ${org.activo ? 'sa-chip--on' : 'sa-chip--off'}`}>
                      {org.activo ? 'Activa' : 'Inactiva'}
                    </span>
                  </div>
                  <div className="sa-card-stats">
                    <div>
                      <div className="sa-stat-n">{org.total_usuarios ?? 0}</div>
                      <div className="sa-stat-l">Usuarios</div>
                    </div>
                    <div>
                      <div className="sa-stat-n">{org.total_afiliados ?? 0}</div>
                      <div className="sa-stat-l">Afiliados</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button className="sa-btn sa-btn--sm" onClick={() => abrirLoginOrg(org)} disabled={!org.activo}>Entrar</button>
                    <button className="sa-btn sa-btn--ghost sa-btn--sm" onClick={() => toggleActivo.mutate(org)}>
                      {org.activo ? 'Desactivar' : 'Activar'}
                    </button>
                    <button className="sa-btn sa-btn--danger sa-btn--sm" onClick={() => setConfirmDel(org)}>Eliminar</button>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* ── Modal: crear organización ── */}
      {modal && (
        <div className="sa-overlay" onClick={() => setModal(false)}>
          <div className="sa-modal" onClick={e => e.stopPropagation()}>
            <h2 className="sa-modal-title">Nueva organización</h2>
            <p className="sa-modal-sub">Se crea la organización con su configuración base y su usuario administrador inicial.</p>
            {err && <div className="sa-err">{err}</div>}
            <div className="sa-field">
              <label className="sa-label">Nombre de la organización *</label>
              <input className="sa-input" value={form.nombre || ''} onChange={e => sf('nombre', e.target.value)} placeholder="Ej: Contadores del Valle S.A.S" />
            </div>
            <div className="sa-field">
              <label className="sa-label">Slug (opcional)</label>
              <input className="sa-input" value={form.slug || ''} onChange={e => sf('slug', e.target.value)} placeholder="se genera del nombre" />
            </div>
            <div className="sa-divider">Administrador inicial</div>
            <div className="sa-field">
              <label className="sa-label">Nombre del admin</label>
              <input className="sa-input" value={form.admin_nombre || ''} onChange={e => sf('admin_nombre', e.target.value)} placeholder="opcional" />
            </div>
            <div className="sa-field">
              <label className="sa-label">Usuario (login) *</label>
              <input className="sa-input" value={form.admin_username || ''} onChange={e => sf('admin_username', e.target.value)} placeholder="único en todo el sistema" />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div className="sa-field" style={{ flex: 1 }}>
                <label className="sa-label">Contraseña *</label>
                <input type="password" className="sa-input" value={form.admin_password || ''} onChange={e => sf('admin_password', e.target.value)} />
              </div>
              <div className="sa-field" style={{ flex: 1 }}>
                <label className="sa-label">Confirmar *</label>
                <input type="password" className="sa-input" value={form.admin_password2 || ''} onChange={e => sf('admin_password2', e.target.value)} />
              </div>
            </div>
            <div className="sa-actions">
              <button className="sa-btn sa-btn--ghost" onClick={() => setModal(false)}>Cancelar</button>
              <button className="sa-btn" onClick={() => crear.mutate()} disabled={crear.isPending}>
                {crear.isPending ? 'Creando…' : 'Crear organización'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: segundo login (entrar a organización) ── */}
      {loginOrg && (
        <div className="sa-overlay" onClick={() => setLoginOrg(null)}>
          <div className="sa-modal" style={{ width: 400 }} onClick={e => e.stopPropagation()}>
            <h2 className="sa-modal-title">Entrar a {loginOrg.nombre}</h2>
            <p className="sa-modal-sub">Inicia sesión con un usuario (admin o empleado) de esta organización.</p>
            {lErr && <div className="sa-err">{lErr}</div>}
            <form onSubmit={(e) => { e.preventDefault(); entrarOrg(); }}>
              <div className="sa-field">
                <label className="sa-label">Usuario</label>
                <input className="sa-input" autoFocus value={lf.username || ''} onChange={e => setLf(f => ({ ...f, username: e.target.value }))} />
              </div>
              <div className="sa-field">
                <label className="sa-label">Contraseña</label>
                <input type="password" className="sa-input" value={lf.password || ''} onChange={e => setLf(f => ({ ...f, password: e.target.value }))} />
              </div>
              <div className="sa-actions">
                <button type="button" className="sa-btn sa-btn--ghost" onClick={() => setLoginOrg(null)}>Cancelar</button>
                <button type="submit" className="sa-btn" disabled={lLoading}>{lLoading ? 'Entrando…' : 'Entrar'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: confirmar eliminación ── */}
      {confirmDel && (
        <div className="sa-overlay" onClick={() => setConfirmDel(null)}>
          <div className="sa-modal" style={{ width: 420 }} onClick={e => e.stopPropagation()}>
            <h2 className="sa-modal-title">¿Eliminar {confirmDel.nombre}?</h2>
            <p className="sa-modal-sub">
              Se eliminarán TODOS sus datos: usuarios, afiliados, facturas, configuración.
              Esta acción no se puede deshacer.
            </p>
            <div className="sa-actions">
              <button className="sa-btn sa-btn--ghost" onClick={() => setConfirmDel(null)}>Cancelar</button>
              <button className="sa-btn sa-btn--danger" style={{ borderColor: 'rgba(217,105,92,.4)' }}
                      onClick={() => eliminar.mutate(confirmDel.id)} disabled={eliminar.isPending}>
                {eliminar.isPending ? 'Eliminando…' : 'Eliminar todo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
