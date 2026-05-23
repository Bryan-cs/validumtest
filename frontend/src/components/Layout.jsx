import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../hooks/useAuth';
import useInactivity from '../hooks/useInactivity';
import api from '../utils/api';
import { playBeep } from '../utils/audio';
import WelcomeModal from './WelcomeModal';
import useAppBadge from '../hooks/useAppBadge';


const SIDEBAR_MIN = 48;
const SIDEBAR_MAX = 380;
const SIDEBAR_DEFAULT = 220;

const PALETTES = [
  { id: 'indigo',   label: 'Índigo',    dot: '#4F46E5' },
  { id: 'ocean',    label: 'Oceánico',   dot: '#0891B2' },
  { id: 'emerald',  label: 'Esmeralda',  dot: '#059669' },
  { id: 'lavender', label: 'Lavanda',    dot: '#7C3AED' },
  { id: 'slate',    label: 'Slate',      dot: '#475569' },
];

const navGroups = (rol) => [
  {
    id: 'principal',
    label: null,
    items: [
      { to: '/', label: '🏠 Dashboard' },
    ],
  },
  {
    id: 'operaciones',
    label: 'OPERACIONES',
    items: [
      { to: '/afiliados',   label: '👥 Afiliados' },
      { to: '/retiros',     label: '↪️ Retiros' },
      { to: '/tareas',      label: '✅ Tareas' },
    ],
  },
  {
    id: 'finanzas',
    label: 'FINANZAS',
    items: [
      { to: '/facturacion',  label: '🧾 Facturación' },
      ...(rol === 'admin' ? [{ to: '/finanzas', label: '📊 Reportes Financieros' }] : []),
      { to: '/cobro',        label: '💰 Cobro' },
      { to: '/planillas-ss', label: '📋 Planillas SS' },
    ],
  },
  ...(rol !== 'cliente' ? [
    {
      id: 'clientes',
      label: 'CLIENTES',
      items: [
        { to: '/novedades-clientes', label: '📬 Novedades clientes' },
      ],
    },
  ] : []),
  ...(rol === 'admin' ? [
    {
      id: 'configuracion',
      label: 'CONFIGURACIÓN',
      items: [
        { to: '/usuarios',           label: '⚙️ Usuarios' },
        { to: '/empleados',          label: '👔 Empleados' },
        { to: '/listas',             label: '📋 Listas' },
        { to: '/calculadora',        label: '🧮 Calculadora' },
      ],
    },
    {
      id: 'gestion',
      label: 'GESTIÓN',
      items: [
        { to: '/actividad', label: '📜 Actividad' },
      ],
    },
  ] : []),
];

function tiempoRelativo(fechaStr) {
  if (!fechaStr) return '';
  const normalized = fechaStr.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(fechaStr) ? fechaStr : fechaStr + 'Z';
  const d = new Date(normalized);
  const diff = Date.now() - d.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return 'ahora';
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h}h`;
  const dias = Math.floor(h / 24);
  if (dias < 7) return `hace ${dias}d`;
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' });
}

function tipoNotif(n) {
  if (n.tarea_id) return { icon: '🔧', color: '#0EA5E9', bg: 'rgba(14,165,233,.13)', label: 'Tarea', ruta: '/tareas' };
  const m = (n.mensaje || '').toLowerCase();
  if (m.includes('novedad ss') || m.includes('novedad de pago'))
    return { icon: '📋', color: '#10B981', bg: 'rgba(16,185,129,.13)', label: 'Nov. SS', ruta: '/novedades-clientes' };
  if (m.includes('retiro'))
    return { icon: '↩️', color: '#F59E0B', bg: 'rgba(245,158,11,.13)', label: 'Retiro', ruta: '/novedades-clientes' };
  if (m.includes('aviso'))
    return { icon: '📢', color: '#F59E0B', bg: 'rgba(245,158,11,.13)', label: 'Aviso', ruta: '/novedades-clientes' };
  if (m.includes('novedad'))
    return { icon: '👤', color: '#8B5CF6', bg: 'rgba(139,92,246,.13)', label: 'Novedad', ruta: '/novedades-clientes' };
  return { icon: '🔔', color: '#6366F1', bg: 'rgba(99,102,241,.13)', label: 'Info', ruta: '/novedades-clientes' };
}

export default function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [width, setWidth] = useState(SIDEBAR_DEFAULT);
  const [showNotifs, setShowNotifs] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark');
  const [palette, setPalette] = useState(() => localStorage.getItem('palette') || 'indigo');
  const [showPalette, setShowPalette] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const dragging = useRef(false);

  // ── Mobile detection ───────────────────────────────────────────────────────
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);

  useEffect(() => {
    document.documentElement.setAttribute('data-palette', palette);
    localStorage.setItem('palette', palette);
  }, [palette]);

  // WelcomeModal — una vez por sesión por usuario (no para clientes)
  useEffect(() => {
    if (!user?.username || user?.rol === 'cliente') return;
    const key = `bbc_welcome_${user.username}`;
    if (!sessionStorage.getItem(key)) {
      setShowWelcome(true);
    }
  }, [user?.username, user?.rol]);

  const closeWelcome = () => {
    sessionStorage.setItem(`bbc_welcome_${user.username}`, '1');
    setShowWelcome(false);
  };

  const startX = useRef(0);
  const startW = useRef(0);

  const collapsed = width <= SIDEBAR_MIN + 10;

  const { data: notifs = [] } = useQuery({
    queryKey: ['notificaciones'],
    queryFn: () => api.get('/tareas/notificaciones').then(r => r.data),
    refetchInterval: 60_000,
  });
  const noLeidas = notifs.filter(n => !n.leida).length;
  const noLeidasPortal = notifs.filter(n => !n.leida && !n.tarea_id).length;
  const prevNoLeidas = useRef(noLeidas);

  useEffect(() => {
    if (noLeidas > prevNoLeidas.current) playBeep(880, 0.4, 0.3);
    prevNoLeidas.current = noLeidas;
  }, [noLeidas]);

  useAppBadge(noLeidas);

  const abrirNotifs = () => setShowNotifs(v => !v);

  const marcarTodasLeidas = () => {
    api.put('/tareas/notificaciones/leer').then(() =>
      qc.invalidateQueries({ queryKey: ['notificaciones'] })
    ).catch(() => {});
  };

  const marcarUnaLeida = (id) => {
    qc.setQueryData(['notificaciones'], prev =>
      (prev || []).map(n => n.id === id ? { ...n, leida: true } : n)
    );
    api.put(`/tareas/notificaciones/${id}/leer`).catch(() =>
      qc.invalidateQueries({ queryKey: ['notificaciones'] })
    );
  };

  const gruposNotifs = useMemo(() => {
    const map = new Map();
    (notifs || []).forEach(n => {
      if (map.has(n.mensaje)) {
        const g = map.get(n.mensaje);
        g.count++;
        g.ids.push(n.id);
        if (!n.leida) g.alguna_no_leida = true;
      } else {
        map.set(n.mensaje, { ...n, count: 1, ids: [n.id], alguna_no_leida: !n.leida });
      }
    });
    return [...map.values()].sort((a, b) => new Date(b.creado) - new Date(a.creado));
  }, [notifs]);

  // ── Drag handlers ──────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = width;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [width]);

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!dragging.current) return;
      const delta = e.clientX - startX.current;
      const newW = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, startW.current + delta));
      setWidth(newW);
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setWidth(w => w < 80 ? SIDEBAR_MIN : w);
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  const [collapsedGroups, setCollapsedGroups] = useState(() => {
    try { return JSON.parse(localStorage.getItem('sb-collapsed-groups') || '{}'); }
    catch { return {}; }
  });
  const toggleGroup = useCallback((id) => {
    setCollapsedGroups(prev => {
      const next = { ...prev, [id]: !prev[id] };
      localStorage.setItem('sb-collapsed-groups', JSON.stringify(next));
      return next;
    });
  }, []);

  const handleLogout = useCallback(async () => {
    if (user?.username) sessionStorage.removeItem(`bbc_welcome_${user.username}`);
    await logout();
    navigate('/login');
  }, [logout, navigate, user?.username]);
  const { showWarning, extender } = useInactivity(handleLogout);
  const groups = navGroups(user?.rol);

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: "'DM Sans', system-ui, sans-serif", overflow: 'hidden' }}>
    <style>{`
      @keyframes status-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50%       { opacity: .45; transform: scale(.7); }
      }
      .status-dot-activo {
        display: inline-block;
        width: 6px; height: 6px; border-radius: 50%;
        background: var(--c-green);
        margin-right: 5px;
        vertical-align: middle;
        animation: status-pulse 1.8s ease-in-out infinite;
      }
      /* ── Global UI enhancements ── */
      .stat-card-lift { transition: transform .2s, box-shadow .2s; }
      .stat-card-lift:hover { transform: translateY(-3px); box-shadow: 0 8px 28px rgba(0,0,0,.1) !important; }

      .btn-lift { transition: transform .15s, box-shadow .15s, background .15s, border-color .15s !important; }
      .btn-lift:hover:not(:disabled) { transform: translateY(-1px) !important; filter: brightness(1.06); }
      .btn-lift:active:not(:disabled) { transform: scale(.97) !important; }

      .ui-input:focus,
      input:focus, select:focus, textarea:focus {
        border-color: var(--c-primary) !important;
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--c-primary) 15%, transparent) !important;
        outline: none !important;
      }

      .tbl tbody tr { transition: background .1s; cursor: pointer; }
      .tbl tbody tr:nth-child(even) td { background: var(--c-surface2); }
      .tbl tbody tr:hover td { background: var(--c-blue-bg) !important; }
      .tbl tbody tr:hover td:first-child { box-shadow: inset 3px 0 0 var(--c-primary); }
      .tbl tbody tr:last-child td { border-bottom: none !important; }

      /* ── Sidebar items ── */
      .sb-item { transition: background .15s, color .15s; }
      .sb-item:hover { background: #1F2937 !important; color: #F9FAFB !important; }
      .sb-item.active::before {
        content: '';
        position: absolute; left: -8px; top: 50%; transform: translateY(-50%);
        width: 3px; height: 60%;
        background: #F9FAFB;
        border-radius: 0 2px 2px 0;
      }

      /* ── Mobile sidebar ── */
      .sb-mobile {
        transform: translateX(-100%);
        transition: transform .25s cubic-bezier(.4,0,.2,1);
      }
      .sb-mobile.open { transform: translateX(0); }
    `}</style>

      {/* Backdrop mobile */}
      {isMobile && mobileOpen && (
        <div onClick={() => setMobileOpen(false)} style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,.55)', zIndex: 1000,
        }} />
      )}

      {/* Sidebar */}
      <aside
        className={isMobile ? `sb-mobile${mobileOpen ? ' open' : ''}` : ''}
        style={{
          width: isMobile ? 260 : width,
          minWidth: isMobile ? 260 : width,
          maxWidth: isMobile ? 260 : width,
          background: '#111827', borderRight: '1px solid #1F2937', display: 'flex', flexDirection: 'column',
          position: isMobile ? 'fixed' : 'relative',
          top: 0, left: 0, height: '100vh',
          zIndex: isMobile ? 1001 : 'auto',
          flexShrink: 0, overflow: 'hidden',
        }}>
        {/* Logo */}
        <div style={{ padding: collapsed ? '14px 0 16px' : '14px 16px 16px', display:'flex', alignItems:'center', gap:10, whiteSpace:'nowrap', overflow:'hidden', justifyContent: collapsed ? 'center' : 'flex-start' }}>
          <div style={{ width:30, height:30, borderRadius:8, background:'linear-gradient(135deg,#f9fafb,#d1d5db)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:800, color:'#111827', flexShrink:0 }}>BB</div>
          {!collapsed && (
            <span style={{ fontFamily:"'Syne', sans-serif", fontSize:16, fontWeight:800, color:'#F9FAFB', letterSpacing:'-.3px' }}>
              BBC File
            </span>
          )}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', paddingBottom: 12 }}>
          {groups.map((group) => {
            const isGroupCollapsed = !collapsed && !!collapsedGroups[group.id];
            return (
              <React.Fragment key={group.id}>
                {/* Group header */}
                {group.label && !collapsed && (
                  <button
                    onClick={() => toggleGroup(group.id)}
                    style={{
                      width: '100%', background: 'none', border: 'none', cursor: 'pointer',
                      fontSize: 11, color: '#6366F1', padding: '16px 18px 5px',
                      fontWeight: 800, letterSpacing: '.18em', whiteSpace: 'nowrap',
                      display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left',
                    }}
                  >
                    {group.label}
                    <span style={{ flex: 1, height: 1, borderTop: '1px solid #1F2937' }} />
                    <span style={{ fontSize: 8, color: '#4B5563', transition: 'transform .2s', display: 'inline-block', transform: isGroupCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>▼</span>
                  </button>
                )}
                {/* Collapsed sidebar: thin separator between groups */}
                {group.label && collapsed && (
                  <div style={{ margin: '6px 10px', borderTop: '1px solid #1F2937' }} />
                )}
                {/* Group items */}
                {!isGroupCollapsed && group.items.map((item) => {
                  const isNovClientes = item.to === '/novedades-clientes';
                  const showDot = isNovClientes && noLeidasPortal > 0;
                  return (
                    <NavLink key={item.to} to={item.to} end={item.to === '/'}
                      title={collapsed ? item.label : undefined}
                      onClick={() => isMobile && setMobileOpen(false)}
                      className={({ isActive }) => ['sb-item', isActive ? 'active' : ''].filter(Boolean).join(' ')}
                      style={({ isActive }) => ({
                        display: 'flex', alignItems: 'center', position: 'relative',
                        padding: collapsed ? '10px 0' : '9px 10px',
                        margin: '1px 8px', borderRadius: 9, textDecoration: 'none', fontSize: 13.5,
                        color: isActive ? '#F9FAFB' : '#D1D5DB',
                        background: isActive ? '#1F2937' : 'transparent',
                        fontWeight: isActive ? 700 : 500,
                        justifyContent: collapsed ? 'center' : 'flex-start',
                        whiteSpace: 'nowrap', overflow: 'hidden',
                      })}>
                      <span style={{ fontSize: collapsed ? 15 : 13, flexShrink: 0, position: 'relative' }}>
                        {item.label.split(' ')[0]}
                        {showDot && collapsed && (
                          <span className="bbc-notif-dot" style={{
                            position: 'absolute', top: -2, right: -3,
                            width: 7, height: 7, borderRadius: '50%',
                            background: '#EF4444', display: 'block',
                          }} />
                        )}
                      </span>
                      {!collapsed && (
                        <span style={{ marginLeft: 8, overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>
                          {item.label.split(' ').slice(1).join(' ')}
                        </span>
                      )}
                      {showDot && !collapsed && (
                        <span className="bbc-notif-dot" style={{
                          marginLeft: 'auto', marginRight: 4,
                          background: '#EF4444', color: '#fff',
                          borderRadius: 10, padding: '1px 6px',
                          fontSize: 10, fontWeight: 700, flexShrink: 0,
                        }}>
                          {noLeidas}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </React.Fragment>
            );
          })}
        </nav>

        {/* Notificaciones */}
        <div style={{ position: 'relative', padding: '6px 14px', borderTop: '1px solid #1F2937', display: 'flex', alignItems: 'center', gap: 6 }}>
          <button onClick={abrirNotifs}
            className={noLeidas > 0 ? 'bbc-notif-pulse' : ''}
            style={{
              background: noLeidas > 0 ? 'rgba(229,62,62,.15)' : 'none',
              border: noLeidas > 0 ? '1px solid rgba(229,62,62,.35)' : '1px solid transparent',
              borderRadius: 8,
              color: noLeidas > 0 ? '#FCA5A5' : 'rgba(255,255,255,.8)',
              cursor: 'pointer', fontSize: 22, position: 'relative', padding: '5px 8px', flexShrink: 0,
              transition: 'all .2s',
            }}>
            🔔
            {noLeidas > 0 && (
              <span style={{
                position: 'absolute', top: -2, right: -2,
                background: '#E53E3E', color: 'white', borderRadius: '50%',
                width: 18, height: 18, fontSize: 10, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 0 2px #111827',
              }}>
                {noLeidas > 9 ? '9+' : noLeidas}
              </span>
            )}
          </button>
          {!collapsed && <span style={{ color: 'rgba(255,255,255,.5)', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden' }}>Notificaciones</span>}

          {showNotifs && (
            <div style={{
              position: 'fixed', bottom: 70, left: Math.min(width + 8, 16),
              width: 'clamp(300px, 35vw, 460px)',
              background: 'var(--c-surface)', borderRadius: 12,
              boxShadow: '0 12px 40px rgba(0,0,0,.3)', zIndex: 9999,
              maxHeight: 'min(520px, 75vh)', display: 'flex', flexDirection: 'column',
              border: '1px solid var(--c-border)',
            }}>
              {/* Header */}
              <div style={{ padding: '12px 16px', fontWeight: 700, fontSize: 14, borderBottom: '1px solid var(--c-border)', color: 'var(--c-text)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <span>🔔 Notificaciones {gruposNotifs.length > 0 && <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--c-text2)' }}>({gruposNotifs.length})</span>}</span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  {noLeidas > 0 && (
                    <button onClick={marcarTodasLeidas} style={{ background: 'var(--c-green-bg)', border: 'none', cursor: 'pointer', color: 'var(--c-green)', fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 6 }}>
                      ✓ Todas leídas
                    </button>
                  )}
                  {gruposNotifs.length > 0 && (
                    <button onClick={() => {
                      api.delete('/tareas/notificaciones').then(() =>
                        qc.invalidateQueries({ queryKey: ['notificaciones'] })
                      ).catch(() => {});
                    }} style={{ background: 'var(--c-red-bg)', border: 'none', cursor: 'pointer', color: 'var(--c-red)', fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 6 }}>
                      Limpiar
                    </button>
                  )}
                  <button onClick={() => setShowNotifs(false)} style={{
                    background: 'var(--c-surface2)', border: '1px solid var(--c-border)',
                    cursor: 'pointer', color: 'var(--c-text)', fontSize: 18, fontWeight: 700,
                    width: 30, height: 30, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
                  }}>×</button>
                </div>
              </div>
              {/* Lista */}
              <div style={{ overflowY: 'auto', flex: 1 }}>
                {gruposNotifs.length === 0
                  ? <p style={{ padding: '24px 16px', color: 'var(--c-text2)', fontSize: 13, margin: 0, textAlign: 'center' }}>Sin notificaciones nuevas</p>
                  : gruposNotifs.map(g => {
                    const tipo = tipoNotif(g);
                    return (
                      <div key={g.id} style={{
                        padding: '11px 14px', borderBottom: '1px solid var(--c-border)',
                        background: g.alguna_no_leida ? tipo.bg : 'transparent',
                        display: 'flex', gap: 10, alignItems: 'flex-start',
                        cursor: 'pointer', transition: 'background .15s',
                      }}
                        onClick={() => { navigate(tipo.ruta); setShowNotifs(false); }}
                      >
                        {/* Icono tipo */}
                        <div style={{
                          width: 34, height: 34, borderRadius: 8, flexShrink: 0,
                          background: tipo.bg, border: `1px solid ${tipo.color}30`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
                        }}>
                          {tipo.icon}
                        </div>
                        {/* Contenido */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2, flexWrap: 'wrap' }}>
                            <span style={{ fontSize: 10, fontWeight: 700, color: tipo.color, background: tipo.bg, border: `1px solid ${tipo.color}30`, borderRadius: 4, padding: '1px 6px', letterSpacing: '.03em' }}>
                              {tipo.label}
                            </span>
                            {g.count > 1 && (
                              <span style={{ fontSize: 10, fontWeight: 700, color: '#fff', background: '#6366F1', borderRadius: 10, padding: '1px 6px' }}>
                                ×{g.count}
                              </span>
                            )}
                            {g.alguna_no_leida && (
                              <span style={{ width: 6, height: 6, borderRadius: '50%', background: tipo.color, display: 'inline-block' }} />
                            )}
                          </div>
                          <div style={{ color: 'var(--c-text)', fontSize: 12.5, lineHeight: 1.45, wordBreak: 'break-word' }}>{g.mensaje}</div>
                          <div style={{ color: 'var(--c-text2)', fontSize: 11, marginTop: 3 }}>{tiempoRelativo(g.creado)}</div>
                        </div>
                        {/* Marcar leída */}
                        {g.alguna_no_leida && (
                          <button
                            onClick={e => { e.stopPropagation(); g.ids.forEach(id => marcarUnaLeida(id)); }}
                            title="Marcar como leída"
                            style={{
                              flexShrink: 0, width: 26, height: 26, borderRadius: 6,
                              background: 'var(--c-surface2)', border: `1px solid ${tipo.color}40`,
                              color: tipo.color, fontSize: 13, fontWeight: 700,
                              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                              marginTop: 2,
                            }}>✓</button>
                        )}
                      </div>
                    );
                  })
                }
              </div>
            </div>
          )}
        </div>

        {/* Usuario + controles */}
        <div style={{ padding: '12px 14px', borderTop: '1px solid #1F2937' }}>
          {/* Avatar + info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, overflow: 'hidden' }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%', background: '#374151',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 700, color: '#F9FAFB', flexShrink: 0,
            }}>
              {user?.nombre?.charAt(0)?.toUpperCase() || '?'}
            </div>
            {!collapsed && (
              <div style={{ minWidth: 0, overflow: 'hidden' }}>
                <div style={{ color: '#F9FAFB', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.nombre}
                </div>
                <div style={{ color: '#9CA3AF', fontSize: 10, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.rol?.toUpperCase()}
                </div>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
            <button onClick={() => setDark(d => !d)} title={dark ? 'Modo claro' : 'Modo oscuro'} style={{
              flex: 1, padding: '5px 8px', background: 'rgba(255,255,255,.1)',
              border: '1px solid rgba(255,255,255,.2)', borderRadius: 6,
              color: '#fff', fontSize: 14, cursor: 'pointer',
            }}>
              {dark ? '☀️' : '🌙'}{!collapsed && <span style={{ fontSize: 11, marginLeft: 4 }}>{dark ? 'Claro' : 'Oscuro'}</span>}
            </button>
            {/* Selector de paleta */}
            <div style={{ position: 'relative' }}>
              <button onClick={() => setShowPalette(v => !v)} title="Cambiar paleta de colores" style={{
                padding: '5px 8px', background: 'rgba(255,255,255,.1)',
                border: '1px solid rgba(255,255,255,.2)', borderRadius: 6,
                color: '#fff', fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
              }}>
                🎨{!collapsed && <span style={{ fontSize: 11 }}>Tema</span>}
              </button>
              {showPalette && (
                <div style={{
                  position: 'absolute', bottom: '100%', left: 0, marginBottom: 6,
                  background: 'var(--c-surface)', borderRadius: 10, padding: 8,
                  boxShadow: '0 8px 30px rgba(0,0,0,.3)', zIndex: 9999,
                  border: '1px solid var(--c-border)', minWidth: 160,
                }}>
                  {PALETTES.map(p => (
                    <button key={p.id} onClick={() => { setPalette(p.id); setShowPalette(false); }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                        padding: '7px 10px', border: 'none', borderRadius: 6, cursor: 'pointer',
                        background: palette === p.id ? 'var(--c-surface2)' : 'transparent',
                        fontSize: 12, color: 'var(--c-text)', fontWeight: palette === p.id ? 700 : 400,
                      }}>
                      <span style={{
                        width: 14, height: 14, borderRadius: '50%', background: p.dot,
                        border: palette === p.id ? '2px solid var(--c-text)' : '2px solid transparent',
                        flexShrink: 0,
                      }} />
                      {p.label}
                      {palette === p.id && <span style={{ marginLeft: 'auto', fontSize: 11 }}>✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button onClick={handleLogout} title="Cerrar sesión" style={{
            width: '100%', padding: '7px 10px', background: 'rgba(255,255,255,.1)',
            border: '1px solid rgba(255,255,255,.2)', borderRadius: 6,
            color: '#fff', fontSize: 12, cursor: 'pointer',
          }}>
            {collapsed ? '↩' : 'Cerrar sesión'}
          </button>
        </div>

        {/* ── Handle de redimensión (solo desktop) ──────────────────────── */}
        {!isMobile && <div
          onMouseDown={onMouseDown}
          title="Arrastra para redimensionar"
          style={{
            position: 'absolute', top: 0, right: 0,
            width: 5, height: '100%', cursor: 'col-resize',
            background: 'transparent',
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(232,155,42,.5)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        />}
      </aside>

      {/* Panel principal */}
      <main style={{ flex: 1, overflowY: 'auto', background: 'var(--c-bg)', padding: isMobile ? '56px 12px 16px' : 24, minWidth: 0 }}>
        {/* Topbar mobile */}
        {isMobile && (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, height: 48, zIndex: 900,
            background: '#111827', borderBottom: '1px solid #1F2937',
            display: 'flex', alignItems: 'center', padding: '0 14px', gap: 12,
          }}>
            <button onClick={() => setMobileOpen(v => !v)} style={{
              background: 'none', border: 'none', cursor: 'pointer', color: '#F9FAFB',
              fontSize: 22, padding: 4, lineHeight: 1, display: 'flex', alignItems: 'center',
            }}>☰</button>
            <span style={{ fontFamily:"'Syne',sans-serif", fontSize: 15, fontWeight: 800, color: '#F9FAFB', letterSpacing: '-.3px' }}>
              BBC File
            </span>
            {noLeidas > 0 && (
              <span style={{
                marginLeft: 'auto', background: '#E53E3E', color: '#fff',
                borderRadius: 20, padding: '2px 8px', fontSize: 11, fontWeight: 700,
              }}>
                {noLeidas} 🔔
              </span>
            )}
          </div>
        )}
        <Outlet />
      </main>

      {showWelcome && <WelcomeModal user={user} onClose={closeWelcome} />}

      {/* Modal inactividad — aviso 2 min antes de cerrar sesión */}
      {showWarning && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.55)', zIndex:3000,
          display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}>
          <div style={{ background:'#1e1e2e', borderRadius:16, maxWidth:380, width:'100%',
            boxShadow:'0 32px 80px rgba(0,0,0,.4)', overflow:'hidden' }}>
            <div style={{ height:4, background:'linear-gradient(90deg,#f59e0b,#ef4444)' }} />
            <div style={{ padding:'22px 24px 24px' }}>
              <h3 style={{ margin:'0 0 8px', color:'#f5f5f5', fontSize:17, fontWeight:800 }}>
                ⏱️ Sesión por expirar
              </h3>
              <p style={{ margin:'0 0 20px', color:'#aaa', fontSize:14, lineHeight:1.6 }}>
                Tu sesión se cerrará en <strong style={{color:'#f59e0b'}}>2 minutos</strong> por inactividad.
                ¿Deseas continuar?
              </p>
              <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
                <button onClick={handleLogout}
                  style={{ padding:'8px 16px', borderRadius:8, border:'none', cursor:'pointer',
                    background:'transparent', color:'#888', fontSize:14 }}>
                  Cerrar sesión
                </button>
                <button onClick={extender}
                  style={{ padding:'8px 20px', borderRadius:8, border:'none', cursor:'pointer',
                    background:'#4F46E5', color:'#fff', fontWeight:700, fontSize:14 }}>
                  Continuar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
