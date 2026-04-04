import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import useAuthStore from '../hooks/useAuth';
import api from '../utils/api';

const _WS_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  .replace(/^https?/, m => m === 'https' ? 'wss' : 'ws');

function _playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    ctx.resume().then(() => {
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(1000, ctx.currentTime);
      gain.gain.setValueAtTime(0.28, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.25);
      osc.addEventListener('ended', () => ctx.close());
    }).catch(() => {});
  } catch (_) {}
}

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

const navItems = (rol) => [
  { to: '/',            label: '🏠 Dashboard',           section: 'PRINCIPAL' },
  { to: '/afiliados',   label: '👥 Afiliados',            section: 'GESTIÓN' },
  { to: '/retiros',     label: '↪️ Retiros',               section: null },
  { to: '/tareas',      label: '✅ Tareas',                section: null },
  { to: '/chat',        label: '💬 Chat',                  section: null },
  { to: '/facturacion', label: '🧾 Facturación',           section: 'FINANCIERO' },
  { to: '/cobro',       label: '💰 Módulo de cobro',       section: null },
  { to: '/planillas-ss', label: '📋 Planillas SS',          section: null },
  ...(rol === 'admin' ? [
    { to: '/empleados',          label: '👔 Empleados',           section: 'ADMINISTRACIÓN' },
    { to: '/usuarios',           label: '⚙️ Usuarios',             section: null },
    { to: '/listas',             label: '📋 Listas y opciones',   section: null },
    { to: '/calculadora',        label: '🧮 Calculadora aportes', section: null },
    { to: '/actividad',          label: '📜 Registro actividad',  section: null },
    { to: '/novedades-clientes', label: '📬 Novedades clientes',  section: null },
    { to: '/backups',            label: '💾 Backups',              section: null },
  ] : []),
];

export default function Layout() {
  const { user, logout, token } = useAuthStore();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [width, setWidth] = useState(SIDEBAR_DEFAULT);
  const [showNotifs, setShowNotifs] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark');
  const [palette, setPalette] = useState(() => localStorage.getItem('palette') || 'indigo');
  const [showPalette, setShowPalette] = useState(false);
  const dragging = useRef(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);

  useEffect(() => {
    document.documentElement.setAttribute('data-palette', palette);
    localStorage.setItem('palette', palette);
  }, [palette]);

  const startX = useRef(0);
  const startW = useRef(0);

  const collapsed = width <= SIDEBAR_MIN + 10;

  const { data: notifs = [] } = useQuery({
    queryKey: ['notificaciones'],
    queryFn: () => api.get('/tareas/notificaciones').then(r => r.data),
    refetchInterval: 60_000,
  });
  const noLeidas = notifs.filter(n => !n.leida).length;
  const prevNoLeidas = useRef(noLeidas);

  useEffect(() => {
    if (noLeidas > prevNoLeidas.current) {
      try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
      } catch (_) {}
    }
    prevNoLeidas.current = noLeidas;
  }, [noLeidas]);

  const { data: chatBadge = { count: 0 } } = useQuery({
    queryKey: ['chat-no-leidos'],
    queryFn: () => api.get('/chat/no-leidos').then(r => r.data),
    refetchInterval: 15_000,
    enabled: user?.rol === 'admin',
  });

  // WS persistente para recibir alertas de mensajes privados nuevos en tiempo real
  useEffect(() => {
    if (user?.rol !== 'admin' || !token) return;
    let ws;
    let reconnectTimer;
    let active = true;

    const connect = () => {
      if (!active) return;
      ws = new WebSocket(`${_WS_BASE}/ws/chat-alertas?token=${token}`);
      ws.onmessage = () => {
        qc.invalidateQueries({ queryKey: ['chat-no-leidos'] });
        qc.invalidateQueries({ queryKey: ['chat-clientes'] });
        _playBeep();
      };
      ws.onclose = () => {
        if (active) reconnectTimer = setTimeout(connect, 5000);
      };
    };
    connect();

    return () => {
      active = false;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [user?.rol, token, qc]);

  const abrirNotifs = () => {
    setShowNotifs(v => !v);
    if (noLeidas > 0) {
      api.put('/tareas/notificaciones/leer').then(() =>
        qc.invalidateQueries({ queryKey: ['notificaciones'] })
      ).catch(() => {});
    }
  };

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

  const handleLogout = () => { logout(); navigate('/login'); };
  const items = navItems(user?.rol);

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: "'DM Sans', system-ui, sans-serif" }}>
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
      @keyframes chat-pulse-ring {
        0%   { box-shadow: 0 0 0 0 rgba(229,62,62,.55); }
        70%  { box-shadow: 0 0 0 6px rgba(229,62,62,0); }
        100% { box-shadow: 0 0 0 0 rgba(229,62,62,0); }
      }
      .chat-badge-pulse { animation: chat-pulse-ring 1.6s ease-out infinite; }
      @keyframes chat-nav-glow {
        0%, 100% { background: rgba(229,62,62,.10); }
        50%       { background: rgba(229,62,62,.18); }
      }
      .chat-nav-unread { animation: chat-nav-glow 2.4s ease-in-out infinite; }

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
      .sb-item:hover { background: rgba(255,255,255,.07) !important; color: rgba(255,255,255,.9) !important; }
      .sb-item.active::before {
        content: '';
        position: absolute; left: -8px; top: 50%; transform: translateY(-50%);
        width: 3px; height: 60%;
        background: var(--c-sidebar-active);
        border-radius: 0 2px 2px 0;
      }
      .sb-icon-box { width:28px; height:28px; border-radius:7px; background:rgba(255,255,255,.07); display:flex; align-items:center; justify-content:center; font-size:13px; flex-shrink:0; transition:background .15s; }
      .sb-item.active .sb-icon-box { background: rgba(249,158,11,.18) !important; }
      .sb-item:hover .sb-icon-box { background: rgba(255,255,255,.12) !important; }
    `}</style>

      {/* Sidebar */}
      <aside style={{
        width, minWidth: width, maxWidth: width,
        background: 'var(--c-sidebar)', display: 'flex', flexDirection: 'column',
        position: 'relative', flexShrink: 0, overflow: 'hidden',
      }}>
        {/* Logo */}
        <div style={{ padding: collapsed ? '14px 0 16px' : '14px 16px 16px', display:'flex', alignItems:'center', gap:10, whiteSpace:'nowrap', overflow:'hidden', justifyContent: collapsed ? 'center' : 'flex-start' }}>
          <div style={{ width:30, height:30, borderRadius:8, background:'linear-gradient(135deg,#F59E0B,#F97316)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:800, color:'#fff', flexShrink:0 }}>B</div>
          {!collapsed && (
            <span style={{ fontFamily:"'Syne', sans-serif", fontSize:16, fontWeight:800, color:'#fff', letterSpacing:'-.3px' }}>
              BBC <span style={{ color:'var(--c-sidebar-active)' }}>File</span>
            </span>
          )}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', paddingBottom: 12 }}>
          {items.map((item) => (
            <React.Fragment key={item.to}>
              {item.section && !collapsed && (
                <div style={{ fontSize: 9.5, color: 'rgba(255,255,255,.28)', padding: '14px 18px 5px', fontWeight: 700, letterSpacing: '.15em', whiteSpace: 'nowrap', display:'flex', alignItems:'center', gap:8 }}>
                  {item.section}
                  <span style={{ flex:1, height:1, background:'rgba(255,255,255,.07)' }} />
                </div>
              )}
              <NavLink to={item.to} end={item.to === '/'}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) => {
                  const cls = ['sb-item'];
                  if (isActive) cls.push('active');
                  if (item.to === '/chat' && chatBadge.count > 0 && !isActive) cls.push('chat-nav-unread');
                  return cls.join(' ');
                }}
                style={({ isActive }) => ({
                  display: 'flex', alignItems: 'center', position: 'relative',
                  padding: collapsed ? '10px 0' : '9px 10px',
                  margin: '1px 8px', borderRadius: 9, textDecoration: 'none', fontSize: 13,
                  color: isActive ? 'var(--c-sidebar-active)' : item.to === '/chat' && chatBadge.count > 0 ? '#fff' : 'rgba(255,255,255,.55)',
                  background: isActive ? 'linear-gradient(90deg,rgba(249,158,11,.16),rgba(249,158,11,.04))' : 'transparent',
                  fontWeight: isActive ? 600 : item.to === '/chat' && chatBadge.count > 0 ? 600 : 400,
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  whiteSpace: 'nowrap', overflow: 'hidden',
                })}>
                <span className="sb-icon-box" style={{ fontSize: collapsed ? 15 : 13, width: collapsed ? 'auto' : 28, background: 'transparent' }}>
                  {item.label.split(' ')[0]}
                </span>
                {!collapsed && <span style={{ marginLeft: 8, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label.split(' ').slice(1).join(' ')}</span>}
                {item.to === '/chat' && chatBadge.count > 0 && (
                  <span className="chat-badge-pulse" style={{
                    background: '#E53E3E', color: 'white', borderRadius: '50%',
                    minWidth: 17, height: 17, fontSize: 10, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    marginLeft: collapsed ? 0 : 'auto', flexShrink: 0,
                    position: collapsed ? 'absolute' : 'static',
                    top: collapsed ? 4 : 'auto', right: collapsed ? 4 : 'auto',
                  }}>
                    {chatBadge.count > 9 ? '9+' : chatBadge.count}
                  </span>
                )}
              </NavLink>
            </React.Fragment>
          ))}
        </nav>

        {/* Notificaciones */}
        <div style={{ position: 'relative', padding: '6px 14px', borderTop: '1px solid rgba(255,255,255,.1)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <button onClick={abrirNotifs} style={{
            background: 'none', border: 'none', color: 'rgba(255,255,255,.8)',
            cursor: 'pointer', fontSize: 20, position: 'relative', padding: '4px 6px', flexShrink: 0,
          }}>
            🔔
            {noLeidas > 0 && (
              <span style={{
                position: 'absolute', top: 0, right: 0,
                background: '#E53E3E', color: 'white', borderRadius: '50%',
                width: 17, height: 17, fontSize: 10, fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {noLeidas > 9 ? '9+' : noLeidas}
              </span>
            )}
          </button>
          {!collapsed && <span style={{ color: 'rgba(255,255,255,.5)', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden' }}>Notificaciones</span>}

          {showNotifs && (
            <div style={{
              position: 'fixed', bottom: 70, left: Math.min(width + 8, 16),
              width: 'clamp(300px, 35vw, 440px)',
              background: 'var(--c-surface)', borderRadius: 12,
              boxShadow: '0 12px 40px rgba(0,0,0,.3)', zIndex: 9999,
              maxHeight: 'min(480px, 70vh)', display: 'flex', flexDirection: 'column',
              border: '1px solid var(--c-border)',
            }}>
              {/* Header */}
              <div style={{ padding: '12px 16px', fontWeight: 700, fontSize: 14, borderBottom: '1px solid var(--c-border)', color: 'var(--c-text)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <span>🔔 Notificaciones {notifs.length > 0 && <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--c-text2)' }}>({notifs.length})</span>}</span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  {notifs.length > 0 && (
                    <button onClick={() => {
                      api.delete('/tareas/notificaciones').then(() =>
                        qc.invalidateQueries({ queryKey: ['notificaciones'] })
                      ).catch(() => {});
                    }} style={{ background: 'var(--c-red-bg)', border: 'none', cursor: 'pointer', color: 'var(--c-red)', fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 6 }}>
                      Limpiar todo
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
                {notifs.length === 0
                  ? <p style={{ padding: '24px 16px', color: 'var(--c-text2)', fontSize: 13, margin: 0, textAlign: 'center' }}>Sin notificaciones nuevas</p>
                  : notifs.map(n => (
                    <div key={n.id} style={{
                      padding: '12px 16px', borderBottom: '1px solid var(--c-border)',
                      background: n.leida ? 'transparent' : 'var(--c-blue-bg)',
                      display: 'flex', gap: 10, alignItems: 'flex-start',
                    }}>
                      <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>{n.leida ? '📭' : '📬'}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ color: 'var(--c-text)', fontSize: 13, lineHeight: 1.45, wordBreak: 'break-word' }}>{n.mensaje}</div>
                        <div style={{ color: 'var(--c-text2)', fontSize: 11, marginTop: 4 }}>{new Date(n.creado).toLocaleString('es-CO')}</div>
                      </div>
                      {!n.leida && <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--c-blue)', flexShrink: 0, marginTop: 5 }} />}
                    </div>
                  ))
                }
              </div>
            </div>
          )}
        </div>

        {/* Usuario + controles */}
        <div style={{ padding: '12px 14px', borderTop: '1px solid rgba(255,255,255,.1)' }}>
          {!collapsed && (
            <div style={{ color: 'rgba(255,255,255,.8)', fontSize: 12, marginBottom: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <span style={{ fontWeight: 600 }}>{user?.nombre}</span>
              <span style={{ marginLeft: 6, background: 'rgba(255,255,255,.15)', borderRadius: 10, padding: '1px 8px', fontSize: 10 }}>
                {user?.rol?.toUpperCase()}
              </span>
            </div>
          )}
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

        {/* ── Handle de redimensión ─────────────────────────────────────── */}
        <div
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
        />
      </aside>

      {/* Panel principal */}
      <main style={{ flex: 1, overflowY: 'auto', background: 'var(--c-bg)', padding: 24, minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
